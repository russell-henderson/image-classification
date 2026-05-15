# Image Classification Desktop App

## Overview

This repository contains a local-first Python desktop application for browsing image folders, storing image metadata in SQLite, and generating image descriptions with a local Ollama + LLaVA setup. The UI is built with Tkinter and can use CustomTkinter when it is installed.

The app is designed around a simple workflow:

1. Open a folder or import individual images.
2. Scan images and create baseline metadata records.
3. View thumbnails and select an image.
4. Edit tags, keywords, categories, rating, and description.
5. Run AI classification on one image or many images in a batch.
6. Persist everything locally in a SQLite database.

There is no cloud dependency in the current codebase. AI classification is expected to run against a locally available Ollama HTTP endpoint, and the classifier falls back to a local heuristic mode when Ollama is unavailable or disabled.

## What The Project Includes

### Core capabilities

- Folder scanning for supported image formats.
- Thumbnail generation and in-memory thumbnail caching.
- EXIF extraction through Pillow with optional `exifread` enrichment.
- Local SQLite persistence for image metadata and cached classification output.
- Manual metadata editing in the UI.
- Single-image classification from the browser or metadata panel.
- Batch classification dialog for folders, selected files, or currently loaded browser images.
- Basic "search similar" support driven by stored classification fields.

### Supported image formats

The image handler currently accepts:

- `.jpg`
- `.jpeg`
- `.png`
- `.bmp`
- `.tiff`
- `.webp`
- `.gif`

Note that `config_template.json` lists a slightly narrower format set than the runtime image handler. The code is the authoritative behavior here.

## Architecture

The app is structured as a small desktop application with three main layers.

### Application bootstrap

- `src/main.py`

This is the main entry point. It:

- Loads configuration from `src/config/settings.json`.
- Applies default config values when keys are missing.
- Sets up logging.
- Initializes the database manager, image handler, and classification engine.
- Builds the main window and wires the browser, metadata panel, and batch processor together.

### Core services

- `src/core/database.py`
  Stores image metadata in SQLite and creates the `images` table on first run.
- `src/core/image_handler.py`
  Handles file scanning, image loading, thumbnails, EXIF extraction, resizing, hashes, and basic image statistics.
- `src/core/classifier.py`
  Handles Ollama calls, prompt parsing, local heuristic fallback, cache validation, and batch processing.

### UI components

- `src/ui/browser.py`
  Main image browser with grid/list views, search box, folder loading, and background thumbnail/classification work.
- `src/ui/metadata_panel.py`
  Right-side editor for preview, file info, rating, description, tags, keywords, categories, raw AI output, and export.
- `src/ui/batch_processor.py`
  Batch processing dialog with source selection, batch size, delay control, and progress logging.

## Repository Layout

```text
.
├── .github/workflows/python-tests.yml   # CI workflow running pytest
├── config_template.json                 # Template for runtime settings
├── docs/                                # Architecture, tech notes, status, TODOs
├── install.bat                          # Windows install helper
├── pytest.ini                           # Pytest discovery config
├── requirements.txt                     # Runtime + dev dependencies
├── run_simple.py                        # Alternate launcher that adds src/ to sys.path
├── setup.py                             # Packaging metadata
├── src/
│   ├── config/settings.json             # Local runtime config (present in this workspace)
│   ├── core/                            # Database, image handling, classification
│   ├── ui/                              # Tkinter UI components
│   ├── image_classifier.log             # Runtime log output
│   ├── image_metadata.db                # Default SQLite database
│   └── main.py                          # Main app entry point
└── tests/                               # Pytest tests
```

## Runtime Behavior

### Configuration loading

The app loads settings from:

- `src/config/settings.json`

If loading fails, `src/main.py` falls back to built-in defaults. The important defaults are:

- Ollama enabled at `http://localhost:11434`
- Ollama model `llava:latest`
- `batch_size: 10`
- `thumbnail_size: 256`
- `max_image_size: 2048`
- `rate_limit_delay: 1.0`
- `grid_columns: 6`

Relative `database_path` values are resolved relative to `src/`.

### Local data

By default, the app stores data locally in:

- `src/image_metadata.db` for image metadata and cached classification data
- `image_classifier.log` or `src/image_classifier.log` depending on the working directory used to start the app

In this workspace, a populated `src/image_metadata.db` and a local `src/config/settings.json` are already present.

### Classification flow

The classifier follows this sequence:

1. Check whether existing cached metadata is still valid.
2. Try Ollama with a strict 7-field slot prompt.
3. If the slot response is incomplete, try a legacy structured prompt.
4. If Ollama fails or is disabled, fall back to local heuristic classification.
5. Save the classification payload and derived metadata back into SQLite.

The heuristic fallback produces much simpler metadata than Ollama. It mainly derives:

- scene shape
- rough mood from brightness
- quality from blur score
- a synthetic description

## Prerequisites

### Required

- Python 3.8 or newer
- A Python build with Tkinter available

### Optional but recommended

- A virtual environment
- Ollama installed locally if you want AI descriptions
- The `llava:latest` model pulled into Ollama

## Setup

### 1. Create and activate a virtual environment

PowerShell:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

You can also use the Windows helper:

```powershell
.\install.bat
```

### 3. Create or update the runtime config

If `src/config/settings.json` does not exist, create it from the template:

