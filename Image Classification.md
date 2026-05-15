# **Project Export: Image Classifier AI**

## **Source Basis and Confidence Notes**

This export is based on the uploaded project handoff and project status files, plus preserved project context from prior work. The strongest source of truth is the uploaded `PROJECT_STATUS.md`, which defines the current app as a local-first desktop GUI for browsing images, viewing/editing metadata, and generating AI metadata through Ollama with `llava:latest`.  The uploaded handoff protocol also defines stable guardrails: no OpenAI, Ollama plus LLaVA as the AI source of truth, SQLite-only metadata persistence for now, slot-first prompting, and incremental reversible changes.

Important uncertainty: full current source files were not uploaded in this chat. I cannot reproduce exact current code for `classifier.py`, `metadata_panel.py`, `database.py`, or tests line-for-line. Where source code is not available, this document records confirmed behavior, known file names, expected interfaces, likely structures, and implementation notes.

---

# **1\. Project Overview**

## **Project Name**

**Image Classifier AI**

Also referred to in project documents as:

* **Image Classifier Desktop App**  
* **Image Classifier Desktop App (Ollama LLaVA)**  
* Earlier/related concept name: **PyImageSorter**

## **Short Description**

Image Classifier AI is a local-first desktop application for browsing image folders, viewing technical image metadata, editing user metadata, and generating AI-assisted descriptions, tags, keywords, and categories. The active implementation uses a Python desktop GUI, local SQLite persistence, and local Ollama with the `llava:latest` vision model rather than cloud AI services.

The app is currently focused on image metadata enrichment and classification traceability. It does not yet embed metadata back into image files, so generated metadata is stored in the local SQLite database only.

## **Primary Objective / Goal**

Build a reliable, local-only desktop image classification and metadata management tool that can:

1. Load folders of images.  
2. Display image thumbnails in grid/list views.  
3. Allow the user to select an image and inspect its metadata.  
4. Use local AI vision to generate description, tags, keywords, and categories.  
5. Persist all user edits and AI outputs locally.  
6. Eventually write sidecar metadata so other tools can use the generated metadata.

## **Secondary Objectives**

* Preserve user privacy by avoiding cloud calls.  
* Remove OpenAI dependency from this project entirely.  
* Improve AI output quality through structured, slot-first prompts.  
* Make AI output traceable by storing raw model output alongside parsed fields.  
* Support future sorting workflows based on metadata, categories, and visual content.  
* Support future sidecar JSON or XMP output.  
* Eventually consider safe embedded metadata workflows for JPEG/IPTC/XMP, but only after sidecar strategy is stable.  
* Keep every change minimal, reversible, tested, and documented.

## **Target Audience / Users**

Primary target user:

* The project owner, working locally on Windows.  
* A user with a large image library needing better classification, metadata enrichment, and sorting support.  
* A developer/operator comfortable running Python apps, Ollama, and local tests.

Secondary target users:

* Designers, media organizers, asset librarians, and AI-assisted image management users.  
* Developers who want a local-first reference app for AI image metadata workflows.

## **Success Criteria**

A project step is complete only when all of the following are true:

* The feature works in the GUI.  
* `pytest` passes.  
* The change is logged in `docs/CHANGELOG.md`.  
* Any new config keys are added to `config_template.json`.  
* Any new config behavior is documented in `README.md` or `TECH.md`.

Current working criteria already confirmed:

* App runs through `python src/main.py`.  
* GUI loads image folders and shows image grid/list views.  
* Selecting an image shows basic information, editable metadata fields, AI classification output, and technical information.  
* `Classify Image` triggers `ClassificationEngine.process_image()` in a background thread.  
* Classification fills Description, Tags, Keywords, and Categories.  
* AI panel shows provider/model/timestamp plus raw AI output.  
* Technical Information shows file stats and EXIF when available.  
* `pytest` currently reports **11 passed**.

---

# **2\. Current Status Summary**

## **Overall Progress**

**Phase:** Functional local-first desktop metadata classifier, pre-sidecar phase.

Estimated completion relative to the intended local metadata classifier:

* Core GUI browsing and selection: **Complete**  
* SQLite metadata persistence: **Complete**  
* Local Ollama LLaVA classification: **Complete**  
* Slot-first prompt parsing and fallback parser: **Complete**  
* AI traceability panel: **Complete**  
* Technical info panel: **Complete**  
* Config cleanup: **Pending**  
* Sidecar metadata: **Not started**  
* Embedded metadata: **Not started**  
* Quality gate and retry logic: **Pending**  
* UI polish around running classification: **Pending**

## **Completed & Working**

| Area | Status |
| :---- | :---- |
| Image folder loading | Working |
| Grid/list display | Working |
| Image selection | Working |
| Basic metadata display | Working |
| Editable Description, Tags, Keywords, Categories fields | Working |
| Local AI classification through Ollama | Working |
| `llava:latest` model installed and used | Working |
| OpenAI removed from active pipeline/config/deps/tests | Working |
| MetadataPanel classify button wiring | Working |
| Background-thread classification | Working |
| Slot-first prompt parsing | Working |
| Fallback old structured parser | Working |
| Raw AI output display | Working |
| SQLite persistence | Working |
| Safe schema extension for `ai_*` columns | Working |
| Tests | `pytest`: 11 passed |

## **In Progress**

| Area | Current State |
| :---- | :---- |
| Description quality tuning | Slot-first output is better, but still sometimes generic. |
| Config normalization | App emits missing `database_path` warning but continues through fallback. |
| Sidecar metadata strategy | Planned next major feature. Merge rules need decision. |
| UI polish | Needs “Classifying…” state, button disable while running, and better error surfacing. |

## **Not Yet Started**

| Area | Notes |
| :---- | :---- |
| JSON sidecar writing | Planned. Not implemented. |
| XMP sidecar writing | Planned option. Not implemented. |
| Embedded EXIF/IPTC/XMP metadata writing | Future option. Must be safe and format-aware. |
| Controlled vocabulary | Planned for better style/environment tags. |
| Description quality gate | Planned. |
| Retry-on-generic-output | Planned. |
| Other-tool interoperability | Depends on sidecar or embedded metadata. |
| Sorting/moving images by classification | Related concept, not confirmed implemented in current app. |
| PyQt/PySide \+ MobileNet/Inception version | Discussed as a conceptual or alternate direction, not the current source-of-truth implementation. |

## **Blockers / Dependencies**

| Blocker / Dependency | Impact | Resolution Path |
| :---- | :---- | :---- |
| Missing `database_path` config key | Startup warning: `Error loading config: 'database_path'` | Add `database_path` to `src/config/settings.json` and `config_template.json`; make loader graceful. |
| No sidecar metadata yet | External tools cannot see generated tags/descriptions | Implement JSON sidecar first, then decide XMP/embedded workflows. |
| LLaVA output may be generic | Lower description value | Strengthen slots, validate slots, retry once when too generic. |
| Full source files not available in this chat | Exact code cannot be exported line-for-line | Use uploaded docs as source of truth; attach files in next chat if code modification is needed. |
| Ollama runtime must be running | Classification fails if Ollama unavailable | Add better UI error surfacing and preflight checks. |

---

# **3\. Completed Work**

## **3.1 Initial Desktop Image Metadata App**

### Name / Description

A Python desktop GUI app was established for loading image folders, browsing images, selecting images, viewing technical metadata, editing metadata fields, and persisting metadata.

### Date / Sequence

Earlier phase, before the February 2026 handoff/status documents.

### Key Outputs

Confirmed project structure and files:

