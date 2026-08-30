import pytest
from unittest.mock import MagicMock
from backend.services.exporter import _normalize_title, _pick_best_version, _is_preferred_language

def test_normalize_title_1g1r():
    assert _normalize_title("Dr. Mario (Europe)") == "drmario"
    assert _normalize_title("Dr. Mario (Japan, USA)") == "drmario"
    assert _normalize_title("dr_mario_(e)") == "drmario"
    assert _normalize_title("dr_mario_(ju)") == "drmario"
    assert _normalize_title("The Legend of Zelda (USA) (Rev 1)") == "legendofzelda"
    assert _normalize_title("Super Mario Bros. (World)") == "supermariobros"
    # SNES extensions deduplication (.smc, .sfc, .snes, .zip)
    assert _normalize_title("Super Mario World.smc") == "supermarioworld"
    assert _normalize_title("Super Mario World.sfc") == "supermarioworld"
    assert _normalize_title("Super Mario World.snes") == "supermarioworld"
    assert _normalize_title("Super Mario World (USA).smc") == "supermarioworld"
    assert _normalize_title("Super Mario World (USA).sfc.zip") == "supermarioworld"
    assert _normalize_title("Chrono Trigger (USA).smc") == _normalize_title("Chrono Trigger (USA).sfc")

def test_pick_best_version_usa_over_europe():
    g_eu = MagicMock(title="Dr. Mario (Europe)", region="Europe", languages="En")
    g_usa = MagicMock(title="Dr. Mario (Japan, USA)", region="Japan, USA", languages="En,Ja")
    
    group = [
        (g_eu, MagicMock(id=1), [MagicMock()]),
        (g_usa, MagicMock(id=1), [MagicMock()]),
    ]
    
    best = _pick_best_version(group, ["En", "Zh", "Ja"])
    assert best[0] == g_usa

def test_is_preferred_language():
    g_usa = MagicMock(title="Super Mario (USA)", region="USA", languages="En")
    g_jp = MagicMock(title="Dragon Ball (Japan)", region="Japan", languages="Ja")
    g_world = MagicMock(title="Game (World)", region="World", languages="En")
    g_eu = MagicMock(title="Castlevania (Europe)", region="Europe", languages="En")
    g_zh = MagicMock(title="Three Kingdoms (China)", region="China", languages="Zh")
    g_jp_usa = MagicMock(title="Dr. Mario (Japan, USA)", region="Japan, USA", languages="En,Ja")

    assert _is_preferred_language(g_usa) is True
    assert _is_preferred_language(g_world) is True
    assert _is_preferred_language(g_eu) is True
    assert _is_preferred_language(g_zh) is True
    assert _is_preferred_language(g_jp_usa) is True
    assert _is_preferred_language(g_jp) is False
