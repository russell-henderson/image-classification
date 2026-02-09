# Project Status: Image Classifier Desktop App (Ollama LLaVA)

## Purpose

A local-first desktop GUI app that lets a user browse images, view metadata, and generate AI-assisted metadata (description, tags, keywords, categories) using Ollama with the LLaVA vision model. The app persists metadata to a local SQLite database and reloads it on future sessions.

## Current State Summary

### What works

- GUI loads folders and displays images in grid/list mode.
- Selecting an image shows:
  - Basic information (filename, size, dimensions, timestamps).
  - Editable fields: Description, Tags, Keywords, Categories.
  - AI Classification panel showing provider/model/timestamp and the raw AI output.
  - Technical Information panel showing file stats and EXIF when available.
- Classification pipeline is now local-only:
  - Ollama is installed locally.
  - Model `llava:latest` is present.
  - OpenAI is not used and has been removed from config/deps/tests.
- Classification from the GUI is wired:
  - The MetadataPanel "Classify Image" button triggers the same `ClassificationEngine.process_image()` pipeline (async background thread).
  - Output is parsed and auto-populates Description, Tags, Keywords, Categories.
- Tests pass:
  - `pytest` currently reports: 11 passed.

### What was improved recently

#### Better descriptions (slot-first approach)

The model was returning weak prose even when prompted for richer descriptions. The solution implemented is a slot-based prompt, then the app assembles a richer description itself.

Implementation details:

- `src/core/classifier.py`
  - Added `OLLAMA_SLOT_PROMPT` (preferred) and `OLLAMA_OLD_PROMPT` (fallback).
  - Added `parse_llava_slots()`, `slots_present()`, `build_description_from_slots()`.
  - `process_image()` now uses slot-first flow, then falls back to the old structured format parser if slots are missing.
  - The old parser for CAPTION/DESCRIPTION/TAGS/KEYWORDS/CATEGORIES is kept intact for fallback.
- `tests/unit_classifier.py`
  - Updated to validate the slot-first flow via `process_image()`.
- `docs/CHANGELOG.md`
  - Logged the slot-based prompt change.

#### AI panel now contains meaningful content

The AI panel previously only showed an "ollama + timestamp" line. It now shows:

- provider/model/timestamp
- raw AI output from the prompt (either slot output or fallback output)

This provides traceability and makes debugging prompt-following easier.

#### Technical Information panel now shows real file stats

The Technical Information panel now displays:

- path, filesize, format, mode, dimensions
- EXIF block when present, otherwise "No EXIF data available"

## Persistence and Data Model

### Metadata persistence

- Metadata edits and classification results persist into a local SQLite database.
- Save Changes commits the current UI field values into the database.
- Reopening the app and reselecting an image reloads from the database.

Important note:

- Metadata is NOT embedded back into the image file (EXIF/IPTC/XMP) yet.
- Other image viewers will not see these tags/description unless they read the SQLite DB.
- Sidecar support is planned as a future step.

### ImageMetadata fields

Known to exist and used:

- filepath
- description
- tags (list or comma-separated display)
- keywords
- categories
- ai_raw
- ai_provider
- ai_model
- ai_timestamp

SQLite schema was extended safely:

- New ai_* columns are added via ALTER TABLE in a "ensure columns" style migration.

## Known Issues / Open Items

### 1) Config load warning: missing database_path

Observed at startup:

- `Error loading config: 'database_path'`

The app continues to run due to fallback behavior, but config should be normalized:

- Ensure `database_path` exists in `src/config/settings.json` and `config_template.json`.

### 2) Description quality tuning is ongoing

Slot-first descriptions are better, but can still be generic depending on the model output.
Future tuning levers:

- Make slot constraints more specific (require 2 to 4 colors, require lighting terms).
- Validate slots and retry once when slots are too generic.
- Expand keyword generation to include environment and lighting phrases.
- Add controlled vocabulary for style and environment.

### 3) Sidecar or embedded metadata is not implemented yet

Next major feature:

- Sidecar JSON or XMP next to images.
- Optional EXIF/IPTC/XMP embedding for JPEG where safe.
- Export Metadata currently exists, but needs alignment with sidecar strategy.

## How to Run

### Requirements

- Python environment with project requirements installed.
- Ollama running locally.
- LLaVA model installed: `ollama list` should show `llava:latest`.

### Run the app

From repo root:

- `python src/main.py`

### Confirm Ollama is reachable

- `ollama run llava:latest`

## Next Suggested Work (Priority Order)

1) Fix config normalization:
   - Add `database_path` to settings and template.
   - Ensure the loader handles missing keys gracefully without noisy error output.
2) Improve slot enforcement:
   - Add a description quality gate and single retry.
   - Strengthen slot prompt wording.
3) Sidecar metadata (planned next):
   - Decide schema: per-image JSON sidecar near the file.
   - Write sidecar on Save Changes and optionally on Classify.
   - Load sidecar on scan, then merge with DB rules (DB overrides vs sidecar overrides).
4) UI polish:
   - Show a "Classifying..." status indicator.
   - Disable classify button while running.
   - Better error surfacing if Ollama fails or times out.