* `src/main.py`  
* `src/core/database.py`  
* `src/core/image_handler.py`  
* `src/core/classifier.py`  
* `src/ui/metadata_panel.py`  
* `src/config/settings.json`  
* `config_template.json`  
* `tests/unit_classifier.py`  
* `docs/PROJECT_STATUS.md`  
* `docs/CHANGELOG.md`

### Important Decisions

* Desktop GUI instead of web app for local-first workflow.  
* SQLite for local metadata persistence.  
* Editable metadata fields should remain visible and user-controlled.  
* AI-generated values should populate UI fields but still be user-editable.

### Relevant References

The status doc confirms GUI folder loading, grid/list display, image selection, editable fields, AI panel, and technical information panel.

---

## **3.2 OpenAI Removal and Local-Only AI Pivot**

### Name / Description

The project previously included OpenAI integration or OpenAI-related configuration. That path is now removed from active project truth. The app now uses local Ollama and `llava:latest`.

### Date / Sequence

Major pivot completed before the current status document.

### Key Outputs

* OpenAI removed from config/deps/tests.  
* Ollama installed locally.  
* `llava:latest` installed and used.  
* `ClassificationEngine.process_image()` wired to local Ollama LLaVA.  
* Guardrail established: do not reintroduce OpenAI.

### Important Decisions

| Decision | Rationale |
| :---- | :---- |
| Use local Ollama LLaVA only | Privacy, local-first operation, no API cost, avoids external dependency. |
| Remove OpenAI from config/deps/tests | Prevent drift and accidental cloud usage. |
| Treat Ollama plus LLaVA as single AI source of truth | Simplifies debugging, reproducibility, and user trust. |

### Relevant References

The uploaded status document states that the classification pipeline is local-only, Ollama is installed locally, `llava:latest` is present, and OpenAI is not used and removed from config/deps/tests.  The handoff protocol explicitly says not to reintroduce OpenAI and to treat Ollama plus LLaVA as the AI source of truth.

---

## **3.3 GUI Classification Wiring**

### Name / Description

The MetadataPanel `Classify Image` button now triggers the same classification pipeline as the core engine, running in an async/background thread to keep the GUI responsive.

### Date / Sequence

Completed in the current working state.

### Key Outputs

* `MetadataPanel` button wired to `ClassificationEngine.process_image()`.  
    
* Background thread prevents UI blocking.  
    
* Parsed output auto-populates:  
    
  * Description  
  * Tags  
  * Keywords  
  * Categories

### Important Decisions

* One canonical classification path should be used from the GUI.  
* Do not duplicate classification logic in the UI.  
* UI should display both parsed fields and raw AI output.

### Relevant References

The project status confirms the MetadataPanel `Classify Image` button triggers `ClassificationEngine.process_image()` through an async background thread and auto-populates the editable metadata fields.

---

## **3.4 Slot-First LLaVA Prompting**

### Name / Description

The app moved from asking LLaVA for broad prose to asking for structured visual slots first, then assembling a better description programmatically.

### Date / Sequence

Recent major improvement before project handoff.

### Key Outputs

In `src/core/classifier.py`:

* Added `OLLAMA_SLOT_PROMPT`.  
* Added `OLLAMA_OLD_PROMPT` fallback.  
* Added `parse_llava_slots()`.  
* Added `slots_present()`.  
* Added `build_description_from_slots()`.  
* Updated `process_image()` to use slot-first flow.  
* Preserved old structured parser for fallback.

In `tests/unit_classifier.py`:

* Tests updated to validate slot-first flow through `process_image()`.

In `docs/CHANGELOG.md`:

* Slot-based prompt change logged.

### Important Decisions

| Decision | Rationale |
| :---- | :---- |
| Use slot-first prompt | LLaVA produced weak prose when asked directly for richer descriptions. |
| Assemble description in app | More control over structure and consistency. |
| Keep old parser fallback | Reversible, safer, and protects against prompt-following failures. |
| Test through `process_image()` | Validates real classification path rather than isolated helpers only. |

### Confirmed Behavior

* Slot-first output is preferred.  
* If slots are missing, app falls back to old `CAPTION`, `DESCRIPTION`, `TAGS`, `KEYWORDS`, `CATEGORIES` parser.  
* Description quality is improved but still needs tuning.

---

## **3.5 AI Classification Panel Improvement**

### Name / Description

The AI panel was improved from a minimal provider/timestamp display into a traceability panel that includes raw model output.

### Date / Sequence

Recent improvement.

### Key Outputs

AI Classification panel now shows:

* Provider  
* Model  
* Timestamp  
* Raw AI output from slot prompt or fallback prompt

### Important Decisions

* Raw AI output should be retained for debugging.  
* Traceability is critical because model prompt-following can vary.  
* User should see what the model actually returned, not just the parsed fields.

### Relevant References

The uploaded status document confirms the AI panel now shows provider/model/timestamp plus raw AI output for traceability.

---

## **3.6 Technical Information Panel Improvement**

### Name / Description

The Technical Information panel now displays real file-level stats and EXIF information when available.

### Date / Sequence

Recent improvement.

### Key Outputs

Technical Information panel now displays:

* Path  
* Filesize  
* Format  
* Mode  
* Dimensions  
* EXIF block when available  
* “No EXIF data available” when EXIF is absent

### Important Decisions

* Technical metadata should be separated from user-editable classification metadata.  
* EXIF display should be informative but not required for classification.

### Relevant References

The status file confirms the Technical Information panel now shows path, filesize, format, mode, dimensions, and EXIF when available.

---

## **3.7 SQLite Persistence and Schema Extension**

### Name / Description

Metadata edits and classification results persist to a local SQLite database and reload on later sessions.

### Date / Sequence

Completed before current status.

### Key Outputs

Known persisted fields:

* `filepath`  
* `description`  
* `tags`  
* `keywords`  
* `categories`  
* `ai_raw`  
* `ai_provider`  
* `ai_model`  
* `ai_timestamp`

Schema evolution:

* New `ai_*` columns added via safe `ALTER TABLE` style migration.

### Important Decisions

| Decision | Rationale |
| :---- | :---- |
| Store metadata in SQLite | Local persistence, fast reads, simple backup, good for desktop app. |
| Add `ai_*` trace fields | Preserve provider/model/timestamp/raw output for debugging and provenance. |
| Use safe migration style | Avoid destructive DB changes. |
| Do not embed metadata yet | Avoid corrupting original image files and defer compatibility decisions. |

### Relevant References

The status file confirms SQLite persistence, save/reload behavior, `ImageMetadata` fields, and safe `ALTER TABLE` migration style for `ai_*` columns.

---

## **3.8 Test Status**

### Name / Description

The current project status reports passing tests.

### Key Output

pytest

\# 11 passed

### Important Decisions

* Keep `pytest` passing after every step.  
* Tests are part of the definition of done.  
* Slot-first flow is validated through unit tests.

### Relevant References

The uploaded status document says `pytest` currently reports 11 passed.

---

## **3.9 Handoff Protocol Created**

### Name / Description

A project handoff protocol was created to allow continuation in a new chat without drift.

### Key Outputs

Document:

* `Chat Handoff Protocol.md`

Defines:

* Minimum context to paste into a new chat.  
* Required files/snippets to attach.  
* Assistant guardrails.  
* Workflow checklist.  
* Stable project truths.  
* Resume prompt template.  
* Done criteria.

### Important Decisions

* New assistant must confirm current behavior before changing anything.  
* Only one next work item should be implemented at a time.  
* Docs must be updated after each completed feature.  
* Avoid broad rewrites.