```powershell
New-Item -ItemType Directory -Force src\config | Out-Null
Copy-Item config_template.json src\config\settings.json
```

Minimal example:

```json
{
  "database_path": "image_metadata.db",
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "model": "llava:latest",
      "timeout_seconds": 120,
      "story_timeout_seconds": 150,
      "story_retry_count": 1,
      "story_quick_mode_enabled": true
    }
  },
  "classification": {
    "primary_provider": "ollama"
  }
}
```

Storytelling-specific Ollama settings:

- `story_timeout_seconds`
  Upper bound for final narrative generation before the sidecar reports a timeout.
- `story_retry_count`
  Number of retry attempts after the first failed narrative attempt.
- `story_quick_mode_enabled`
  When enabled, retries switch to a shorter prompt intended to return faster.

## Ollama Setup

If you want AI-generated image descriptions, start Ollama locally and pull the expected model:

```powershell
ollama pull llava:latest
ollama serve
```

The app expects Ollama at:

- `http://localhost:11434`

If you use a different endpoint or model name, update `src/config/settings.json`.

If Ollama is disabled or unavailable, the app still runs, but classification drops to the local heuristic path.

## Running The App

### Primary entry point

```powershell
python src/main.py
```

### Alternate launcher

```powershell
python run_simple.py
```

`run_simple.py` adds `src/` to `sys.path` before importing the app, which can be useful when running from the repository root.

## How To Use The UI

### Main window

The window is split into:

- a large browser pane on the left
- a metadata/editor pane on the right

### Browser actions

- `File -> Open Folder` scans a directory recursively.
- `File -> Import Images` imports specific files.
- Grid and list buttons switch browser layout.
- The size slider changes thumbnail size.
- The search box filters by filename, description, tags, or keywords.
- Double-clicking a thumbnail triggers classification.

### Metadata panel actions

When an image is selected, the panel shows:

- preview
- file info
- star rating
- editable description
- editable tags, keywords, and categories
- raw AI output and provider/model info
- technical/EXIF details

You can:

- classify the selected image
- clear classification
- launch the storytelling sidecar with `Create`
- save changes
- revert changes
- export metadata as JSON

### Storytelling sidecar

The storytelling flow is launched from the metadata panel with `Create`.

The sidecar includes:

- a UI status test
- a Python bridge ping
- an Ollama model readiness check
- hook generation and manual Option 4 story direction

The metadata panel also shows saved story history for the currently selected image.

### Batch processing

`Tools -> Batch Process` opens a modal dialog that can process:

- an entire folder
- the images currently loaded in the browser
- a manually selected set of files

Available controls include:

- force refresh
- include subfolders
- skip already classified images
- batch size
- delay between batches

## Dependencies

### Runtime dependencies

- `customtkinter`
- `Pillow`
- `opencv-python`
- `exifread`
- `requests`
- `pandas`

### Dev/test dependencies listed in `requirements.txt`

- `pytest`
- `pytest-asyncio`
- `black`
- `flake8`
- `mypy`

Some dependencies are optional in practice. For example:

- The app runs without `customtkinter` by falling back to standard Tkinter.
- Some image statistics degrade gracefully when OpenCV or NumPy are unavailable.
- EXIF extraction still partially works without `exifread`.

## Testing

### Test configuration

Pytest is configured through `pytest.ini`:

- test path: `tests`
- file pattern: `unit_*.py`

That means the current default pytest run discovers the `unit_*.py` files, not `tests/test_setup.py`.

### Run tests

```powershell
pytest
```

In this environment, running tests through the venv failed before test execution because pytest could not create its temporary directories on Windows. The failure surfaced as `PermissionError: [WinError 5] Access is denied` when creating `pytest-of-forlu` directories. That is an environment issue worth resolving before treating the test suite as locally verified.

### CI

GitHub Actions is configured in `.github/workflows/python-tests.yml` to:

- run on `push`
- run on `pull_request`
- install dependencies with `pip install -r requirements.txt`
- execute `pytest`

## Packaging

Packaging metadata lives in `setup.py`.

Important notes:

- Package name: `image-classification-desktop`
- Python requirement: `>=3.8`
- Source package root: `src`
- Console script entry point is defined as `image-classifier=main:main`

The repository is runnable directly as an app today. Packaging support exists, but it has not been documented or verified in this README beyond what `setup.py` declares.

## Known Gaps And Caveats

- The Settings dialog in the UI is still a placeholder.
- Search similarity is basic and depends on stored classification structure.
- Logging output location depends on the working directory used to start the process.
- `requirements.txt` mixes runtime and development dependencies.
- The repository contains generated runtime artifacts in the workspace, including a SQLite database and log files.
- Linting and type-checking tools are listed, but no project-specific config files for them were found.

## Related Documentation

Useful project notes in `docs/`:

- `docs/ARCHITECTURE.md`
- `docs/TECH.md`
- `docs/TODO.md`
- `docs/PROJECT_STATUS.md`
- `docs/SHIP_CHECKLIST.md`
- `docs/AUDIT.md`

## Recommended First Run

If you want the shortest path to a working local setup:

```powershell
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull llava:latest
ollama serve
python src/main.py
```

If Ollama is not ready yet, you can still launch the app and use the local heuristic classifier instead.
