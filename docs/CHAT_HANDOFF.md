# Chat Handoff Protocol: Resume This Project in a New Chat

## Goal

Enable a new chat to continue development without re-explaining the full history. This document defines:

- The exact project context to paste
- The current system state to confirm
- The "next-step" workflow and guardrails

## What You Must Paste Into the New Chat (Minimum)

Copy and paste this block into the first message of the new chat:

1) Project name and repo path

- "Image Classifier Desktop App" repo root path: <paste your local path>

2) Runtime environment

- OS: Windows
- Python version: <paste `python --version`>
- How you run it: `python src/main.py`

3) Ollama state

- Ollama installed: yes
- Model installed: `llava:latest`
- Confirm output of:
  - `ollama list`
  - `ollama run llava:latest` (just confirm it runs)

4) Current status and last completed work

- Paste `docs/PROJECT_STATUS.md` section: "Current State Summary" and "Known Issues / Open Items"
- Paste the "Key updates" summary from Cursor (the latest update message you have)

5) What you want next
Example:

- "Next I want sidecar metadata so other tools can see tags/description, and I want to decide merge rules with the DB."

## Recommended Attachments for the New Chat

To avoid guessing, include these files (copy/paste snippets or upload files):

- `src/core/classifier.py` (the process_image path, prompt, parsers)
- `src/ui/metadata_panel.py` (populate method, classification panel, technical info)
- `src/config/settings.json` and `config_template.json`
- `src/core/database.py` or whichever module defines DB path + migrations
- `tests/unit_classifier.py`

If you cannot paste full files, paste the relevant functions and config sections.

## How the Assistant Should Work in the New Chat

### Guardrails

- Do not reintroduce OpenAI.
- Ollama + LLaVA is the single source of AI truth.
- Keep changes minimal and incremental.
- Prefer reversible changes: one feature at a time.
- Keep tests passing (`pytest`) after each step.

### Workflow

1) Confirm current behavior with an explicit checklist:
   - App runs
   - Classification fills Description, Tags, Keywords, Categories
   - AI panel shows provider/model/timestamp plus raw output
   - Technical Information shows file stats
2) Identify the single next work item and implement only that.
3) Run tests and validate in the GUI.
4) Update docs:
   - `docs/CHANGELOG.md`
   - Any relevant design or status docs

## Memory and Continuity Notes

This project has several critical "truths" that should remain stable across chats:

- The app is local-first and must not call OpenAI.
- Metadata is currently stored in SQLite only.
- Slot-first LLaVA prompting is used to improve description quality.
- The UI uses:
  - `self.tags_entry`, `self.keywords_entry`, `self.categories_entry`
  - `self.classification_text` for the AI panel
  - `self.exif_text` for technical info
- Known warning: config loader expects `database_path` and currently can emit a missing-key message.

When starting a new chat, explicitly restate these truths in your first message so there is no drift.

## Quick “Resume Prompt” Template

Use this exact prompt in a new chat:

"Resume the Image Classifier Desktop App project. We are local-only with Ollama and `llava:latest`. OpenAI is removed. Slot-first prompt parsing is implemented in `src/core/classifier.py` and UI wiring is in `src/ui/metadata_panel.py` using `self.classification_text` and `self.exif_text`. Tests currently pass (11). The current known issue is the config warning for missing `database_path`. Next task: <describe next task, e.g. sidecar metadata>. Here are the relevant files/snippets: <paste/upload>."

## What Counts as Done for a Step

A step is "done" only when:

- The feature works in the GUI
- `pytest` passes
- The change is logged in `docs/CHANGELOG.md`
- Any new config keys are added to `config_template.json` and documented in `README.md` or `TECH.md`
