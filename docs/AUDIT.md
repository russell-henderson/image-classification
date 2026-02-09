# Audit Report

## Executive summary

- Project intent (as implemented): Desktop app to browse images, edit metadata, and classify images using Ollama LLaVA with local fallback.
- Overall code health: Mixed
- Biggest blockers to ship: missing `src/config/settings.json`, no lint/security tooling
- Doc update: 2026-02-08

## Inventory

- Entrypoints: `src/main.py`, `run_simple.py`
- Primary packages: `src/core/`, `src/ui/`
- Config locations: `config_template.json` (expected to be copied to `src/config/settings.json`)
- Tests present: Yes (`tests/` with `unit_*.py`, `pytest.ini`)
- Lint present: No config files found
- CI present: Yes (`.github/workflows/python-tests.yml`)

## Missing / suspicious files

- Missing: `src/config/settings.json` (referenced by `src/main.py` and README)
- Stale: none confirmed
- Duplicates / dead code likely: none confirmed

## Complexity & maintainability risks

### Run-on / bloated code areas

- `src/ui/browser.py`: large UI + threading + search logic in one module
- `src/ui/metadata_panel.py`: large UI + persistence in one module
- Suggested refactor boundaries: extract UI widgets, move data formatting helpers to a shared module

### Confusing structure

- No major structure risks detected after cleanup

## Reliability risks

- Config loading fails when `src/config/settings.json` is missing; fallback config may hide misconfiguration
- Limited error recovery for Ollama failures beyond fallback

## Security risks

- API key stored in `src/config/settings.json` without secrets scanning
- No dependency audit or SAST tooling
- CI only runs tests (no lint/security gates)

## Recommendations (prioritized)

1) Create `src/config/settings.json` from `config_template.json` and add `.env`-style guidance to avoid committing secrets
2) Add lint/format/typecheck configuration (black/flake8/mypy) and enforce in CI
3) Add security checks (dependency audit + secrets scan + SAST) and enforce in CI

## Ship readiness scorecard

| Category | Status | Evidence | Fix |
|---------|--------|----------|-----|
| Clean clone run | Fail | `src/config/settings.json` missing; deps not installed | Provide config file and bootstrap docs |
| Tests | Pass | `tests/` + `pytest.ini` + CI workflow | Expand coverage for classifier |
| Lint/format | Fail | No config found | Add tool configs and CI |
| Security | Fail | No security tooling found | Add dependency audit + secrets scan + SAST |
| Deploy/package | Fail | No build command documented | Document build/package steps |
