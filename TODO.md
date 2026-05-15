# TODO

## Purpose

This file is the working project plan for the current repo state.
It replaces the older prompt dump and should track what is done, what is unstable, and what comes next.

Last updated: 2026-05-15

## Current Baseline

- `pytest` passes: `18 passed`
- Local classifier flow is working
- Storytelling sidecar launches from the main app
- Electron <-> Python bridge now uses both stdio and file-backed JSONL fallback
- Sidecar has visible status, event log, bridge ping, and Ollama model test controls
- Story generation now has explicit timeout/error handling instead of hanging forever

## Completed

### Core Classifier

- Local-first Ollama + LLaVA classification path is implemented
- Slot-based parsing and fallback parsing are implemented
- Classification metadata persists to SQLite
- Technical info panel and AI traceability panel are implemented

### Storytelling Phase

- `src/core/story_engine.py` exists and uses `dolphin3:8b`
- `src/core/CREATIVE.md` is loaded as the storytelling system prompt
- `src/ui/metadata_panel.py` has a `Create` button
- `src/core/database.py` includes `image_stories`
- `save_story()` and `get_stories()` exist
- Option 4 manual input is separated from normal hook selection
- Sidecar UI has status LEDs, event log, Python bridge ping, and model check controls

### IPC / Sidecar Stability

- Windows launch path bypasses `npm start` and prefers direct Electron launch
- Sidecar stdin parsing is line-buffered
- File-backed bridge fallback exists in `.tmp/sidecar_bridge`
- Python-side bridge diagnostics are written to `image_classifier.log`

## Active Issues

### 1. Narrative generation can still be slow or fail depending on Ollama responsiveness

Status:

- Improved
- No longer allowed to hang forever

Current behavior:

- Narrative generation times out and surfaces an error if Ollama does not return in time

Follow-up:

- Tune `story_timeout_seconds`
- Consider shorter narrative prompt for first-pass generation
- Add retry or cancel behavior if needed

### 2. Runtime verification is still more important than test status for the sidecar

Status:

- Partially addressed

Why:

- The Python/Electron/Ollama path is integration-heavy
- `pytest` covers logic, but not the full Windows GUI runtime

Follow-up:

- Keep validating with the sidecar controls:
  - `Run UI Test Status`
  - `Ping Python Bridge`
  - `Test Ollama Model`

### 3. Main-app storytelling UX is still minimal

Status:

- Incomplete

Current gap:

- Story mode selection is still driven by simple prompts
- Story history is saved in SQLite but not surfaced well in the main app
- Sidecar can generate content, but the broader workflow still needs polish

## Next Priority Plan

### Priority 1: Make story generation operationally reliable

- [ ] Add configurable story timeout to `config_template.json`
- [ ] Add a visible timeout value in docs
- [ ] Add one retry path for transient Ollama failures
- [ ] Add a smaller/faster narrative prompt mode for quick testing
- [ ] Log story request start/end/error with enough detail to debug model stalls

Success criteria:

- Narrative generation either completes or fails visibly within the timeout window
- User can tell whether failure is bridge, model readiness, or generation latency

### Priority 2: Improve sidecar workflow

- [ ] Replace modal yes/no prompts for chaos/complexity with explicit controls in the UI or sidecar
- [ ] Show current mode and complexity more clearly in the sidecar
- [ ] Add a "Regenerate Hooks" action
- [ ] Add a "Regenerate Story" action for the selected hook
- [ ] Add a clear "Busy" / "Ready" state in the sidecar controls

Success criteria:

- User can stay inside the storytelling flow without repeated blocking prompts
- User can retry hooks/stories without relaunching the sidecar

### Priority 3: Surface story history in the main app

- [ ] Show saved stories for the current image in `metadata_panel.py` or a separate panel
- [ ] Allow selecting a prior story record
- [ ] Show mode used for each saved story
- [ ] Add copy/export for selected story

Success criteria:

