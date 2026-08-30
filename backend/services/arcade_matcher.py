"""
MAME & Arcade ROM set matcher.
Handles arcade sets where the archive (.zip / .7z) contains multiple hardware chip dumps
(CPU, GFX, Sound, PROMs, etc.) rather than a single console ROM.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Core known Neo-Geo MVS / AES and popular MAME arcade driver names to titles
# Extended dynamically from any loaded Arcade DATs (Logiqx XML / MAME ListXML)
_ARCADE_TITLES: dict[str, str] = {
    "2020bb": "2020 Super Baseball (set 1)",
    "2020bba": "2020 Super Baseball (set 2)",
    "2020bbh": "2020 Super Baseball (set 3)",
    "3countb": "3 Count Bout / Fire Suplex (NGM-043)",
    "alpham2": "Alpha Mission II / ASO II - Last Guardian (NGM-007)",
    "androdun": "Andro Dunos (NGM-049)",
    "aof": "Art of Fighting / Ryuuko no Ken (NGM-044)",
    "aof2": "Art of Fighting 2 / Ryuuko no Ken 2 (NGM-056)",
    "aof3": "Art of Fighting 3 - The Path of the Warrior / Ryuuko no Ken Gaiden (NGM-096)",
    "bjourney": "Blue's Journey / Raguy (ALM-001)",
    "blazstar": "Blazing Star",
    "breakers": "Breakers",
    "breakrev": "Breakers Revenge",
    "bstars": "Baseball Stars Professional (NGM-002)",
    "bstars2": "Baseball Stars 2",
    "burningf": "Burning Fight (NGM-018)",
    "crsword": "Crossed Swords (ALM-002)",
    "ctomspd": "Cyber-Lip",
    "cyberlip": "Cyber-Lip (NGM-010)",
    "doubledr": "Double Dragon (Neo-Geo)",
    "fatfur1": "Fatal Fury - King of Fighters / Garou Densetsu (NGM-033)",
    "fatfur2": "Fatal Fury 2 / Garou Densetsu 2 (NGM-047)",
    "fatfursp": "Fatal Fury Special / Garou Densetsu Special (NGM-058)",
    "fatfury3": "Fatal Fury 3 - Road to the Final Victory / Garou Densetsu 3 (NGM-069)",
    "fightfev": "Fight Fever (set 1)",
    "fswords": "Fighter's Swords (Korean release of Samurai Shodown III)",
    "galaxyfg": "Galaxy Fight - Universal Warriors",
    "ganryu": "Ganryu / Musashi Ganryuki",
    "garou": "Garou - Mark of the Wolves (NGM-253)",
    "ghostlop": "Ghostlop (prototype)",
    "gpilot": "Ghost Pilots (NGM-020)",
    "gowcaizr": "Voltage Fighter Gowcaizer / Choujin Gakuen Gowcaizer",
    "gururin": "Gururin",
    "ironclad": "Ironclad / Choutetsu Brikin'ger (prototype)",
    "jchan": "Jackie Chan in Fists of Fire",
    "jockeygp": "Jockey Grand Prix",
    "kabukikl": "Kabuki Klash - Far East of Eden / Tengai Makyou - Shin Den",
    "karnovr": "Karnov's Revenge / Fighter's History Dynamite",
    "kizuna": "Kizuna Encounter - Super Tag Battle / Fu'un Super Tag Battle",
    "kof94": "The King of Fighters '94 (NGM-055)",
    "kof95": "The King of Fighters '95 (NGM-084)",
    "kof96": "The King of Fighters '96 (NGM-214)",
    "kof97": "The King of Fighters '97 (NGM-232)",
    "kof98": "The King of Fighters '98 - The Slugfest / Road to the Final Battle (NGM-242)",
    "kof99": "The King of Fighters '99 - Millennium Battle (NGM-251)",
    "kof2000": "The King of Fighters 2000 (NGM-259)",
    "kof2001": "The King of Fighters 2001 (NGM-262)",
    "kof2002": "The King of Fighters 2002 - Challenge to Ultimate Battle (NGM-265)",
    "kof2003": "The King of Fighters 2003 (NGM-271)",
    "kotm": "King of the Monsters (NGM-016)",
    "kotm2": "King of the Monsters 2 - The Next Dimension (NGM-039)",
    "lastblad": "The Last Blade / Bakumatsu Roman - Gekka no Kenshi (NGM-234)",
    "lastbld2": "The Last Blade 2 / Bakumatsu Roman - Dai Ni Maku Gekka no Kenshi (NGM-243)",
    "lastsold": "The Last Soldier (Korean release of The Last Blade)",
    "lbowling": "League Bowling (NGM-019)",
    "legendos": "Legend of Success Joe / Ashita no Joe Densetsu",
    "magdrop2": "Magical Drop II",
    "magdrop3": "Magical Drop III",
    "maglord": "Magician Lord (NGM-005)",
    "mahretsu": "Mahjong Kyoretsuden (NGM-004)",
    "marukrunc": "Maruko Deluxe Quiz",
    "matrim": "Matrimelee / Shin Gouketsuji Ichizoku - Toukon",
    "miexchng": "Money Idol Exchanger / Money Puzzle Exchanger",
    "minasan": "Minnasanno Okagesamadesu (NGM-026)",
    "mosyougi": "Master of Syougi",
    "mslug": "Metal Slug - Super Vehicle-001 (NGM-201)",
    "mslug2": "Metal Slug 2 - Super Vehicle-001/II (NGM-241)",
    "mslug3": "Metal Slug 3 (NGM-256)",
    "mslug4": "Metal Slug 4 (NGM-263)",
    "mslug5": "Metal Slug 5 (NGM-268)",
    "mslugx": "Metal Slug X - Super Vehicle-001 (NGM-250)",
    "mutnat": "Mutation Nation (NGM-014)",
    "nam1975": "NAM-1975 (NGM-001)",
    "ncombat": "Ninja Combat (NGM-009)",
    "ncommand": "Ninja Commando (NGM-050)",
    "ninjamas": "Ninja Master's - Haoh-Ninpo-Cho",
    "neobombe": "Neo Bomberman",
    "neomrdo": "Neo Mr. Do!",
    "neogeo": "Neo-Geo MVS / AES BIOS",
    "overtop": "Over Top",
    "panicbom": "Panic Bomber",
    "pnyaa": "Pochi and Nyaa",
    "popbounc": "Pop 'n Bounce / Gapporin",
    "preisle2": "Prehistoric Isle 2",
    "pulstar": "Pulstar",
    "puzzledp": "Puzzle De Pon!",
    "puzzldpr": "Puzzle De Pon! R!",
    "quizdais": "Quiz Daisousasen (NGM-021)",
    "quizkof": "Quiz King of Fighters (NGM-080)",
    "ragnagrd": "Ragnagard / Shin-Oh-Ken",
    "rbff1": "Real Bout Fatal Fury / Real Bout Garou Densetsu (NGM-095)",
    "rbff2": "Real Bout Fatal Fury 2 - The Newcomers (NGM-240)",
    "rbffspec": "Real Bout Fatal Fury Special (NGM-223)",
    "ridhero": "Riding Hero (NGM-006)",
    "roboarmy": "Robo Army (NGM-032)",
    "rotd": "Rage of the Dragons",
    "s1945p": "Strikers 1945 Plus",
    "samsho": "Samurai Shodown / Samurai Spirits (NGM-045)",
    "samsho2": "Samurai Shodown II / Shin Samurai Spirits (NGM-063)",
    "samsho3": "Samurai Shodown III / Samurai Spirits - Zankurou Musouken (NGM-087)",
    "samsho4": "Samurai Shodown IV - Amakusa's Revenge (NGM-222)",
    "samsho5": "Samurai Shodown V / Samurai Spirits Zero (NGM-270)",
    "samsh5sp": "Samurai Shodown V Special / Samurai Spirits Zero Special (NGM-272)",
    "savagere": "Savage Reign / Fu'un Mokushiroku (NGM-059)",
    "sdodgeb": "Super Dodge Ball (Neo-Geo)",
    "sengoku": "Sengoku / Sengoku Denshou (NGM-017)",
    "sengoku2": "Sengoku 2 / Sengoku Denshou 2 (NGM-040)",
    "sengoku3": "Sengoku 3 / Sengoku Densho 2001",
    "shocktr2": "Shock Troopers - 2nd Squad",
    "shocktro": "Shock Troopers (set 1)",
    "socbrawl": "Soccer Brawl (NGM-031)",
    "spinmast": "Spin Master / Miracle Adventure",
    "ssideki": "Super Sidekicks / Tokuten Ou (NGM-061)",
    "ssideki2": "Super Sidekicks 2 - The World Championship (NGM-061)",
    "ssideki3": "Super Sidekicks 3 - The Next Glory (NGM-081)",
    "ssideki4": "The Ultimate 11 - The SNK Football Championship (NGM-215)",
    "stakwin": "Stakes Winner / Stakes Winner - GI Kinzen Seiha e no Michi",
    "stakwin2": "Stakes Winner 2",
    "strhoop": "Street Hoop / Street Slam / Dunk Dream",
    "superspy": "The Super Spy (NGM-011)",
    "svc": "SNK vs. Capcom - SVC Chaos",
    "topblr": "Top Player's Golf (NGM-003)",
    "tophunt": "Top Hunter - Roddy & Cathy (NGM-046)",
    "tpgolf": "Top Player's Golf (NGM-003)",
    "tws96": "Tecmo World Soccer '96",
    "twinspri": "Twinkle Star Sprites",
    "viewpoin": "Viewpoint",
    "wakuwak7": "Waku Waku 7",
    "wh1": "World Heroes (ALM-005)",
    "wh2": "World Heroes 2 (ALM-006)",
    "wh2j": "World Heroes 2 Jet (ALM-007)",
    "whp": "World Heroes Perfect",
    "wh2jet": "World Heroes 2 Jet",
    "wjammers": "Windjammers / Flying Power Disc (NGM-065)",
    "zedblade": "Zed Blade / Operation Ragnarok",
    "zintrckb": "Zintrick / Oshidashi Zentrix (hack)",
    # Popular MAME Arcade sets
    "1941": "1941: Counter Attack (World 900227)",
    "1942": "1942 (Revision B)",
    "1943": "1943: The Battle of Midway (Euro)",
    "1943kai": "1943 Kai: Midway Kaisen (Japan)",
    "1944": "1944: The Loop Master (USA 000620)",
    "1945kiii": "1945k III",
    "10yard": "10-Yard Fight (World, set 1)",
    "005": "005",
    "pacman": "Pac-Man (Midway)",
    "puckman": "Puck Man (Japan set 1)",
    "mspacman": "Ms. Pac-Man",
    "galaga": "Galaga (Namco rev. B)",
    "donkeyk": "Donkey Kong (US set 1)",
    "dkong": "Donkey Kong (US set 1)",
    "dkongjr": "Donkey Kong Junior (US set F-4)",
    "sf2": "Street Fighter II: The World Warrior (World 910522)",
    "sf2ce": "Street Fighter II': Champion Edition (World 920513)",
    "sf2hf": "Street Fighter II': Hyper Fighting (World 921209)",
    "ssf2": "Super Street Fighter II: The New Challengers (World 931005)",
    "ssf2t": "Super Street Fighter II Turbo (World 940223)",
    "tmnt": "Teenage Mutant Ninja Turtles (World 4 Players)",
    "tmnt2": "Teenage Mutant Hero Turtles - Turtles in Time (4 Players ver UAA)",
    "simpsons": "The Simpsons (4 Players World, set 1)",
    "xmen": "X-Men (4 Players ver UBB)",
    "captcomm": "Captain Commando (World 911202)",
    "ffight": "Final Fight (World, set 1)",
    "punisher": "The Punisher (World 930422)",
    "cadillacs": "Cadillacs and Dinosaurs (World 930201)",
    "dino": "Cadillacs and Dinosaurs (World 930201)",
    "mwalk": "Michael Jackson's Moonwalker (World)",
    "outrun": "Out Run (sitdown/upright, Rev B)",
    "mk": "Mortal Kombat (rev 5.0 T-Unit 03/19/93)",
    "mk2": "Mortal Kombat II (rev L3.1)",
    "umk3": "Ultimate Mortal Kombat 3 (rev 1.2)",
    "alien3": "Alien3: The Gun (World)",
    "gauntlet": "Gauntlet (2 Players, rev 6)",
    "joust": "Joust (White/Green label)",
    "defender": "Defender (Red label)",
    "robotron": "Robotron: 2084 (Solid Blue label)",
    "centiped": "Centipede (revision 4)",
    "asteroids": "Asteroids (rev 4)",
    "tempest": "Tempest (rev 3, Revised Hardware)",
    "tron": "Tron (set 1)",
    "spyhunt": "Spy Hunter",
    "paperboy": "Paperboy (rev 3)",
    "rampage": "Rampage (Rev 3, 8/27/86)",
    "shinobi": "Shinobi (set 6, System 16A)",
    "goldnaxe": "Golden Axe (set 6, US, 8751 317-0123A)",
    "cavenger": "Cosmo Gang the Video (US)",
    "brapboys": "B.Rap Boys (World)",
    "ddragon": "Double Dragon (World set 1)",
    "ddragon2": "Double Dragon II: The Revenge (World)",
    "nbajam": "NBA Jam (rev 3.01 04/07/93)",
    "nbajamte": "NBA Jam TE (rev 4.0 03/23/94)",
    "offroad": "Ironman Stewart's Super Off-Road",
}


def is_arcade_set(path: Path) -> bool:
    """Check if a file is an arcade driver set (MAME / Neo-Geo / FBNeo)."""
    stem = path.stem.lower()
    parent = path.parent.name.lower()
    
    if parent in ("mame", "arcade", "neogeo", "fbneo", "cps1", "cps2", "cps3"):
        return True
    
    if stem in _ARCADE_TITLES:
        return True

    # If ZIP contains arcade chip dumps (e.g. .p1, .c1, .m1, .v1, prom, cpu)
    ext = path.suffix.lower()
    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                if len(names) > 1:
                    chip_suffixes = {".bin", ".rom", ".cpu", ".prom", ".p1", ".c1", ".c2", ".m1", ".v1", ".v2", ".s1"}
                    chip_matches = sum(1 for n in names if Path(n).suffix.lower() in chip_suffixes or "-" in n)
                    if chip_matches >= len(names) * 0.7:
                        return True
        except Exception:
            pass
            
    return False


def get_arcade_title(driver_name: str) -> Optional[str]:
    """Get the official human-readable title for an arcade driver name."""
    clean = driver_name.lower().strip()
    return _ARCADE_TITLES.get(clean)