### Relevant References

The handoff protocol lists exact guardrails, workflow, memory continuity notes, resume prompt, and done criteria.

---

# **4\. In-Progress Work**

## **4.1 Config Normalization**

### Task Name

Fix missing `database_path` config warning.

### Current State / Last Actions Taken

At startup, the app can emit:

Error loading config: 'database\_path'

The app continues running due to fallback behavior, but the warning indicates mismatch between config expectations and actual settings/template.

### Remaining Steps

1. Open `src/config/settings.json`.  
2. Add `database_path` if missing.  
3. Open `config_template.json`.  
4. Add the same key with a safe default.  
5. Find the config loader and make missing keys graceful.  
6. Confirm startup no longer prints the warning.  
7. Run:

pytest

8. Confirm GUI still launches:

python src/main.py

9. Update:  
     
   * `docs/CHANGELOG.md`  
   * `README.md` or `TECH.md`, if config behavior is documented there.

### Expected Outcome

* No noisy missing-key warning.  
* Database path is explicit and documented.  
* Existing fallback still works.  
* Tests remain at 11 passing or better.

### Suggested Config Shape

Exact current schema is not available, but a likely safe addition is:

{

  "database\_path": "src/image\_metadata.db"

}

Alternative if the app already uses a `data/` directory:

{

  "database\_path": "data/image\_metadata.db"

}

The correct value should match the actual path used by `src/core/database.py`.

---

## **4.2 Description Quality Tuning**

### Task Name

Improve slot enforcement and description quality.

### Current State / Last Actions Taken

Slot-first descriptions are better than direct prose prompting, but output can still be generic depending on LLaVA’s response.

### Remaining Steps

1. Strengthen `OLLAMA_SLOT_PROMPT`.  
     
2. Require concrete visual details:  
     
   * 2 to 4 colors  
   * Lighting description  
   * Main subject  
   * Setting/background  
   * Style or medium  
   * Composition  
   * Mood

   

3. Add quality validation:  
     
   * Detect missing/empty slots.  
   * Detect overly generic values such as “image”, “object”, “unknown”, “various”.  
   * Detect description below a minimum detail threshold.

   

4. Retry once when slots are too weak.  
     
5. Preserve fallback parser.  
     
6. Add tests for:  
     
   * Good slot output.  
   * Missing slot output.  
   * Generic slot output.  
   * Retry path.  
   * Fallback path.

   

7. Update `docs/CHANGELOG.md`.

### Expected Outcome

* Descriptions become more specific and useful.  
* Tags/keywords reflect visible content, environment, color, lighting, and style.  
* Prompt-following failures remain recoverable.

### Suggested Slot Prompt Direction

Return only the following labeled fields. Be specific and visual.

SUBJECT:

SETTING:

COLORS:

LIGHTING:

COMPOSITION:

STYLE\_OR\_MEDIUM:

MOOD:

VISIBLE\_TEXT:

DETAILS:

TAGS:

KEYWORDS:

CATEGORIES:

### Suggested Quality Gate

GENERIC\_TERMS \= {

    "image",

    "picture",

    "photo",

    "object",

    "scene",

    "unknown",

    "various",

    "miscellaneous",

    "none"

}

REQUIRED\_SLOTS \= \[

    "subject",

    "setting",

    "colors",

    "lighting",

    "composition",

    "style\_or\_medium",

    "details",

\]

---

## **4.3 Sidecar Metadata Strategy**

### Task Name

Implement per-image sidecar metadata.

### Current State / Last Actions Taken

Sidecar metadata is planned but not implemented. Metadata currently persists only in SQLite and is not visible to external image tools.

### Remaining Steps

1. Decide sidecar format:  
     
   * JSON first is recommended.  
   * XMP can be added later.

   

2. Decide naming convention:  
     
   * `image.jpg.metadata.json`  
   * `image.jpg.json`  
   * `.image.jpg.metadata.json`

   

3. Decide write timing:  
     
   * On Save Changes.  
   * Optionally after Classify Image.

   

4. Decide merge rules:  
     
   * DB overrides sidecar.  
   * Sidecar overrides DB.  
   * Newest timestamp wins.  
   * Manual edits override AI fields.

   

5. Implement sidecar service.  
     
6. Add tests.  
     
7. Update docs and config template.

### Expected Outcome

Generated metadata becomes available outside the SQLite DB and portable with image files.

### Recommended First Schema

{

  "schema\_version": 1,

  "source\_image": "example.jpg",

  "filepath": "C:/path/to/example.jpg",

  "description": "A detailed AI-assisted description.",

  "tags": \["portrait", "studio", "warm lighting"\],

  "keywords": \["person", "face", "warm tones"\],

  "categories": \["People", "Portrait"\],

  "ai": {

    "provider": "ollama",

    "model": "llava:latest",

    "timestamp": "2026-02-09T01:30:00Z",

    "raw": "SUBJECT: ...",

    "prompt\_mode": "slot\_first"

  },

  "manual": {

    "last\_saved\_at": "2026-02-09T01:35:00Z",

    "edited\_by\_user": true

  }

}

---

## **4.4 UI Classification State and Error Surfacing**

### Task Name

Improve classify button state, progress/status feedback, and Ollama failure handling.

### Current State / Last Actions Taken

Classification runs from the GUI through a background thread. However, planned polish includes:

* Show “Classifying...” status.  
* Disable classify button while running.  
* Surface better errors if Ollama fails or times out.

### Remaining Steps

1. Add UI state flag:  
     
   * `is_classifying`

   

2. Disable button during classification.  
     
3. Add visible status label or progress indicator.  
     
4. Catch Ollama connectivity errors.  
     
5. Catch model timeout errors.  
     
6. Show clear UI message and preserve existing metadata fields.  
     
7. Log error details.  
     
8. Test manually with:  
     
   * Ollama running.  
   * Ollama stopped.  
   * Invalid model name.  
   * Large image.

   

9. Add tests where practical.

### Expected Outcome

The GUI feels more stable and gives useful feedback instead of failing silently.

---

# **5\. Pending / Planned Work Backlog**

| Priority | Task | Description | Dependencies | Constraints |
| :---- | :---- | :---- | :---- | :---- |
| High | Fix `database_path` config warning | Normalize config files and loader fallback | Existing config loader | Minimal change, no broad rewrite |
| High | Strengthen slot prompt | Improve specificity of descriptions | `src/core/classifier.py` | Keep fallback parser |
| High | Add quality gate and retry | Retry once when LLaVA slots are missing/generic | Slot parser | Avoid infinite retries |
| High | Sidecar JSON metadata | Write portable metadata next to image | DB schema and save flow | Decide merge rules first |
| High | GUI classification status | Show running state and disable classify button | MetadataPanel UI | Must not block GUI |
| Medium | Better Ollama error surfacing | Show timeout/connection/model errors in UI | Classifier and UI | No raw stack traces for normal user |
| Medium | README/TECH config docs | Document config keys and runtime expectations | Config normalization | Include `database_path` |
| Medium | Controlled vocabulary | Normalize style/environment/category values | Slot parser | Keep user-editable fields |
| Medium | Batch classification | Classify multiple images in a folder | Stable single-image classifier | Needs progress, cancellation, logs |
| Medium | Metadata export alignment | Align existing export with sidecar schema | Sidecar schema | Avoid duplicate formats |
| Medium | Sorting/moving by category | Organize images based on metadata/classification | Sidecar/DB stable | Must support dry-run first |
| Low | XMP sidecar support | Add interoperable metadata sidecars | JSON sidecar stable | More complex schema |
| Low | Embedded JPEG metadata | Write EXIF/IPTC/XMP into image files | Sidecar and backups | Must be opt-in and safe |
| Low | PyQt/PySide GUI migration | Possible future GUI modernization | Current Tk app stable | Not current priority |
| Low | Local ML classifier model | MobileNet/Inception style categorization | Clear separate product goal | Do not mix until current app stable |

