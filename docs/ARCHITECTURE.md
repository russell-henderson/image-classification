# Architecture

## System overview

Desktop GUI app that loads images from the local filesystem, extracts metadata, stores metadata in a local SQLite database, and calls Ollama LLaVA for image descriptions. The UI drives folder scanning, metadata editing, and batch processing.

Doc update: 2026-02-08

## Major components

- ImageClassifierApp (`src/main.py`): application bootstrap, config loading, UI wiring
- ImageBrowser (`src/ui/browser.py`): image grid/list browsing, thumbnail loading, search/filter
- MetadataPanel (`src/ui/metadata_panel.py`): metadata editing and display
- BatchProcessor (`src/ui/batch_processor.py`): batch classification workflow
- ClassificationEngine (`src/core/classifier.py`): Ollama LLaVA + local heuristic classification
- ImageHandler (`src/core/image_handler.py`): image I/O, thumbnails, EXIF, image stats
- DatabaseManager (`src/core/database.py`): SQLite schema + CRUD for metadata

## Data flow

### Primary user flows

1) Browse folder and view thumbnails

- UI requests folder scan
- `ImageHandler.scan_directory()` finds images
- `ImageBrowser` loads thumbnails and metadata (from DB or by creating new metadata)

2) Select image and edit metadata

- `ImageBrowser` selection changes
- `MetadataPanel` loads image metadata from DB
- Edits write back via `DatabaseManager.update_metadata()`

3) Classify an image (single or batch)

- `ClassificationEngine` encodes image, calls Ollama LLaVA (if enabled)
- Fallback to local heuristic if Ollama fails or is disabled
- Results stored in SQLite, UI refreshed

## Key modules and responsibilities

| Module/Dir | Responsibility | Notes |
|-----------|-----------------|------|
| `src/main.py` | App config, UI composition, event wiring | Loads `src/config/settings.json` |
| `src/core/classifier.py` | AI classification + caching | Ollama LLaVA; rate limiting |
| `src/core/image_handler.py` | Image I/O, thumbnails, EXIF | Uses Pillow/OpenCV |
| `src/core/database.py` | SQLite persistence | Creates schema on first run |
| `src/ui/browser.py` | Image browsing UI | Loads thumbnails in threads |
| `src/ui/metadata_panel.py` | Metadata editor UI | Writes metadata updates |
| `src/ui/batch_processor.py` | Batch processing UI | Thread + asyncio loop |

## Dependencies and integration points

- External services: Ollama local HTTP API
- Internal libraries/shared packages: none
- Network ports: none (local desktop app)

## Operational concerns

- Performance hotspots: large folder scans, thumbnail generation, Ollama inference latency
- Caching strategy: in-memory thumbnail cache; classification cache in SQLite
- Background jobs: background threads for scanning/loading/classification
- Failure modes + retries: Ollama failures fall back to local heuristic; minimal retry logic
- Logging/metrics/tracing: Python logging to `image_classifier.log`

## Known constraints / tradeoffs

- Secrets stored in `src/config/settings.json` (risk of accidental commit)
- CI only runs pytest; lint and security gates are not yet enforced
