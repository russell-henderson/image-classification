# Story Engine & Electron Sidecar Handoff

## Project Overview
Implemented a "Creative Story Studio" feature for the Image Classification Desktop App. This feature leverages Ollama's `dolphin3:8b` model to generate narrative hooks and full stories based on image metadata (LLaVA descriptions and tags).

## Implementation Summary

### 1. Core Logic & AI Integration
*   **Story Engine (`src/core/story_engine.py`)**: A new module that interfaces with Ollama. It handles two-stage generation:
    *   **Hook Generation**: Produces 4 distinct story directions.
    *   **Narrative Generation**: Produces the final story (1-2 paragraphs).
    *   **Chaos/Spicy Mode**: Implements specific sampling parameters (`temperature=1.2`, `top_p=0.95`) for "not normal" creative outputs.
*   **System Prompt (`src/core/CREATIVE.md`)**: A dedicated markdown file containing the "Creative Assistant" identity and constraints.

### 2. Electron Sidecar
*   **Scaffolded App (`src/sidecar/`)**: A persistent sidecar window built with Electron.
*   **Director Workflow**:
    *   **Area A & B**: Auto-populated with description and tags.
    *   **Interactive UI**: Allows selection of hooks or manual entry via **Option 4**.
    *   **Manual Finalize Flow**: Option 4 now sends a distinct `finalize_story` message instead of reusing the normal hook-selection event.
    *   **Status Indicators**: Implemented 3-stage LED feedback (Connected, Working, Done) and the required DOM elements now exist in `index.html`.
*   **IPC Bridge (`src/core/sidecar_manager.py`)**: Manages the life cycle of the Electron subprocess.
    *   Uses a **Handshake Protocol**: Python waits for the sidecar's `ready` signal before syncing data to ensure no messages are lost during startup.
    *   Handles bidirectional JSON messaging via `stdin`/`stdout`.
    *   The Electron stdin reader is now line-buffered so partial chunks do not break JSON parsing.

### 3. Database & Schema
*   **Update (`src/core/database.py`)**:
    *   New table `image_stories` with foreign key relationship to `images`.
    *   Fields: `image_file_path`, `selected_hook`, `full_story`, `mode`.
    *   Implemented `save_story` and `get_stories` methods.

### 4. UI Refinements (`src/ui/metadata_panel.py`)
*   **Create Button**: Added next to "Clear Classification".
*   **Dynamic Preview**: Re-engineered the image preview to use dynamic scaling (max-height ~40% of panel) with right-side padding to prevent scrollbar overlap.
*   **LED Feedback**: Optimized threading to ensure the first LED ("Command received") lights up instantly upon button click by forcing a UI update before the background thread starts.

## Technical Challenges & Solutions
*   **Subprocess Warnings**: Encountered `RuntimeWarning` regarding line buffering in binary mode. **Fixed** by setting `text=True` in `subprocess.Popen`.
*   **Missing Dependencies**: The sidecar failed to launch because `node_modules` were missing. **Fixed** by adding an automatic `npm install` check in the `SidecarManager`.
*   **Message Race Conditions**: Initial data was often sent before the Electron window was ready. **Fixed** by implementing a `ready` event handshake.

## Success Definition (Verification)
1.  **Launch**: Clicking "Create" in the main panel opens a persistent Electron window.
2.  **Sync**: The sidecar's text areas should automatically fill with the current image's description and tags.
3.  **Visuals**: The status LEDs in the sidecar should cycle (Blue -> Yellow -> Green) as hooks are generated.
4.  **Interaction**: Selecting a hook (or typing a custom one in Option 4 and hitting 'Finish') should produce a 1-2 paragraph story in the final narrative box.
5.  **Persistence**: The generated story and hook are successfully written to the `image_stories` table in `image_metadata.db`.

## Dependencies
*   Ollama (must be running)
*   `dolphin3:8b` model (`ollama pull dolphin3:8b`)
*   Node.js & npm (for Electron)