---

# **6\. Architecture & Design**

## **6.1 Current System Architecture**

flowchart TD

    A\[User opens app: python src/main.py\] \--\> B\[Desktop GUI\]

    B \--\> C\[Folder Browser\]

    C \--\> D\[Image Grid/List\]

    D \--\> E\[Image Selection\]

    E \--\> F\[Metadata Panel\]

    F \--\> G\[Basic Info Display\]

    F \--\> H\[Editable Metadata Fields\]

    F \--\> I\[AI Classification Panel\]

    F \--\> J\[Technical Information Panel\]

    H \--\> K\[Save Changes\]

    K \--\> L\[SQLite Metadata DB\]

    F \--\> M\[Classify Image Button\]

    M \--\> N\[Background Thread\]

    N \--\> O\[ClassificationEngine.process\_image\]

    O \--\> P\[Ollama Local API\]

    P \--\> Q\[llava:latest\]

    Q \--\> R\[Raw LLaVA Output\]

    R \--\> S\[Slot Parser\]

    S \--\> T{Slots Valid?}

    T \--\>|Yes| U\[Build Description From Slots\]

    T \--\>|No| V\[Fallback Structured Parser\]

    U \--\> W\[ImageMetadata Result\]

    V \--\> W

    W \--\> H

    W \--\> I

    W \--\> L

    J \--\> X\[Pillow/File Stats/EXIF\]

## **6.2 High-Level Architecture Description**

The app follows a local desktop architecture:

1. **GUI layer**  
     
   * Handles folder selection, image browsing, metadata editing, and user actions.  
   * Displays image information and classification outputs.

   

2. **Core service layer**  
     
   * Handles image loading, metadata extraction, classification, and database persistence.

   

3. **AI classification layer**  
     
   * Sends image input to Ollama using `llava:latest`.  
   * Uses slot-first prompting.  
   * Parses model output into structured metadata.

   

4. **Persistence layer**  
     
   * Stores metadata in SQLite.  
   * Safely extends schema with missing columns.  
   * Reloads saved metadata on future sessions.

   

5. **Future interoperability layer**  
     
   * Sidecar JSON/XMP files.  
   * Optional embedded metadata.

## **6.3 Component / Module Breakdown**

| Component / File | Responsibility | Interactions |
| :---- | :---- | :---- |
| `src/main.py` | Main app entry point | Initializes GUI, loads config, starts app |
| `src/core/classifier.py` | AI classification engine | Calls Ollama, parses output, returns metadata |
| `src/core/database.py` | SQLite persistence | Saves/loads metadata, handles schema migration |
| `src/core/image_handler.py` | Image file handling | Loads images, thumbnails, dimensions, EXIF/file stats |
| `src/ui/metadata_panel.py` | Metadata UI panel | Displays editable fields, AI output, technical info |
| `src/config/settings.json` | Runtime config | Should contain `database_path` and model/config settings |
| `config_template.json` | Safe default config template | Must include all expected keys |
| `tests/unit_classifier.py` | Unit tests for classifier flow | Validates slot-first/fallback behavior |
| `docs/PROJECT_STATUS.md` | Source of truth status document | Tracks current working state and next steps |
| `docs/CHANGELOG.md` | Change log | Must be updated after each completed change |
| `Chat Handoff Protocol.md` | Resume/new-chat protocol | Prevents context drift |

## **6.4 Data Flow**

### Image Selection Flow

User selects folder

→ app scans supported images

→ GUI renders grid/list

→ user selects image

→ app loads basic file metadata

→ app loads saved SQLite metadata, if present

→ MetadataPanel displays editable fields

→ Technical Information panel displays file stats/EXIF

### Classification Flow

User clicks Classify Image

→ MetadataPanel starts background classification

→ ClassificationEngine.process\_image(image\_path)

→ image sent to Ollama llava:latest

→ model returns raw slot output

→ parser extracts slots

→ app validates slot presence

→ app builds description from slots

→ fields are populated:

   \- description

   \- tags

   \- keywords

   \- categories

→ AI panel displays provider/model/timestamp/raw output

→ user can save changes to SQLite

### Persistence Flow

User edits metadata or classification populates metadata

→ Save Changes

→ metadata object written to SQLite

→ app is closed/reopened

→ selecting same image reloads saved metadata

## **6.5 Data Models / Schemas**

### ImageMetadata Fields

Confirmed known fields:

| Field | Type / Shape | Purpose |
| :---- | :---- | :---- |
| `filepath` | string | Absolute or app-resolved image path |
| `description` | string | User or AI-generated description |
| `tags` | list or comma-separated display | Short labels |
| `keywords` | list or comma-separated display | Search terms |
| `categories` | list or comma-separated display | Higher-level groups |
| `ai_raw` | string | Raw model output |
| `ai_provider` | string | Example: `ollama` |
| `ai_model` | string | Example: `llava:latest` |
| `ai_timestamp` | datetime/string | Classification timestamp |

### SQLite Schema Concept

Exact schema is not available, but confirmed fields imply a table similar to:

CREATE TABLE IF NOT EXISTS image\_metadata (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    filepath TEXT UNIQUE NOT NULL,

    description TEXT,

    tags TEXT,

    keywords TEXT,

    categories TEXT,

    ai\_raw TEXT,

    ai\_provider TEXT,

    ai\_model TEXT,

    ai\_timestamp TEXT,

    created\_at TEXT,

    updated\_at TEXT

);

Safe migration behavior likely resembles:

ALTER TABLE image\_metadata ADD COLUMN ai\_raw TEXT;

ALTER TABLE image\_metadata ADD COLUMN ai\_provider TEXT;

ALTER TABLE image\_metadata ADD COLUMN ai\_model TEXT;

ALTER TABLE image\_metadata ADD COLUMN ai\_timestamp TEXT;

Status confirms new `ai_*` columns are added through a safe “ensure columns” style migration.

### Future Sidecar Schema

Recommended JSON sidecar:

{

  "schema\_version": 1,

  "source\_image": "image.jpg",

  "filepath": "C:/Images/image.jpg",

  "description": "Detailed description here.",

  "tags": \["tag1", "tag2"\],

  "keywords": \["keyword1", "keyword2"\],

  "categories": \["category1"\],

  "ai": {

    "provider": "ollama",

    "model": "llava:latest",

    "timestamp": "2026-02-09T01:30:00Z",

    "raw": "Raw model output",

    "prompt\_mode": "slot\_first"

  },

  "manual": {

    "last\_saved\_at": "2026-02-09T01:35:00Z",

    "edited\_by\_user": true

  }

}

## **6.6 API / Interface Definitions**

### Internal Function: Classification Engine

Confirmed function name:

ClassificationEngine.process\_image(image\_path)

Expected behavior:

* Accepts image path.  
* Sends image to Ollama LLaVA.  
* Parses raw output.  
* Returns structured metadata.  
* Includes provider/model/timestamp/raw AI output.

Likely return shape:

{

    "description": "...",

    "tags": \["..."\],

    "keywords": \["..."\],

    "categories": \["..."\],

    "ai\_raw": "...",

    "ai\_provider": "ollama",

    "ai\_model": "llava:latest",

    "ai\_timestamp": "..."

}

