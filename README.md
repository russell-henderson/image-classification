# Image Classification Desktop App

## What this is

A Python desktop application for browsing image folders, editing metadata, and running AI-assisted image classification. The UI is built on Tkinter/CustomTkinter, metadata is stored in a local SQLite database, and classification uses Ollama LLaVA with a local heuristic fallback.

## Current status

- Ship readiness: Not ready
- Confidence: Low
- Biggest risks: Missing `src/config/settings.json`, no test suite/CI, no lint/security tooling configured
- Doc update: 2026-02-08

## Tech stack (high level)

- Python 3.8+ desktop app
- Tkinter/CustomTkinter UI
- SQLite metadata storage
- Pillow + OpenCV + EXIF extraction for image handling
- Ollama LLaVA for local image description

## Quick start (clean clone)
>
> Goal: one command to run locally.

```bash
python src/main.py
```

## Configuration

- Required config file: copy `config_template.json` to `src/config/settings.json`
- Required key: `providers.ollama` settings (Ollama config; see `docs/TECH.md`)
- Secrets: do not commit `src/config/settings.json`
- Ollama setup guide: see `docs/TECH.md` → “Ollama LLaVA setup”

## Scripts / Commands

- Run: `python src/main.py`
- Test: `pytest`
- Lint/format: `black .` / `flake8` / `mypy` (UNVERIFIED: no config files found)
- Security: UNVERIFIED (no dependency audit, secrets scan, or SAST tooling found)
- Build/package: UNVERIFIED (a `setup.py` exists, but no build command is documented)
- CI: GitHub Actions runs pytest on push and pull requests (`.github/workflows/python-tests.yml`)

## Repo structure

- `src/main.py`: main app entrypoint
- `src/core/`: classification, database, and image handling
- `src/ui/`: image browser, metadata panel, batch processor UI
- `src/config/`: runtime settings (expected `settings.json`)
- `docs/`: project docs and audits
- `tests/`: pytest unit tests
- `run_simple.py`: launcher script
- `install.bat`: Windows convenience script

## Roadmap

See `docs/TODO.md` (top-to-bottom priority order).
