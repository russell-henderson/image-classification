"""
Manages the Electron sidecar process and bidirectional communication.
"""

import json
import logging
import os
import subprocess
import threading
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Callable
from core.database import DatabaseManager, ImageMetadata
from core.story_engine import StoryEngine

class SidecarManager:
    """Manages the life cycle and IPC of the Electron sidecar."""

    def __init__(self, db_manager: DatabaseManager, config: Dict[str, Any], event_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.db_manager = db_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.event_callback = event_callback
        self.process: Optional[subprocess.Popen] = None
        self.story_engine = StoryEngine(config)
        self.current_metadata: Optional[ImageMetadata] = None
        self.current_complexity = "Simple"
        self.is_chaos = False
        self.last_description = ""
        self.last_tags = ""
        self.bridge_dir = Path(__file__).parent.parent.parent / ".tmp" / "sidecar_bridge"
        self.python_to_sidecar_path = self.bridge_dir / "python_to_sidecar.jsonl"
        self.sidecar_to_python_path = self.bridge_dir / "sidecar_to_python.jsonl"
        self._bridge_read_offset = 0
        self._bridge_write_lock = threading.Lock()
        self._seen_incoming_ids: Set[str] = set()
        self._next_message_id = 1
        self.story_timeout_seconds = int(
            config.get("providers", {}).get("ollama", {}).get("story_timeout_seconds", 150)
        )
        self.story_retry_count = int(
            config.get("providers", {}).get("ollama", {}).get("story_retry_count", 1)
        )
        self.story_quick_mode_enabled = bool(
            config.get("providers", {}).get("ollama", {}).get("story_quick_mode_enabled", True)
        )

    def _emit_event(self, source: str, message: str, event_type: str = "status") -> None:
        """Publish sidecar activity to an optional UI callback."""
        if not self.event_callback or not message:
            return
        try:
            self.event_callback({"source": source, "message": message, "type": event_type})
        except Exception as exc:
            self.logger.debug("Sidecar event callback failed: %s", exc)

    def is_alive(self) -> bool:
        """Check if the sidecar process is still running."""
        return self.process is not None and self.process.poll() is None

    def launch(self, metadata: ImageMetadata, description: str, tags: str, complexity: str, is_chaos: bool):
        """Launch or refocus the sidecar window."""
        self.current_metadata = metadata
        self.current_complexity = complexity
        self.is_chaos = is_chaos
        self.last_description = description
        self.last_tags = tags
        
        if not self.is_alive():
            self._start_process()
        else:
            # If already alive, we can send immediately (refocus scenario)
            self._sync_data()

    def _sync_data(self):
        """Send initialization data and start hook generation."""
        if not self.last_description:
            self.logger.warning("No description available to sync to sidecar.")
            self.send_message({
                "type": "status",
                "stage": "error",
                "message": "No description is available yet. Run classification first or add a description.",
            })
            return

        self.send_message({
            "type": "status",
            "stage": "conn",
            "message": "Sidecar handshake complete. Syncing description and tags...",
        })
        self.send_message({
            "type": "init",
            "description": self.last_description,
            "tags": self.last_tags,
            "isChaos": self.is_chaos,
            "complexity": self.current_complexity
        })
        self.send_message({
            "type": "status",
            "stage": "work",
            "message": "Seed received. Preparing hook generation...",
        })

        # Automatically start hook generation
        threading.Thread(
            target=self._generate_hooks_async, 
            args=(self.last_description, self.last_tags), 
            daemon=True
        ).start()

    def _start_process(self):
        """Start the Electron process."""
        sidecar_path = Path(__file__).parent.parent / "sidecar"
        self._prepare_bridge_files()
        
        # Ensure dependencies are installed before trying to run npm start
        node_modules = sidecar_path / "node_modules"
        if not node_modules.exists():
            self.logger.info("Dependencies missing. Running 'npm install' in sidecar directory...")
            try:
                subprocess.run(
                    ["npm", "install"],
                    cwd=str(sidecar_path),
                    shell=True if sys.platform == "win32" else False,
                    check=True
                )
                self.logger.info("npm install completed successfully.")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to run npm install: {e}")

        try:
            launch_cmd = self._build_launch_command(sidecar_path)
            self.logger.info("Launching sidecar with command: %s", launch_cmd)
            child_env = dict(os.environ)
            child_env["IMAGE_CLASSIFIER_BRIDGE_DIR"] = str(self.bridge_dir)
            child_env["IMAGE_CLASSIFIER_PY_TO_SIDECAR"] = str(self.python_to_sidecar_path)
            child_env["IMAGE_CLASSIFIER_SIDECAR_TO_PY"] = str(self.sidecar_to_python_path)
            self.process = subprocess.Popen(
                launch_cmd,
                cwd=str(sidecar_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                shell=False,
                env=child_env,
            )
            
            # Start a thread to listen to sidecar's stdout
            threading.Thread(target=self._listen_to_sidecar, daemon=True).start()
            threading.Thread(target=self._listen_to_sidecar_stderr, daemon=True).start()
            threading.Thread(target=self._listen_to_sidecar_bridge_file, daemon=True).start()
            self.logger.info("Electron sidecar launched.")
        except Exception as e:
            self.logger.error(f"Failed to start Electron sidecar: {e}")
            raise

    def _prepare_bridge_files(self) -> None:
        """Create or reset the bridge files used for Windows-safe IPC fallback."""
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.python_to_sidecar_path.write_text("", encoding="utf-8")
        self.sidecar_to_python_path.write_text("", encoding="utf-8")
        self._bridge_read_offset = 0
        self._seen_incoming_ids.clear()
        self.logger.info(
            "Sidecar bridge prepared: python_to_sidecar=%s sidecar_to_python=%s",
            self.python_to_sidecar_path,
            self.sidecar_to_python_path,
        )

    def _build_launch_command(self, sidecar_path: Path) -> List[str]:
        """Resolve the most direct Electron launch command for this platform."""
        if sys.platform == "win32":
            electron_exe = sidecar_path / "node_modules" / "electron" / "dist" / "electron.exe"
            if electron_exe.exists():
                return [str(electron_exe), "."]

            electron_cmd = sidecar_path / "node_modules" / ".bin" / "electron.cmd"
            if electron_cmd.exists():
                return [str(electron_cmd), "."]

        electron_bin = sidecar_path / "node_modules" / ".bin" / "electron"
        if electron_bin.exists():
            return [str(electron_bin), "."]

        return ["npm", "start"]

    def send_message(self, message: Dict[str, Any]):
        """Send a JSON message to the sidecar's stdin."""
        outbound = dict(message)
        outbound.setdefault("_bridge_id", self._new_bridge_id("py"))
        payload = json.dumps(outbound)
        self.logger.info(
            "Sidecar outbound message: id=%s type=%s via=stdio+file",
            outbound.get("_bridge_id"),
            outbound.get("type"),
        )
        if outbound.get("type") == "status":
            self._emit_event("dolphin3:8b", outbound.get("message", ""), "status")

        if self.is_alive() and self.process.stdin:
            try:
                self.process.stdin.write(payload + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self.logger.error(f"Error sending message to sidecar: {e}")

        try:
            with self._bridge_write_lock:
                with self.python_to_sidecar_path.open("a", encoding="utf-8") as handle:
                    handle.write(payload + "\n")
        except Exception as e:
            self.logger.error(f"Error writing bridge message to sidecar file: {e}")

    def _new_bridge_id(self, prefix: str) -> str:
        bridge_id = f"{prefix}-{self._next_message_id}"
        self._next_message_id += 1
        return bridge_id

    def _listen_to_sidecar(self):
        """Threaded listener for messages from the sidecar's stdout."""
        if not self.process or not self.process.stdout:
            return

        while self.is_alive():
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line.strip())
                self.logger.info(
                    "Sidecar inbound stdout message: id=%s type=%s",
                    message.get("_bridge_id"),
                    message.get("type"),
                )
                self._dispatch_sidecar_message(message)
            except Exception as e:
                self.logger.debug("Sidecar stdout (non-JSON): %s", line.strip())

    def _listen_to_sidecar_bridge_file(self):
        """Poll the sidecar-to-python file so IPC still works when stdio does not."""
        while self.is_alive():
            try:
                if self.sidecar_to_python_path.exists():
                    with self.sidecar_to_python_path.open("r", encoding="utf-8") as handle:
                        handle.seek(self._bridge_read_offset)
                        while True:
                            line = handle.readline()
                            if not line:
                                break
                            self._bridge_read_offset = handle.tell()
                            trimmed = line.strip()
                            if not trimmed:
                                continue
                            try:
                                message = json.loads(trimmed)
                                self.logger.info(
                                    "Sidecar inbound file message: id=%s type=%s",
                                    message.get("_bridge_id"),
                                    message.get("type"),
                                )
                                self._dispatch_sidecar_message(message)
                            except Exception:
                                self.logger.debug("Bridge file line was not valid JSON: %s", trimmed)
                time.sleep(0.2)
            except Exception as e:
                self.logger.warning("Bridge file listener error: %s", e)
                time.sleep(0.5)

    def _listen_to_sidecar_stderr(self):
        """Threaded listener for sidecar stderr so startup failures are visible."""
        if not self.process or not self.process.stderr:
            return

        while self.is_alive():
            line = self.process.stderr.readline()
            if not line:
                break
            self.logger.warning("Sidecar stderr: %s", line.strip())

    def _dispatch_sidecar_message(self, message: Dict[str, Any]) -> None:
        """Deduplicate messages that may arrive from both stdout and the bridge file."""
        bridge_id = message.get("_bridge_id")
        if bridge_id:
            if bridge_id in self._seen_incoming_ids:
                self.logger.info(
                    "Sidecar inbound duplicate ignored: id=%s type=%s",
                    bridge_id,
                    message.get("type"),
                )
                return
            self._seen_incoming_ids.add(bridge_id)
        self.logger.info(
            "Sidecar inbound dispatch: id=%s type=%s",
            bridge_id,
            message.get("type"),
        )
        inbound_type = message.get("type", "")
        inbound_summary = message.get("message") or message.get("hook") or inbound_type
        self._emit_event("electron", str(inbound_summary), inbound_type or "ipc")
        self._handle_sidecar_message(message)

    def _handle_sidecar_message(self, message: Dict[str, Any]):
        """Process messages received from the sidecar UI."""
        m_type = message.get("type")
        if m_type == "ready":
            self.logger.info("Sidecar signaled ready. Syncing initial data.")
            self._sync_data()
        elif m_type == "select_hook":
            hook = message.get("hook")
            if hook:
                threading.Thread(
                    target=self._generate_story_async,
                    args=(hook, False),
                    daemon=True,
                ).start()
        elif m_type == "finalize_story":
            custom_input = (message.get("custom_input") or "").strip()
            if custom_input:
                threading.Thread(
                    target=self._generate_story_async,
                    args=(custom_input, True),
                    daemon=True,
                ).start()
        elif m_type == "ping_python":
            self.send_message({
                "type": "pong_python",
                "message": "Python bridge is connected.",
                "hasDescription": bool((self.last_description or "").strip()),
                "hasTags": bool((self.last_tags or "").strip()),
                "complexity": self.current_complexity,
                "isChaos": self.is_chaos,
            })
        elif m_type == "check_model":
            self.send_message({
                "type": "status",
                "stage": "conn",
                "message": "Checking Ollama for dolphin3:8b availability...",
            })
            is_ready = self.story_engine.check_model_ready()
            if is_ready:
                self.send_message({
                    "type": "model_status",
                    "ready": True,
                    "message": "dolphin3:8b is available in Ollama.",
                    "model": self.story_engine.model,
                })
                self.send_message({
                    "type": "status",
                    "stage": "done",
                    "message": "Model check passed.",
                })
            else:
                self.send_message({
                    "type": "model_status",
                    "ready": False,
                    "message": "dolphin3:8b was not found or Ollama is unreachable.",
                    "model": self.story_engine.model,
                })
                self.send_message({
                    "type": "status",
                    "stage": "error",
                    "message": "Model check failed.",
                })

    def _generate_hooks_async(self, description: str, tags: str):
        """Background task to generate story hooks."""
        self.send_message({"type": "status", "stage": "conn", "message": "Connecting to dolphin3:8b..."})
        
        if not self.story_engine.check_model_ready():
            self.send_message({"type": "status", "stage": "error", "message": "dolphin3:8b not found in Ollama!"})
            return

        self.send_message({"type": "status", "stage": "work", "message": "Model check passed. Building four story directions..."})
        self.send_message({"type": "status", "stage": "work", "message": "Generating 4 hooks..."})
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        hooks = self.story_engine.generate_hooks(description, tags_list, self.current_complexity, self.is_chaos)
        
        if hooks:
            self.send_message({"type": "status", "stage": "done", "message": f"Generated {len(hooks)} hooks. Select one or use Option 4."})
            self.send_message({"type": "hooks", "hooks": hooks})
        else:
            self.send_message({"type": "status", "stage": "error", "message": "Generation failed."})

    def _generate_story_async(self, hook: str, is_custom: bool = False):
        """Background task to generate the full story."""
        self.send_message({"type": "status", "stage": "conn", "message": "Connecting to dolphin3:8b..."})
        self.send_message({"type": "status", "stage": "work", "message": "Writing narrative..."})
        max_attempts = max(1, self.story_retry_count + 1)
        story = ""
        final_error = ""

        for attempt in range(1, max_attempts + 1):
            use_quick_mode = self.story_quick_mode_enabled and attempt > 1
            if attempt > 1:
                retry_message = (
                    f"Story attempt {attempt} of {max_attempts}. "
                    f"{'Using quick mode for a faster retry.' if use_quick_mode else 'Retrying generation.'}"
                )
                self.send_message({"type": "status", "stage": "work", "message": retry_message})

            result_holder: Dict[str, Any] = {}
            error_holder: Dict[str, str] = {}

            def _worker() -> None:
                try:
                    result_holder["story"] = self.story_engine.generate_narrative(
                        hook,
                        self.current_complexity,
                        self.is_chaos,
                        quick_mode=use_quick_mode,
                    )
                except Exception as e:
                    error_holder["error"] = str(e)

            worker = threading.Thread(target=_worker, daemon=True)
            worker.start()
            worker.join(timeout=self.story_timeout_seconds)

            if worker.is_alive():
                final_error = (
                    f"Narrative generation exceeded {self.story_timeout_seconds}s "
                    f"on attempt {attempt} of {max_attempts}."
                )
                self.logger.error("Story generation timeout: attempt=%s hook=%s", attempt, hook[:120])
                if attempt < max_attempts:
                    continue
                break

            if error_holder.get("error"):
                final_error = f"Narrative generation failed: {error_holder['error']}"
                self.logger.error(final_error)
                if attempt < max_attempts:
                    continue
                break

            story = (result_holder.get("story") or "").strip()
            if not story or story.startswith("Error:"):
                final_error = story or "Narrative generation returned no text."
                self.logger.error("Story generation returned an error payload: %s", final_error)
                if attempt < max_attempts:
                    continue
                break

            break

        if not story:
            message = final_error or "Narrative generation failed."
            self.send_message({"type": "status", "stage": "error", "message": message})
            self.send_message({"type": "narrative_error", "message": message})
            return
        
        # Save to database
        if self.current_metadata:
            mode_prefix = "Custom" if is_custom else ("Chaos" if self.is_chaos else "Adventure")
            mode_str = f"{mode_prefix}/{self.current_complexity}"
            self.db_manager.save_story(self.current_metadata.file_path, hook, story, mode_str)
        
        self.send_message({"type": "status", "stage": "done", "message": "Narrative complete."})
        self.send_message({"type": "narrative", "story": story})
