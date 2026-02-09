# Ship Checklist

## 1) Reproducible local run (clean clone)

- [ ] Document one-command run in README.md
- [ ] New machine/bootstrap verified
- [ ] Env vars documented in `docs/TECH.md`
- [ ] Sample config present (`src/config/settings.json` or `.env.example`)

## 2) Tests

- [ ] Unit tests exist for core logic
- [ ] Integration tests for critical boundaries (DB/API)
- [ ] E2E tests (if UI) for top flows
- [ ] Minimum pass threshold defined
- [ ] CI runs tests on PR

## 3) Lint / format / typecheck

- [ ] Tools configured
- [ ] One command to run locally
- [ ] CI enforcement enabled

## 4) Security

- [ ] Dependency audit configured (pip-audit/safety)
- [ ] Secrets scan (gitleaks or equivalent)
- [ ] SAST (bandit or security lint rules)
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

Doc update: 2026-02-08
