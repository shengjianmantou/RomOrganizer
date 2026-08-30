"""Unit tests for filename_parser, dedup logic, and language priority."""
import pytest
from backend.services.filename_parser import (
    ParsedRomName,
    best_language_version,
    parse_rom_filename,
)


class TestParseRomFilename:
    def test_usa_english(self):
        p = parse_rom_filename("Super Mario World (USA).sfc")
        assert p.clean_title == "Super Mario World"
        assert p.region == "USA"
        assert "En" in p.languages

    def test_japan(self):
        p = parse_rom_filename("Final Fantasy VI (Japan).sfc")
        assert p.region == "Japan"
        assert "Ja" in p.languages

    def test_multilang(self):
        p = parse_rom_filename("Final Fantasy VII (Europe) (En,Fr,De).iso")
        assert p.region == "Europe"
        assert "En" in p.languages
        assert "Fr" in p.languages
        assert "De" in p.languages

    def test_revision(self):
        p = parse_rom_filename("Donkey Kong (USA) (Rev 1).nes")
        assert p.revision == "1"
        assert p.region == "USA"

    def test_beta(self):
        p = parse_rom_filename("StarFox (USA) (Beta).sfc")
        assert p.is_special is True

    def test_version(self):
        p = parse_rom_filename("Sonic (USA) (v1.1).md")
        assert p.version == "1.1"

    def test_no_tags(self):
        p = parse_rom_filename("mygame.nes")
        assert p.clean_title == "mygame"
        assert p.region == ""
        assert p.languages == []

    def test_china(self):
        p = parse_rom_filename("Game Name (China).gb")
        assert p.region == "China"
        assert "Zh" in p.languages

    def test_world(self):
        p = parse_rom_filename("Tetris (World).gb")
        assert p.region == "World"
        assert "En" in p.languages


class TestBestLanguageVersion:
    def _make(self, id_: int, langs: list[str], is_special: bool = False) -> tuple[int, ParsedRomName]:
        p = ParsedRomName(clean_title="Game", languages=langs, is_special=is_special)
        return (id_, p)

    def test_prefers_english(self):
        candidates = [
            self._make(1, ["Ja"]),
            self._make(2, ["En"]),
            self._make(3, ["Zh"]),
        ]
        assert best_language_version(candidates, ["En", "Zh", "Ja"]) == 2

    def test_prefers_chinese_when_no_english(self):
        candidates = [
            self._make(1, ["Ja"]),
            self._make(2, ["Zh"]),
            self._make(3, ["De"]),
        ]
        assert best_language_version(candidates, ["En", "Zh", "Ja"]) == 2

    def test_skips_special_releases_when_possible(self):
        candidates = [
            self._make(1, ["En"], is_special=True),  # Beta
            self._make(2, ["Ja"]),
        ]
        # Should pick Ja over Beta-En
        result = best_language_version(candidates, ["En", "Zh", "Ja"])
        assert result == 2

    def test_falls_back_to_special_when_all_special(self):
        candidates = [
            self._make(1, ["En"], is_special=True),
        ]
        result = best_language_version(candidates, ["En", "Zh", "Ja"])
        assert result == 1

    def test_single_candidate(self):
        candidates = [self._make(42, ["Fr"])]
        assert best_language_version(candidates) == 42

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            best_language_version([])


class TestLangPriorityScore:
    def test_score(self):
        p = ParsedRomName(languages=["Zh", "En"])
        assert p.lang_priority_score(["En", "Zh", "Ja"]) == 0  # En found at index 0

    def test_no_match(self):
        p = ParsedRomName(languages=["De"])
        score = p.lang_priority_score(["En", "Zh", "Ja"])
        assert score == 3  # len(priority)
