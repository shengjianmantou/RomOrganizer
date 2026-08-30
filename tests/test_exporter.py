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
    g1 = MagicMock(title="Super Mario (USA)", region="USA", languages="En")
    g2 = MagicMock(title="Game (Japan)", region="Japan", languages="Ja")
    
    assert _is_preferred_language(g1, ["En", "Zh"]) is True
    assert _is_preferred_language(g2, ["En", "Zh"]) is False
