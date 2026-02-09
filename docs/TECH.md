# TECH — Stack + Ops Notes

## Stack summary

- Language/runtime: Python 3.8+
- Frameworks: Tkinter (built-in), CustomTkinter (optional)
- Package manager: pip
- Build tooling: setuptools (`setup.py`)
- Database: SQLite (`image_metadata.db` by default)
- Queue/background jobs: None (batch processing uses threads + asyncio)
- Storage: Local filesystem for images and SQLite file
- Auth: None
- External APIs: Ollama (local HTTP API)
- Observability: Python logging to `image_classifier.log`
- Deployment target(s): Desktop app (local execution)
- Doc update: 2026-02-08

## How to run (authoritative)

### Clean clone prerequisites

- OS assumptions: Windows tested via `.bat` scripts (should run on any OS with Python + Tk)
- Required versions: Python 3.8+
- Required system deps: Tkinter (ships with standard Python installs on Windows)

### One-command run

```bash
python src/main.py
```

Notes:

- Install dependencies first: `pip install -r requirements.txt`
- Create config: copy `config_template.json` to `src/config/settings.json`

## Environment variables

| Name | Required | Example | Purpose | Where used |
| ---- | -------- | ------- | ------- | ---------- |
| None | N/A | N/A | Configuration is via `src/config/settings.json` | N/A |

## Ollama LLaVA setup

1) Ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

2) Run Ollama locally and pull LLaVA:

```bash
ollama pull llava:latest
ollama serve
```

3) Copy the config template:

```bash
copy config_template.json src\config\settings.json
```

4) Edit `src/config/settings.json` to ensure:

```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "model": "llava:latest",
      "timeout_seconds": 120
    }
  }
}
```

Notes:

- If `providers.ollama.enabled` is false, the app falls back to local heuristic classification.
- The Ollama client is invoked in `src/core/classifier.py` via `ollama_llava_describe_image`.

## Data & persistence

- DB schema location: created at runtime in SQLite file defined by `database_path`
- Migrations: none
- Seed data: none
- Local dev reset instructions: delete the SQLite file (default `src/image_metadata.db` if using fallback config)

## Testing

- Test frameworks: pytest (listed in `requirements.txt`)
- Tests location: `tests/` (files matching `unit_*.py`)
- How to run: `pytest`
- What “pass” means: all tests pass locally and in CI
- Coverage target (if any): not defined
- CI enforcement: GitHub Actions runs pytest on push and pull requests

## Lint/format/typecheck

- Tools: black, flake8, mypy (listed in `requirements.txt`)
- How to run: `black .`, `flake8`, `mypy` (UNVERIFIED: no config files found)
- CI enforcement: not found

## Security checks

- Dependency audit: UNVERIFIED (no `pip-audit`/`safety` tooling found)
- SAST/lint: UNVERIFIED (no security-focused lint tooling found)
- Secret scanning: UNVERIFIED (no `gitleaks`/`trufflehog` tooling found)
- Container scanning (if Docker): Not applicable (no Docker config found)

## Build/package/deploy

- Build command(s): UNVERIFIED (no build command documented; `setup.py` exists)
- Artifact(s) produced: unknown
- Deploy steps: not documented
- Rollback strategy (if applicable): not documented
