# Agent Workflow

* `README.md` (create/update)
* `TODO.md`
* `ARCHITECTURE.md` (create/update)
* `TECH.md`
* `AUDIT.md`
* `SHIP_CHECKLIST.md`

Below is (1) the agent workflow and (2) copy-paste templates that make the output consistent and actionable.

---

## 1) Agent workflow (what the agent must do, in order)

### A. Intake + repo scan

1. Identify repo type(s): Python / Node / Full-stack / Docker / monorepo.
2. Inventory: list top-level files/dirs, detect entrypoints (`main.py`, `app.py`, `src/`, `package.json`, `docker-compose.yml`, etc.).
3. Detect “run from clean clone” command(s): `make dev`, `docker compose up`, `npm run dev`, `uv run`, etc.
4. Detect tests + lint: pytest/jest/vitest/playwright/eslint/ruff/black/mypy, etc.
5. Detect security tooling: pip-audit/safety/bandit/npm audit/trivy/gitleaks, etc.

### B. Read for intent and current state

* Summarize what the app does (as-is, from code and docs).
* Identify readiness gaps (missing env docs, missing migrations, no test runner, etc.).

### C. Produce the doc set

* Update existing docs if present (preserve useful content, replace stale sections).
* Output each file fully (no partial snippets).

### D. “Ready to ship” evaluation rubric

The agent must score and justify:

* **Reproducible local run from clean clone:** yes/no + exact command(s)
* **Tests:** present? pass? coverage goals?
* **Lint/format:** present? enforced? CI?
* **Security checks:** present? enforced? CI?
* **Deploy packaging:** defined? documented? repeatable?

---

## 2) Templates (copy/paste into each repo)

### README.md (template)

````md
# <Project Name>

## What this is
<1–3 paragraphs: what the project does, for who, and the core value.>

## Current status
- Ship readiness: <Not ready | MVP | Beta | Ready>  
- Confidence: <High | Medium | Low>  
- Biggest risks: <3 bullets>

## Tech stack (high level)
<Short bullets; detailed stack goes in TECH.md>

## Quick start (clean clone)
> Goal: one command to run locally.
```bash
<ONE command here, e.g. make dev OR docker compose up OR npm i && npm run dev>
````

## Configuration

* Required env vars: see `TECH.md` → “Environment Variables”
* Local data: <sqlite/postgres/files/etc>
* Secrets: <where stored + what not to commit>

## Scripts / Commands

* Run: `<...>`
* Test: `<...>`
* Lint/format: `<...>`
* Security: `<...>`

## Repo structure

<short tree of important directories and what they contain>

## Roadmap

See `TODO.md` (top-to-bottom priority order).

````

### TECH.md (template)
```md
# TECH — Stack + Ops Notes

## Stack summary
- Language/runtime:
- Frameworks:
- Package manager:
- Build tooling:
- Database:
- Queue/background jobs:
- Storage:
- Auth:
- External APIs:
- Observability:
- Deployment target(s):

## How to run (authoritative)
### Clean clone prerequisites
- OS assumptions:
- Required versions:
- Required system deps:

### One-command run
```bash
<make dev | docker compose up | npm i && npm run dev | etc>
````

## Environment variables

| Name | Required | Example | Purpose | Where used |
| ---- | -------- | ------- | ------- | ---------- |
|      |          |         |         |            |

## Data & persistence

* DB schema location:
* Migrations:
* Seed data:
* Local dev reset instructions:

## Testing

* Test frameworks:
* How to run:
* What “pass” means:
* Coverage target (if any):

## Lint/format/typecheck

* Tools:
* How to run:
* CI enforcement:

## Security checks

* Dependency audit:
* SAST/lint:
* Secret scanning:
* Container scanning (if Docker):

## Build/package/deploy

* Build command(s):
* Artifact(s) produced:
* Deploy steps:
* Rollback strategy (if applicable):

````

### ARCHITECTURE.md (template)
```md
# Architecture

## System overview
<One diagram described in words if no diagram: clients → API → DB → workers → external services>

## Major components
- <Component A>: purpose, entrypoint, key modules
- <Component B>: purpose, entrypoint, key modules

## Data flow
### Primary user flows
1) <Flow name>
- Step-by-step from UI/request through services to persistence

## Key modules and responsibilities
| Module/Dir | Responsibility | Notes |
|-----------|-----------------|------|
|           |                 |      |

## Dependencies and integration points
- External services:
- Internal libraries/shared packages:
- Network ports:

## Operational concerns
- Performance hotspots:
- Caching strategy:
- Background jobs:
- Failure modes + retries:
- Logging/metrics/tracing:

## Known constraints / tradeoffs
- <tradeoff + why>
````

### AUDIT.md (template)