### Internal Parser Functions

Confirmed functions in `src/core/classifier.py`:

parse\_llava\_slots(raw\_output)

slots\_present(slots)

build\_description\_from\_slots(slots)

Confirmed prompt constants:

OLLAMA\_SLOT\_PROMPT

OLLAMA\_OLD\_PROMPT

### UI Attributes

Confirmed MetadataPanel UI attributes:

self.tags\_entry

self.keywords\_entry

self.categories\_entry

self.classification\_text

self.exif\_text

The handoff protocol identifies these as stable continuity truths.

### Runtime Commands

python src/main.py

ollama list

ollama run llava:latest

pytest

## **6.7 Design Patterns Used**

| Pattern | Where Used | Rationale |
| :---- | :---- | :---- |
| Local-first architecture | Whole app | Privacy, offline control, no cloud dependency |
| Service separation | Core modules vs UI modules | Keeps classification/database/image logic out of GUI |
| Background worker/thread | GUI classification | Prevents UI freeze |
| Slot-first prompting | Classifier | Makes model output easier to parse and improves descriptions |
| Fallback parser | Classifier | Keeps app resilient when LLaVA does not follow slot format |
| Safe DB migration | Database layer | Adds columns without destructive migrations |
| Traceability fields | AI panel and DB | Stores raw AI output and provenance |
| Incremental change workflow | Development process | Reduces regressions and context drift |

## **6.8 Important Design Decisions & Rationale**

| Decision | Rationale | Trade-Off |
| :---- | :---- | :---- |
| Local-only Ollama LLaVA | Privacy, no cost, no cloud dependency | Quality/speed depends on local model and hardware |
| Remove OpenAI | Prevent accidental cloud use and simplify architecture | Loses access to stronger cloud vision models |
| SQLite first | Simple and reliable for desktop metadata | External tools cannot read metadata unless exported |
| Sidecar planned next | Portable metadata without modifying originals | Requires merge rules and file management |
| Do not embed metadata yet | Avoid corruption and format-specific complexity | Other image viewers cannot see metadata yet |
| Slot-first prompt | More consistent output than prose prompt | More code required for parsing and assembly |
| Keep fallback parser | Resilience and reversibility | More branches to test |
| Raw AI output shown | Debuggable and transparent | UI can become noisy if not formatted well |

---

# **7\. File & Code Inventory**

## **7.1 Confirmed Files**

| File Path / Name | Purpose | Language / Framework | Key Contents / Notes | Dependencies |
| :---- | :---- | :---- | :---- | :---- |
| `src/main.py` | App entry point | Python | Runs desktop GUI with `python src/main.py` | Tkinter/CustomTkinter likely |
| `src/core/classifier.py` | AI classification engine | Python | Ollama/LLaVA call, slot prompt, fallback parser, metadata assembly | Ollama local API, image encoding, datetime |
| `src/core/database.py` | SQLite persistence | Python | Metadata save/load, DB path, schema migration, `ai_*` columns | `sqlite3` |
| `src/core/image_handler.py` | Image file handling | Python | Image loading, thumbnails, technical stats, EXIF extraction | Pillow likely |
| `src/ui/metadata_panel.py` | Metadata and classification UI | Python GUI | Editable fields, classify button, AI panel, technical info panel | Tkinter/CustomTkinter |
| `src/config/settings.json` | Runtime settings | JSON | Missing `database_path` currently causes warning | Config loader |
| `config_template.json` | Safe config template | JSON | Should include all expected config keys | None |
| `tests/unit_classifier.py` | Classifier tests | Python/pytest | Tests slot-first `process_image()` flow | pytest |
| `docs/PROJECT_STATUS.md` | Current source-of-truth status | Markdown | Purpose, current state, known issues, next work | None |
| `docs/CHANGELOG.md` | Change log | Markdown | Slot prompt change logged | None |
| `Chat Handoff Protocol.md` | New-chat handoff | Markdown | Guardrails, resume prompt, done criteria | None |
| `README.md` | Project docs | Markdown | Should document setup/config | None |
| `TECH.md` | Technical docs | Markdown | Should document config/architecture if present | None |

## **7.2 Critical File: `src/core/classifier.py`**

### Confirmed Responsibilities

* Define prompt constants:  
    
  * `OLLAMA_SLOT_PROMPT`  
  * `OLLAMA_OLD_PROMPT`


* Send image to local Ollama LLaVA.  
    
* Parse slot output.  
    
* Check whether slots are present.  
    
* Build description from slot fields.  
    
* Fall back to old structured parser.  
    
* Return metadata fields and AI provenance.

### Confirmed Functions / Symbols

OLLAMA\_SLOT\_PROMPT \= "..."

OLLAMA\_OLD\_PROMPT \= "..."

def parse\_llava\_slots(raw\_output):

    ...

def slots\_present(slots):

    ...

def build\_description\_from\_slots(slots):

    ...

class ClassificationEngine:

    def process\_image(self, image\_path):

        ...

### Reconstructed Pseudocode

class ClassificationEngine:

    def process\_image(self, image\_path):

        timestamp \= current\_timestamp()

        raw\_output \= self.\_call\_ollama(

            image\_path=image\_path,

            prompt=OLLAMA\_SLOT\_PROMPT,

            model="llava:latest",

        )

        slots \= parse\_llava\_slots(raw\_output)

        if slots\_present(slots):

            description \= build\_description\_from\_slots(slots)

            tags \= parse\_list\_field(slots.get("tags"))

            keywords \= parse\_list\_field(slots.get("keywords"))

            categories \= parse\_list\_field(slots.get("categories"))

        else:

            parsed \= parse\_old\_structured\_output(raw\_output)

            description \= parsed.description

            tags \= parsed.tags

            keywords \= parsed.keywords

            categories \= parsed.categories

        return ImageMetadata(

            filepath=image\_path,

            description=description,

            tags=tags,

            keywords=keywords,

            categories=categories,

            ai\_raw=raw\_output,

            ai\_provider="ollama",

            ai\_model="llava:latest",

            ai\_timestamp=timestamp,

        )

## **7.3 Critical File: `src/ui/metadata_panel.py`**

### Confirmed Responsibilities

* Display selected image metadata.  
    
* Provide editable fields:  
    
  * Description  
  * Tags  
  * Keywords  
  * Categories


* Trigger classification.  
    
* Display AI traceability:  
    
  * provider  
  * model  
  * timestamp  
  * raw output


* Display technical file information and EXIF.  
    
* Save changes to SQLite.

### Confirmed UI Attributes

self.tags\_entry

self.keywords\_entry

self.categories\_entry

self.classification\_text

self.exif\_text

### Reconstructed Pseudocode

class MetadataPanel:

    def populate(self, image\_metadata, technical\_info):

        self.description\_entry.set(image\_metadata.description)

        self.tags\_entry.set(format\_list(image\_metadata.tags))

        self.keywords\_entry.set(format\_list(image\_metadata.keywords))

        self.categories\_entry.set(format\_list(image\_metadata.categories))

        self.classification\_text.configure(state="normal")

        self.classification\_text.delete("1.0", "end")

        self.classification\_text.insert("end", format\_ai\_panel(image\_metadata))

        self.classification\_text.configure(state="disabled")

        self.exif\_text.configure(state="normal")

        self.exif\_text.delete("1.0", "end")

        self.exif\_text.insert("end", format\_technical\_info(technical\_info))

        self.exif\_text.configure(state="disabled")

    def handle\_classify\_image(self):

        \# Runs ClassificationEngine.process\_image() in background thread.

        \# On completion, populate fields and AI panel.

        ...

