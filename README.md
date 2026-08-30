# RomOrganizer

A Calibre-like local ROM library manager with a web UI. Browse, filter, and export your ROM collection to an ES-DE-compatible directory structure for the Retroid Pocket 5 (or any ES-DE device).

## Features

- 📚 **Managed library** — import ROMs from any directory (read-only source), stored in a central library
- 🔍 **Hash identification** — CRC32/MD5/SHA1 matching against No-Intro DAT files
- 🏷️ **Metadata scraping** — cover art, descriptions, genres from ScreenScraper & TheGamesDB
- 🖼️ **Web UI** — cover art grid + sortable table view with filters by system, language, region, genre, series, year
- 📤 **ES-DE export** — exports to `roms/<system>/` structure with `gamelist.xml` per system
- 🗜️ **Format conversion** — export as original, ZIP, or 7z
- 🔄 **Deduplication** — absolute hash dedup on import; language-priority dedup on export (En → Zh → Ja → ...)
- 🔀 **Merge exports** — re-export to the same directory; existing games are never overwritten
- 📦 **Self-contained exports** — each export directory includes a portable copy of the app

## Quick Start

### Requirements
- Python 3.11+
- Node.js 18+ (for building the frontend; only needed once)

### Run

```bash
./start.sh
```

This will:
1. Create a Python virtual environment and install dependencies
2. Build the React frontend (first run only)
3. Start the server at **http://localhost:8765**

## Usage

### 1. Import ROMs

Click **Import** in the top toolbar, enter one or more directory paths (one per line), and click **Start Import**.

The importer will:
- Scan all directories recursively (read-only)
- Compute hashes and check against No-Intro DATs
- Skip exact duplicates (same hash already in library)
- Copy files to the managed library
- Fetch metadata in the background

Progress is shown in a live toast at the bottom-right.

### 2. Browse & Filter

Use the sidebar to filter by:
- **System** — NES, SNES, PS1, GBA, etc.
- **Language** — En, Zh, Ja, Fr, ...
- **Region** — USA, Europe, Japan, ...
- **Genre, Series, Year range**

Toggle between **grid** (cover art) and **list** (table) views.

### 3. Select & Export

Check games (click tiles or rows) then click **Export**.

#### Export options:
| Option | Description |
|--------|-------------|
| **Export directory** | Target path (e.g. `/Volumes/MicroSD`) |
| **ROM format** | Original (as-is) / ZIP / 7z |
| **Best version only** | One per game, chosen by language priority (default: En → Zh → Ja) |
| **All versions** | Export every selected variant |

The export creates:
```
<export_dir>/
├── roms/
│   ├── snes/
│   │   ├── Super Mario World (USA).sfc
│   │   └── gamelist.xml
│   └── psx/
│       └── ...
└── RomOrganizer/
    ├── manifest.json      ← tracks exported hashes for merge detection
    ├── start.sh           ← launch app from this export dir
    └── backend/           ← portable copy of the app
```

### 4. ES-DE on Retroid Pocket 5

Copy the contents of your export directory to your microSD card. ES-DE will pick up the `roms/` directory automatically.

### 5. Merging

To add more games to an existing export (e.g. after adding new ROMs to your library):
- Select the new games in the UI
- Set the export directory to the same path as before
- Click Export — existing files are **never overwritten**, new games are merged in

## Settings

Go to **Settings** to configure:
- ScreenScraper username/password (free account at screenscraper.fr)
- TheGamesDB API key
- Scrape-on-import toggle

## No-Intro DAT Files

For precise hash-based game identification:
1. Create a free account at [no-intro.org](https://www.no-intro.org)
2. Download DAT files for your systems
3. Place them in the `dat_files/` directory

Without DATs, the app falls back to filename tag parsing.

## Directory Structure

```
RomOrganizer/
├── backend/           # FastAPI Python backend
│   ├── services/      # scanner, hasher, importer, exporter, scraper
│   ├── routers/       # API endpoints
│   └── db/            # SQLAlchemy models
├── frontend/          # React + Vite frontend
│   └── src/
├── library/           # Managed library (created on first run)
│   ├── romorganizer.db
│   ├── files/         # Copied ROM files
│   └── media/         # Cover art & screenshots
├── dat_files/         # No-Intro DAT files (user-supplied)
├── tests/             # Unit tests
├── start.sh           # Mac/Linux launcher
└── start.bat          # Windows launcher
```

## Development

```bash
# Run backend only (with hot reload)
PYTHONPATH=. .venv/bin/uvicorn backend.main:app --reload --port 8765

# Run frontend dev server (with proxy to backend)
cd frontend && npm run dev

# Run tests
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

## Supported Systems

Nintendo (NES, SNES, N64, GB, GBC, GBA, DS, 3DS, Switch, GC, Wii, Wii U, Virtual Boy),
Sony (PS1, PS2, PS3, PSP, Vita),
Sega (Master System, Genesis/MD, Sega CD, 32X, Saturn, Dreamcast, Game Gear),
Arcade (MAME, FBNeo, Neo Geo),
Atari (2600, 5200, 7800, Lynx, Jaguar),
Microsoft (Xbox, Xbox 360),
NEC (PC Engine/TurboGrafx-16, PC Engine CD),
SNK (Neo Geo Pocket, Neo Geo Pocket Color),
Bandai (WonderSwan, WonderSwan Color),
and more.

## Notes

- **RAR**: RAR files can be read/imported, but RAR export is not supported (open-source license restriction). Export to ZIP or 7z instead.
- **Multi-disc**: Not implemented in this version. Each disc file is imported separately.
- **Source directories are always read-only** — the app never modifies source directories.