- Stories are not just written to DB; they are visible and reusable from the app

### Priority 4: Expand automated coverage

- [ ] Add tests for sidecar manager message routing
- [ ] Add tests for story timeout/error paths
- [ ] Add tests for duplicate bridge message suppression
- [ ] Add tests for manual Option 4 finalization

Success criteria:

- Storytelling regression risk is reduced
- Transport and timeout behavior are covered by tests

### Priority 5: Clean up configuration and docs

- [ ] Add story-related settings to `config_template.json`
- [ ] Document sidecar verification workflow in `README.md` or `docs/PROJECT_STATUS.md`
- [ ] Remove outdated duplicated planning language from older docs
- [ ] Document bridge files and expected debug signals in `image_classifier.log`

Success criteria:

- The repo has one clear source of truth for current behavior
- A new collaborator can diagnose sidecar problems quickly

## Suggested Settings To Add

These should be added if not already present:

```json
{
  "providers": {
    "ollama": {
      "story_timeout_seconds": 150
    }
  }
}
```

Optional future settings:

```json
{
  "providers": {
    "ollama": {
      "story_timeout_seconds": 150,
      "story_retry_count": 1,
      "story_quick_mode_enabled": true
    }
  }
}
```

## Runtime Verification Checklist

Use this order when debugging:

1. Launch the app
2. Select an image with valid description/tags
3. Click `Create`
4. In the sidecar, run `Run UI Test Status`
5. Run `Ping Python Bridge`
6. Run `Test Ollama Model`
7. Generate hooks
8. Generate a story

Expected interpretation:

- If UI test works but Python ping fails:
  the Electron UI is alive but the bridge is failing

- If Python ping works but model test fails:
  the bridge is alive but Ollama/model availability is failing

- If model test works but story times out:
  Ollama is reachable but generation latency or model behavior is the issue

## Definition Of Done For Storytelling Phase

The storytelling phase is considered stable when all of the following are true:

- Sidecar launch is reliable on Windows
- Bridge ping works consistently
- Model check works consistently
- Hook generation works consistently
- Story generation either completes or fails within a bounded timeout
- Saved stories are visible from the main app
- Config and docs reflect the feature
- Tests cover the critical transport and timeout paths

---

## Verify At Every Turn

Use this section as the execution rule for all future story-side work.
No storytelling change is considered complete unless it passes both automated and runtime checks.

### Required verification for every change

1. Run `pytest -q`
2. Launch the app
3. Select an image with description and tags
4. Click `Create`
5. Run sidecar checks in this order:
   - `Run UI Test Status`
   - `Ping Python Bridge`
   - `Test Ollama Model`
6. Generate hooks
7. Generate a story
8. Confirm the story either completes or fails within the configured timeout
9. Confirm saved story history appears in the main app for that image

### Runtime pass criteria

- Sidecar opens reliably
- Event log updates immediately
- Python bridge responds
- Ollama model check responds
- Hook generation returns visible options
- Story generation returns text or a visible bounded error
- Story record is written to SQLite and shown in the metadata panel

### If a change fails verification

- Do not mark the task done
- Capture the failure in `image_classifier.log`
- Note whether failure is:
  - UI only
  - bridge only
  - Ollama/model only
  - generation latency/timeout
  - persistence/display only
- Fix the failing layer before moving to the next task

## Remaining Execution Plan

### Next implementation target

- [x] Replace the blocking `Chaos` and `Complexity` yes/no dialogs in `src/ui/metadata_panel.py` with persistent controls in the main UI

Verification:
- Launch sidecar without modal interruptions
- Confirm selected mode is visible before generating hooks
- Confirm mode and complexity are reflected in saved story records

### After that

- [ ] Add explicit `Regenerate Hooks` and `Regenerate Story` actions
- [ ] Add tests for sidecar manager retry/timeout behavior
- [ ] Add tests for duplicate bridge delivery suppression
- [ ] Add docs for bridge files and expected log output