## **7.4 Critical File: `src/core/database.py`**

### Confirmed Responsibilities

* Store and retrieve metadata.  
* Persist AI provenance fields.  
* Ensure schema has `ai_raw`, `ai_provider`, `ai_model`, `ai_timestamp`.

### Reconstructed Pseudocode

class MetadataDatabase:

    def \_\_init\_\_(self, database\_path):

        self.database\_path \= database\_path

        self.\_initialize()

        self.\_ensure\_ai\_columns()

    def save\_metadata(self, metadata):

        ...

    def get\_metadata(self, filepath):

        ...

    def \_ensure\_ai\_columns(self):

        existing\_columns \= self.\_get\_columns("image\_metadata")

        required\_columns \= {

            "ai\_raw": "TEXT",

            "ai\_provider": "TEXT",

            "ai\_model": "TEXT",

            "ai\_timestamp": "TEXT",

        }

        for column\_name, column\_type in required\_columns.items():

            if column\_name not in existing\_columns:

                self.\_execute(

                    f"ALTER TABLE image\_metadata ADD COLUMN {column\_name} {column\_type}"

                )

## **7.5 Critical File: `tests/unit_classifier.py`**

### Confirmed Responsibilities

* Validate slot-first flow.  
* Validate `process_image()`.  
* Keep tests passing.

### Confirmed Current Result

pytest

\# 11 passed

### Expected Test Themes

def test\_parse\_llava\_slots\_extracts\_expected\_fields():

    ...

def test\_slots\_present\_returns\_true\_for\_required\_slots():

    ...

def test\_slots\_present\_returns\_false\_when\_missing\_required\_slots():

    ...

def test\_build\_description\_from\_slots\_creates\_rich\_description():

    ...

def test\_process\_image\_uses\_slot\_first\_flow(monkeypatch):

    ...

def test\_process\_image\_falls\_back\_to\_old\_parser(monkeypatch):

    ...

## **7.6 Critical File: `src/config/settings.json`**

### Current Known Issue

Missing key:

"database\_path"

### Required Addition

{

  "database\_path": "src/image\_metadata.db"

}

Exact value must match the actual DB path currently used by the app.

## **7.7 Critical File: `config_template.json`**

### Required Addition

Same `database_path` key must be added to the template.

{

  "database\_path": "src/image\_metadata.db"

}

## **7.8 Critical File: `docs/PROJECT_STATUS.md`**

### Purpose

Current status, what works, known issues, and next priorities.

### Confirmed Contents

* Purpose.  
* Current state summary.  
* Working GUI behavior.  
* Local-only classification state.  
* Slot-first prompt implementation.  
* AI panel improvement.  
* Technical info improvement.  
* SQLite persistence.  
* Known issues.  
* Next suggested work.

## **7.9 Critical File: `Chat Handoff Protocol.md`**

### Purpose

Allows project continuation in a new chat.

### Confirmed Contents

* Minimum context to paste.  
* Recommended attachments.  
* Assistant guardrails.  
* Step workflow.  
* Stable truths.  
* Resume prompt.  
* Done criteria.

---

# **8\. Dependencies & Environment**

## **Programming Languages**

| Language | Version |
| :---- | :---- |
| Python | Python 3.8+ confirmed from preserved context; exact installed version must be checked with `python --version`. |
| JSON | Used for config/template and planned sidecars. |
| Markdown | Used for docs and handoff. |
| SQL | SQLite schema and migrations. |

## **Frameworks / Libraries**

| Library / Framework | Known / Likely Use | Version |
| :---- | :---- | :---- |
| Tkinter | Desktop GUI foundation | Python stdlib |
| CustomTkinter | Likely enhanced GUI widgets | Version unknown |
| Pillow / PIL | Image loading, format, EXIF, dimensions | Version unknown |
| sqlite3 | Local metadata DB | Python stdlib |
| pytest | Test runner | Version unknown |
| Ollama | Local AI runtime | Version unknown |
| LLaVA | Local vision model through Ollama | `llava:latest` |
| requests or urllib | Likely Ollama API calls | Unknown |

## **Tools & Services**

| Tool / Service | Purpose |
| :---- | :---- |
| Windows | Primary OS |
| Ollama | Local model runtime |
| `llava:latest` | Local vision model |
| SQLite | Metadata persistence |
| Cursor | Development environment previously used for updates |
| Python CLI | Running app/tests |

## **Environment Variables / Secrets**

No active secrets should be required for the current local-only implementation.

Important rule:

* Do not reintroduce `OPENAI_API_KEY`.  
* Do not require OpenAI credentials.  
* Do not store secrets in config.

Possible future environment variable names, if needed:

OLLAMA\_HOST

IMAGE\_CLASSIFIER\_CONFIG\_PATH

IMAGE\_CLASSIFIER\_DB\_PATH

## **Setup / Installation Instructions So Far**

### 1\. Confirm Python

python \--version

Expected:

Python 3.8+

### 2\. Install Python Dependencies

Exact requirements file was not included here. Likely command:

pip install \-r requirements.txt

### 3\. Confirm Ollama

ollama list

Expected:

llava:latest

### 4\. Confirm LLaVA Runs

ollama run llava:latest

### 5\. Run the App

python src/main.py

### 6\. Run Tests

pytest

Expected current result:

11 passed

---

# **9\. Key Decisions & Rationale**

## **Decision 1: Local-First Desktop App**

### What Was Decided

The project should run as a local desktop app rather than a cloud-hosted or web-first tool.

### Alternatives Considered

* Web app.  
* Cloud AI workflow.  
* API-first service.

### Why Final Choice Was Made

* User wants privacy and direct local file access.  
* Images may be personal or large.  
* Local GUI fits folder browsing and manual metadata editing.

### Trade-Offs

* GUI packaging and threading complexity.  
* Local hardware controls model speed.  
* Remote collaboration is less direct.

---

## **Decision 2: Ollama \+ LLaVA Only**

### What Was Decided

Use local Ollama with `llava:latest` as the single AI classification source.

### Alternatives Considered

* OpenAI vision models.  
* Hybrid OpenAI/Ollama.  
* TensorFlow/PyTorch classification models.  
* BLIP/CLIP style local tagging.

### Why Final Choice Was Made

* Avoid cloud calls.  
* Preserve local-first privacy.  
* OpenAI path had been removed and should not be reintroduced.  
* Existing working pipeline already uses Ollama LLaVA.

### Trade-Offs

* LLaVA may produce generic or inconsistent output.  
* Local model speed and quality may be lower than cloud models.  
* Prompt engineering and parsers are more important.

---

## **Decision 3: SQLite Metadata Persistence**

### What Was Decided

Store generated and edited metadata in a local SQLite database.

### Alternatives Considered

* Write directly into EXIF/IPTC/XMP.  
* Use per-image JSON sidecars only.  
* Use flat JSON database.

### Why Final Choice Was Made

* SQLite is safe, local, queryable, and easy to migrate.  
* Avoids modifying original image files.  
* Good fit for desktop app persistence.

### Trade-Offs

* Other tools cannot read metadata yet.  
* DB and images can get separated unless sidecars are added.  
* Merge rules become necessary once sidecars exist.

---

## **Decision 4: Do Not Embed Metadata Yet**

### What Was Decided

Do not write metadata back into image files at the current stage.

### Alternatives Considered

* Embed EXIF/IPTC metadata directly.  
* Write XMP metadata directly.  
* Use sidecar-only metadata.

### Why Final Choice Was Made

