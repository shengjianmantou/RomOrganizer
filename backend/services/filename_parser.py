"""
Filename parser — extracts region, language, revision, and clean title
from ROM filenames using No-Intro / Redump / TOSEC-style tag conventions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Region / Language mappings ────────────────────────────────────────────────

REGION_MAP: dict[str, str] = {
    "usa": "USA",
    "us": "USA",
    "united states": "USA",
    "europe": "Europe",
    "eur": "Europe",
    "eu": "Europe",
    "japan": "Japan",
    "jpn": "Japan",
    "jp": "Japan",
    "australia": "Australia",
    "aus": "Australia",
    "brazil": "Brazil",
    "bra": "Brazil",
    "canada": "Canada",
    "can": "Canada",
    "china": "China",
    "chn": "China",
    "france": "France",
    "fra": "France",
    "germany": "Germany",
    "ger": "Germany",
    "deu": "Germany",
    "italy": "Italy",
    "ita": "Italy",
    "korea": "Korea",
    "kor": "Korea",
    "netherlands": "Netherlands",
    "nld": "Netherlands",
    "russia": "Russia",
    "rus": "Russia",
    "spain": "Spain",
    "spa": "Spain",
    "esp": "Spain",
    "sweden": "Sweden",
    "swe": "Sweden",
    "taiwan": "Taiwan",
    "twn": "Taiwan",
    "world": "World",
    "wld": "World",
    "scandinavia": "Scandinavia",
    "scan": "Scandinavia",
    "uk": "UK",
    "united kingdom": "UK",
    "gbr": "UK",
    "hong kong": "Hong Kong",
    "hkg": "Hong Kong",
    "asia": "Asia",
}

LANGUAGE_MAP: dict[str, str] = {
    "en": "En",
    "eng": "En",
    "zh": "Zh",
    "chi": "Zh",
    "zhs": "Zh",
    "zht": "Zh",
    "ja": "Ja",
    "jpn": "Ja",
    "fr": "Fr",
    "fre": "Fr",
    "de": "De",
    "ger": "De",
    "es": "Es",
    "spa": "Es",
    "it": "It",
    "ita": "It",
    "pt": "Pt",
    "por": "Pt",
    "ru": "Ru",
    "rus": "Ru",
    "ko": "Ko",
    "kor": "Ko",
    "nl": "Nl",
    "nld": "Nl",
    "sv": "Sv",
    "swe": "Sv",
    "no": "No",
    "nor": "No",
    "da": "Da",
    "dan": "Da",
    "fi": "Fi",
    "fin": "Fi",
    "pl": "Pl",
    "pol": "Pl",
}

# Known regions that imply a primary language
REGION_LANGUAGE_DEFAULTS: dict[str, list[str]] = {
    "USA": ["En"],
    "Europe": ["En"],
    "Japan": ["Ja"],
    "China": ["Zh"],
    "Taiwan": ["Zh"],
    "Hong Kong": ["Zh"],
    "Korea": ["Ko"],
    "Germany": ["De"],
    "France": ["Fr"],
    "Italy": ["It"],
    "Spain": ["Es"],
    "Brazil": ["Pt"],
    "Russia": ["Ru"],
    "Australia": ["En"],
    "Canada": ["En", "Fr"],
    "UK": ["En"],
    "World": ["En"],
    "Scandinavia": ["En", "Sv", "No", "Da"],
}

# Tags that indicate non-retail / prototype releases
SPECIAL_TAGS = {
    "beta", "proto", "prototype", "demo", "sample", "review", "hack",
    "overdump", "bad", "baddump", "pirate", "unl", "unlicensed", "homebrewn",
    "aftermarket", "test",
}

# Regex patterns
_PAREN_TAG_RE = re.compile(r"\(([^)]+)\)")
_BRACKET_TAG_RE = re.compile(r"\[([^\]]+)\]")
_REV_RE = re.compile(r"^rev\s*([a-z0-9.]+)$", re.IGNORECASE)
_VERSION_RE = re.compile(r"^v(\d[\d.a-z]*)$", re.IGNORECASE)
_DISC_RE = re.compile(r"^disc\s*(\d+)$", re.IGNORECASE)
_LANG_LIST_RE = re.compile(r"^[A-Za-z]{2}(?:,[A-Za-z]{2})*$")


@dataclass
class ParsedRomName:
    clean_title: str = ""
    region: str = ""
    languages: list[str] = field(default_factory=list)
    revision: str = ""
    version: str = ""
    disc: str = ""
    is_special: bool = False  # beta/demo/hack etc.
    extra_tags: list[str] = field(default_factory=list)

    @property
    def language_str(self) -> str:
        return ",".join(self.languages)

    @property
    def has_english(self) -> bool:
        return "En" in self.languages

    @property
    def has_chinese(self) -> bool:
        return "Zh" in self.languages

    @property
    def has_japanese(self) -> bool:
        return "Ja" in self.languages

    def lang_priority_score(self, priority: list[str]) -> int:
        """Lower = higher priority. Returns len(priority) if no match."""
        for i, lang in enumerate(priority):
            if lang in self.languages:
                return i
        return len(priority)


def parse_rom_filename(filename: str) -> ParsedRomName:
    """
    Parse a ROM filename (without directory, with or without extension)
    and return a ParsedRomName with extracted metadata.

    Supports No-Intro, Redump, and TOSEC-style naming conventions.
    """
    # Strip extension
    stem = re.sub(r"\.[^.]+$", "", filename)

    result = ParsedRomName()
    paren_tags: list[str] = _PAREN_TAG_RE.findall(stem)
    bracket_tags: list[str] = _BRACKET_TAG_RE.findall(stem)

    # Clean title = stem before first paren/bracket
    title_end = min(
        (stem.find("(") if "(" in stem else len(stem)),
        (stem.find("[") if "[" in stem else len(stem)),
    )
    raw_title = stem[:title_end].strip().rstrip(",-_ ").strip()
    # Normalize underscores to spaces if filename uses snake_case
    cleaned = re.sub(r"[_\s]+", " ", raw_title).strip()
    result.clean_title = cleaned or stem[:title_end].strip()

    all_tags = paren_tags + bracket_tags

    for raw_tag in all_tags:
        tag = raw_tag.strip()
        tag_lower = tag.lower()

        # --- Special release tags ---
        if any(s in tag_lower for s in SPECIAL_TAGS):
            result.is_special = True
            result.extra_tags.append(tag)
            continue

        # --- Revision ---
        rev_m = _REV_RE.match(tag)
        if rev_m:
            result.revision = rev_m.group(1)
            continue

        # --- Version ---
        ver_m = _VERSION_RE.match(tag)
        if ver_m:
            result.version = ver_m.group(1)
            continue

        # --- Disc ---
        disc_m = _DISC_RE.match(tag)
        if disc_m:
            result.disc = disc_m.group(1)
            continue

        # --- Language list (e.g. "En,Fr,De") ---
        if _LANG_LIST_RE.match(tag) and "," in tag:
            langs = []
            for part in tag.split(","):
                mapped = LANGUAGE_MAP.get(part.strip().lower())
                if mapped:
                    langs.append(mapped)
            if langs:
                result.languages.extend(langs)
                continue

        # --- Single language code ---
        single_lang = LANGUAGE_MAP.get(tag_lower)
        if single_lang:
            if single_lang not in result.languages:
                result.languages.append(single_lang)
            continue

        # --- Region ---
        region = REGION_MAP.get(tag_lower)
        if region:
            if not result.region:
                result.region = region
            # Infer language from region if not yet set
            continue

        # Unrecognized tag
        result.extra_tags.append(tag)

    # If no language found, infer from region
    if not result.languages and result.region:
        result.languages = REGION_LANGUAGE_DEFAULTS.get(result.region, [])

    # If still no language and it looks like a JP game (common heuristic)
    if not result.languages and not result.region:
        result.languages = []

    return result


def best_language_version(
    candidates: list[tuple[int, ParsedRomName]],
    priority: list[str] | None = None,
) -> int:
    """
    Given a list of (id, ParsedRomName) tuples representing the same game
    in different language/region variants, return the id of the best match
    according to the given language priority list.

    Priority defaults to ["En", "Zh", "Ja"].
    """
    if not candidates:
        raise ValueError("Empty candidate list")
    if priority is None:
        priority = ["En", "Zh", "Ja"]

    # Filter out special releases unless that's all we have
    normal = [(id_, p) for id_, p in candidates if not p.is_special]
    pool = normal if normal else candidates

    def score(item: tuple[int, ParsedRomName]) -> tuple[int, int]:
        _, p = item
        return (p.lang_priority_score(priority), -len(p.languages))

    best = min(pool, key=score)
    return best[0]
