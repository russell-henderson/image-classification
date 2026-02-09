# TODO

## P0 — Unblock “run from clean clone”

- [ ] Create `src/config/settings.json` from `config_template.json` and document the copy step
- [ ] Confirm `pip install -r requirements.txt` + `python src/main.py` works on a clean clone
- [ ] Add a sample config with clearly marked placeholder API key

## P0 — Quality gates (must-have)

- [ ] Tests: expand pytest coverage for Ollama error handling and timeouts
- [ ] Lint/format: add config for black/flake8/mypy and document commands
- [ ] Security: add dependency audit, secrets scan, and basic SAST tooling

## P1 — Architecture/maintainability

- [ ] Split large UI modules (`src/ui/browser.py`, `src/ui/metadata_panel.py`)
- [ ] Remove dead code and duplicate modules
- [ ] Centralize UI strings and formatting helpers

## P1 — Product readiness

- [ ] Implement settings dialog in `MetadataPanel` flow
- [ ] Wire `MetadataPanel` “Classify Image” button to `ClassificationEngine`
- [ ] Add consistent error handling and user-visible failures

## P2 — Enhancements

- [ ] Add search filters for rating/tags/categories
- [ ] Add export/import workflows for metadata
- [ ] Add performance optimizations for large folders

## Notes

- Definition of done: matches `SHIP_CHECKLIST.md` items 1–5.
- Doc update: 2026-02-08