* Avoid file corruption risk.  
* Avoid format-specific complexity.  
* Allow metadata workflow to stabilize first.

### Trade-Offs

* Metadata is not visible to image viewers.  
* Interoperability is delayed.  
* Sidecar feature becomes necessary.

---

## **Decision 5: Slot-First Prompting**

### What Was Decided

Ask LLaVA for labeled visual slots first, then assemble the description in the app.

### Alternatives Considered

* Ask LLaVA directly for a detailed paragraph.  
* Use only old structured format parser.  
* Use freeform model output and heuristic parsing.

### Why Final Choice Was Made

The model returned weak prose when prompted for richer descriptions. Slot-first output gives the app more structure and control.

### Trade-Offs

* More parser code.  
* Need validation and fallback.  
* Prompt wording must be maintained.

---

## **Decision 6: Keep Old Parser as Fallback**

### What Was Decided

Keep parser support for old structured output fields:

* `CAPTION`  
* `DESCRIPTION`  
* `TAGS`  
* `KEYWORDS`  
* `CATEGORIES`

### Why Final Choice Was Made

It preserves compatibility and reduces risk if LLaVA does not follow the new slot prompt.

### Trade-Offs

* More code paths.  
* More tests required.

---

## **Decision 7: Show Raw AI Output**

### What Was Decided

Display raw AI output in the AI Classification panel along with provider/model/timestamp.

### Why Final Choice Was Made

Traceability makes debugging prompt-following easier and helps explain how fields were generated.

### Trade-Offs

* More UI content.  
* Needs formatting to avoid clutter.

---

## **Decision 8: Small Reversible Changes**

### What Was Decided

Development should proceed one feature at a time, keep tests passing, and update docs after each step.

### Why Final Choice Was Made

The project has multiple moving pieces. Incremental changes reduce breakage and context drift.

### Relevant Source

The handoff protocol explicitly requires minimal, incremental, reversible changes and keeping `pytest` passing after each step.

---

# **10\. Known Issues, Limitations & Risks**

## **Bugs**

### Bug 1: Config Warning for Missing `database_path`

#### Symptom

Error loading config: 'database\_path'

#### Impact

* Startup output is noisy.  
* Indicates config/template mismatch.  
* App still runs because fallback behavior exists.

  #### Reproduction

1. Start app:

python src/main.py

2. Observe startup warning.

   #### Fix

* Add `database_path` to `src/config/settings.json`.  
* Add `database_path` to `config_template.json`.  
* Update config loader to use `.get()` or default merging.

---

## **Current Limitations**

| Limitation | Impact |
| :---- | :---- |
| Metadata stored only in SQLite | Other tools cannot see tags/descriptions. |
| No sidecar metadata | Metadata is not portable with image files. |
| No embedded metadata | EXIF/IPTC/XMP viewers will not reflect app metadata. |
| LLaVA output can be generic | Descriptions may need manual editing. |
| No quality retry yet | Weak outputs are accepted if parser succeeds. |
| UI lacks classification running state | User may not know classification is active. |
| Error surfacing needs improvement | Ollama failures may not be clear enough. |
| Exact config schema not exported here | Must inspect current files before edits. |
| Full source not attached | Exact code cannot be reconstructed line-for-line. |

## **Technical Risks**

| Risk | Severity | Mitigation |
| :---- | :---- | :---- |
| Ollama unavailable or model missing | High | Preflight check and UI error message |
| LLaVA inconsistent formatting | Medium | Slot validation and fallback parser |
| Database path mismatch | Medium | Config normalization |
| Sidecar/DB conflict | Medium | Explicit merge rules |
| Image path changes | Medium | Consider file hash or relative path strategy |
| Writing embedded metadata could corrupt files | High | Defer, backup, opt-in only |
| Batch classification may freeze UI | Medium | Worker queue, progress, cancellation |
| Large image files may slow classification | Medium | Resize/encode preprocessing |

## **Schedule / Dependency Risks**

* Sidecar strategy can expand quickly if XMP and embedded metadata are added too early.  
* GUI refactors could introduce regressions if done before config/classifier stability.  
* PyQt/PySide migration should not happen until current Tkinter/CustomTkinter workflow is stable.  
* Mixing MobileNet/Inception sorting into the current metadata app too soon could create architectural drift.

## **Unresolved Questions**

1. What exact `database_path` should be canonical?  
     
   * `src/image_metadata.db`  
   * `data/image_metadata.db`  
   * user-configured path

   

2. What should sidecar naming be?  
     
   * `image.jpg.metadata.json`  
   * `image.jpg.json`  
   * `.image.jpg.metadata.json`

   

3. What should merge precedence be?  
     
   * DB wins.  
   * Sidecar wins.  
   * Newest timestamp wins.  
   * Manual edits always win over AI output.

   

4. Should classification auto-save to DB immediately?  
     
   * Current behavior appears to populate fields, then Save Changes commits.  
   * Need confirm whether classification results are auto-persisted.

   

5. Should sidecar writing happen:  
     
   * only on Save Changes,  
   * immediately after classification,  
   * or both?

   

6. Should image identity rely only on filepath?  
     
   * Filepath is current known field.  
   * File hash may be useful later for moved/renamed files.

   

7. Should PyImageSorter local ML classification remain a separate future project?  
     
   * Recommended: keep separate until current app is stable.

---

# **11\. Glossary / Terminology**

| Term | Definition |
| :---- | :---- |
| AI Classification panel | UI area showing provider/model/timestamp and raw AI model output. |
| AI provenance | Metadata that records where an AI result came from, including provider, model, timestamp, and raw output. |
| ClassificationEngine | Core service that processes images through Ollama LLaVA and returns metadata. |
| Controlled vocabulary | A curated set of allowed tags/categories/style terms to improve consistency. |
| DB | Database, currently SQLite. |
| EXIF | Image metadata embedded in many image formats, often camera/device information. |
| Fallback parser | Old parser that handles structured fields like `DESCRIPTION`, `TAGS`, etc. when slot parsing fails. |
| IPTC | Metadata standard often used for media/photo cataloging. |
| JSON sidecar | A separate `.json` file stored next to an image to hold metadata without modifying the image. |
| LLaVA | Local vision-language model used through Ollama. Current model is `llava:latest`. |
| Local-first | Design principle where data and AI processing stay on the user’s machine. |
| MetadataPanel | UI panel responsible for metadata fields, classification output, and technical info. |
| Ollama | Local model runtime used to run LLaVA. |
| OpenAI removal | Project decision that OpenAI must not be used in this app. |
| Prompt mode | The prompt strategy used to generate output, currently slot-first with fallback. |
| PyImageSorter | Related or alternate conceptual direction involving PyQt/PySide and MobileNet/Inception sorting. Not the current source-of-truth implementation. |
| SQLite | Local file-based relational database used to persist metadata. |
| Slot-first prompt | Prompt strategy where model returns labeled visual slots first, then app assembles description. |
| Technical Information panel | UI area showing path, file size, format, mode, dimensions, and EXIF data. |
| XMP | XML-based metadata standard often used as embedded metadata or sidecar files. |

---

# **12\. Next Actions**

## **Immediate Action 1: Verify Current Runtime State**

Run from repo root:

python \--version

ollama list

ollama run llava:latest

python src/main.py

pytest

Expected:

11 passed

## **Immediate Action 2: Fix Config Normalization**

Files to inspect/edit:

* `src/config/settings.json`  
* `config_template.json`  
* config loader module, likely near `src/config/` or inside app initialization  
* `src/core/database.py`, to confirm actual DB path expectation