```md
# Audit Report

## Executive summary
- Project intent (as implemented):
- Overall code health: <Good | Mixed | Poor>
- Biggest blockers to ship: <top 3>

## Inventory
- Entrypoints:
- Primary packages:
- Config locations:
- Tests present: <yes/no> (where)
- Lint present: <yes/no> (where)
- CI present: <yes/no> (where)

## Missing / suspicious files
- Missing: <list>
- Stale: <list>
- Duplicates / dead code likely: <list>

## Complexity & maintainability risks
### Run-on / bloated code areas
- File:line ranges + why risky
- Suggested refactor boundaries (modules to split)

### Confusing structure
- <examples: unclear naming, circular deps, mixed responsibilities>

## Reliability risks
- Error handling gaps:
- Input validation gaps:
- Race conditions / concurrency risks:
- Data integrity risks:

## Security risks
- Secrets handling issues:
- Dependency risks:
- Auth/permission risks:
- Unsafe file handling / injections:

## Recommendations (prioritized)
1) <High impact, low effort>
2) <High impact, medium effort>
3) <Longer refactor>

## Ship readiness scorecard
| Category | Status | Evidence | Fix |
|---------|--------|----------|-----|
| Clean clone run | <Pass/Fail> | <command + result> | <next step> |
| Tests | <Pass/Fail> |  |  |
| Lint/format | <Pass/Fail> |  |  |
| Security | <Pass/Fail> |  |  |
| Deploy/package | <Pass/Fail> |  |  |
```

### SHIP_CHECKLIST.md (template)

```md
# Ship Checklist

## 1) Reproducible local run (clean clone)
- [ ] Document one-command run in README.md
- [ ] New machine/bootstrap verified
- [ ] Env vars documented in TECH.md
- [ ] Sample config present (.env.example or equivalent)

## 2) Tests
- [ ] Unit tests exist for core logic
- [ ] Integration tests for critical boundaries (DB/API)
- [ ] E2E tests (if UI) for top flows
- [ ] Minimum pass threshold defined: <e.g., 100% tests pass + no skipped in CI>
- [ ] CI runs tests on PR

## 3) Lint / format / typecheck
- [ ] Tools configured
- [ ] One command to run locally
- [ ] CI enforcement enabled

## 4) Security
- [ ] Dependency audit configured (pip-audit/safety or npm audit)
- [ ] Secrets scan (gitleaks or equivalent)
- [ ] SAST (bandit/eslint security rules/etc)
- [ ] Container scan (trivy) if Docker image produced
- [ ] Security checks run in CI

## 5) Packaging / deploy
- [ ] Build artifact documented
- [ ] Deploy steps documented and repeatable
- [ ] Runtime config documented (ports, storage, env)
- [ ] Rollback plan documented (even if simple)

## 6) Release hygiene
- [ ] Versioning strategy
- [ ] Changelog notes (optional)
- [ ] License verified
- [ ] Basic smoke test script
```

### TODO.md (template with strict ordering)

```md
# TODO

## P0 — Unblock “run from clean clone”
- [ ] <Make ONE command work reliably>
- [ ] <Document prerequisites + env>
- [ ] <Provide .env.example / config template>
- [ ] <Fix missing files / broken imports / entrypoint issues>

## P0 — Quality gates (must-have)
- [ ] Tests: add baseline unit tests for core modules
- [ ] Lint/format: configure + enforce
- [ ] Security: dependency audit + secrets scan + basic SAST

## P1 — Architecture/maintainability
- [ ] Break up <file/module> into <modules> with boundaries
- [ ] Remove dead code / unused deps
- [ ] Clarify folder structure and naming

## P1 — Product readiness
- [ ] Error handling + user-facing failures
- [ ] Logging/observability baseline
- [ ] Config hardening (no hardcoded paths/secrets)

## P2 — Enhancements
- [ ] Performance improvements
- [ ] Better docs, examples
- [ ] Optional features

## Notes
- Definition of done: matches SHIP_CHECKLIST.md items 1–5.
```

---

## 3) “Agent instruction block” (paste into any agent chat)

Use this to force consistency:

```text
You are in a repo opened in an IDE. Your job: create/update exactly these files:
README.md, TODO.md, ARCHITECTURE.md, TECH.md, AUDIT.md, SHIP_CHECKLIST.md.

Rules:
1) If a doc exists, update it (preserve correct info, remove stale sections).
2) Output complete file contents for each doc.
3) TODO.md must be prioritized (P0 then P1 then P2), top-to-bottom execution order.
4) Define “ready to ship” as:
   - Runs from clean clone with ONE command (documented)
   - Tests present + defined pass threshold
   - Lint/format enforced
   - Security checks (deps audit + secrets scan + basic SAST) documented and CI-ready
   - Packaging/deploy steps documented after the above gates pass
5) In AUDIT.md, explicitly list: missing files, confusing/bloated code areas (with file paths), and concrete refactor suggestions.
6) In TECH.md, document stack + env vars + authoritative commands for run/test/lint/security/build.
```