Acceptance criteria:

* No `Error loading config: 'database_path'` at startup.  
* DB still loads existing metadata.  
* `pytest` passes.  
* Change logged in `docs/CHANGELOG.md`.

## **Immediate Action 3: Strengthen Slot Prompt and Add Quality Gate**

Files to inspect/edit:

* `src/core/classifier.py`  
* `tests/unit_classifier.py`

Implementation targets:

* Strengthen `OLLAMA_SLOT_PROMPT`.  
* Add required slots.  
* Add generic-output detection.  
* Retry once on weak slot output.  
* Preserve old fallback parser.

Acceptance criteria:

* Good slot outputs produce richer descriptions.  
* Weak slot outputs trigger retry.  
* Missing slots still fall back safely.  
* Tests pass.

## **Immediate Action 4: Decide Sidecar Merge Rules Before Coding**

Recommended decision:

Manual UI edits are highest authority.

SQLite is the current app state.

Sidecar is portable export/import state.

When both DB and sidecar exist, newest manual timestamp wins.

AI-only sidecar values must not overwrite newer manual DB values.

Minimum decision needed before implementation:

| Question | Recommended Answer |
| :---- | :---- |
| Sidecar format | JSON first |
| File name | `image.jpg.metadata.json` |
| Write timing | On Save Changes |
| Read timing | On image selection or folder scan |
| Merge rule | Manual/newest wins |
| Embedded metadata | Defer |

## **Immediate Action 5: Implement Sidecar JSON Service**

Suggested new file:

src/core/sidecar.py

Suggested functions:

def sidecar\_path\_for\_image(image\_path: str) \-\> str:

    ...

def write\_sidecar(image\_path: str, metadata: ImageMetadata) \-\> None:

    ...

def read\_sidecar(image\_path: str) \-\> dict | None:

    ...

def merge\_db\_and\_sidecar(db\_metadata, sidecar\_metadata):

    ...

Tests:

tests/unit\_sidecar.py

Acceptance criteria:

* Save Changes writes sidecar.  
* Existing sidecar can be read.  
* Merge behavior is deterministic.  
* DB remains source of current app truth.  
* Tests pass.  
* Docs updated.

## **Immediate Action 6: Add UI Running State**

File:

src/ui/metadata\_panel.py

Expected behavior:

* When classification starts:  
    
  * Disable Classify Image button.  
  * Show “Classifying...” status.


* When classification completes:  
    
  * Re-enable button.  
  * Populate fields.  
  * Update AI panel.


* When classification fails:  
    
  * Re-enable button.  
  * Show clear error.  
  * Do not erase existing metadata.

---

# **13\. Conversation Highlights**

1. The project is a local-first desktop image metadata/classification app.  
2. The active implementation uses Python desktop GUI plus SQLite plus Ollama LLaVA.  
3. OpenAI has been removed and must not be reintroduced.  
4. `llava:latest` is the active local vision model.  
5. The GUI can load folders and display images in grid/list mode.  
6. Selecting an image shows basic information and editable metadata.  
7. The MetadataPanel `Classify Image` button calls `ClassificationEngine.process_image()` on a background thread.  
8. AI output fills Description, Tags, Keywords, and Categories.  
9. The AI panel now shows provider/model/timestamp and raw model output.  
10. The Technical Information panel now shows real file stats and EXIF when available.  
11. SQLite persists metadata across sessions.  
12. The SQLite schema includes `ai_raw`, `ai_provider`, `ai_model`, and `ai_timestamp`.  
13. The project moved to slot-first LLaVA prompting because direct prose prompting produced weak descriptions.  
14. The old structured parser remains as fallback.  
15. Tests currently pass with 11 passing tests.  
16. Current known warning: missing `database_path`.  
17. Next priority is config normalization.  
18. Next major feature is sidecar metadata.  
19. Sidecar metadata should likely be JSON first, not embedded metadata.  
20. Development should remain incremental, reversible, and test-backed.

---

# **14\. Resume Prompt for a New AI Collaborator**

Resume the Image Classifier Desktop App project.

Current source of truth:

\- Local-only desktop image metadata/classification app.

\- Runtime: Windows, Python, run with \`python src/main.py\`.

\- AI: Ollama only, model \`llava:latest\`.

\- OpenAI has been removed and must not be reintroduced.

\- Metadata persists in local SQLite only for now.

\- Full metadata fields include filepath, description, tags, keywords, categories, ai\_raw, ai\_provider, ai\_model, ai\_timestamp.

\- Slot-first prompting is implemented in \`src/core/classifier.py\`.

\- Fallback old structured parser remains for CAPTION/DESCRIPTION/TAGS/KEYWORDS/CATEGORIES.

\- UI wiring is in \`src/ui/metadata\_panel.py\`.

\- Important UI attributes: \`self.tags\_entry\`, \`self.keywords\_entry\`, \`self.categories\_entry\`, \`self.classification\_text\`, \`self.exif\_text\`.

\- AI panel shows provider/model/timestamp plus raw output.

\- Technical Information panel shows file stats and EXIF.

\- Tests currently pass: 11 passed.

\- Known issue: startup warning \`Error loading config: 'database\_path'\`.

Workflow:

1\. Confirm app runs.

2\. Confirm Ollama has \`llava:latest\`.

3\. Confirm \`pytest\` passes.

4\. Fix only one work item at a time.

5\. Keep changes minimal and reversible.

6\. Update \`docs/CHANGELOG.md\`.

7\. Add config keys to both \`src/config/settings.json\` and \`config\_template.json\`.

8\. Do not use OpenAI.

Next recommended task:

Fix config normalization by adding \`database\_path\` to settings/template and making the loader handle missing keys gracefully.

---

# **15\. Recommended Project State Ledger**

| Claim | Status | Evidence |
| :---- | :---- | :---- |
| App is local-first | Confirmed | Uploaded status and handoff docs |
| OpenAI removed | Confirmed | Uploaded status and handoff docs |
| Ollama installed | Confirmed in status | Must recheck locally |
| `llava:latest` installed | Confirmed in status | Must recheck with `ollama list` |
| GUI loads folders | Confirmed | Status doc |
| Grid/list mode works | Confirmed | Status doc |
| Metadata panel works | Confirmed | Status doc |
| Classify button wired | Confirmed | Status doc |
| Slot-first prompt implemented | Confirmed | Status doc |
| Fallback parser retained | Confirmed | Status doc |
| AI panel raw output works | Confirmed | Status doc |
| Technical info panel works | Confirmed | Status doc |
| SQLite persistence works | Confirmed | Status doc |
| Tests pass | Confirmed as 11 passed | Re-run locally |
| Sidecar implemented | Not implemented | Planned |
| Embedded metadata implemented | Not implemented | Planned/future |
| Config warning exists | Confirmed | Fix next |

---

# **16\. Final Working Rules for Continuation**

1. Do not reintroduce OpenAI.  
2. Do not turn this into a cloud app.  
3. Do not migrate GUI frameworks until current app is stable.  
4. Do not write embedded metadata before sidecar metadata is proven.  
5. Do not overwrite user-edited metadata with AI output without explicit merge rules.  
6. Do not perform broad rewrites when a targeted patch will solve the issue.  
7. Always run `pytest` after code changes.  
8. Always update docs after successful changes.  
9. Prefer JSON sidecars before XMP.  
10. Treat SQLite as the current app state until sidecar merge rules are implemented.

Refinement checkpoint: Should the next export version include a proposed exact `src/core/sidecar.py` implementation and matching `tests/unit_sidecar.py` based on this architecture?  
