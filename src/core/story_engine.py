"""
Story Engine for generating narratives based on image metadata using Ollama dolphin3:8b.
"""

import json
import logging
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


class StoryEngine:
    """Manages story generation logic using Ollama."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.ollama_config = config.get("providers", {}).get("ollama", {})
        self.base_url = self.ollama_config.get(
            "base_url", "http://localhost:11434")
        self.model = "dolphin3:8b"  # Explicitly using dolphin3:8b as requested
        self.request_timeout_seconds = int(
            self.ollama_config.get("story_timeout_seconds", 120)
        )
        self.quick_mode_enabled = bool(
            self.ollama_config.get("story_quick_mode_enabled", True)
        )

        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load the creative system prompt from CREATIVE.md."""
        prompt_path = Path(__file__).parent / "CREATIVE.md"
        try:
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        except Exception as e:
            self.logger.error(f"Error loading system prompt: {e}")

        return "You are a creative story assistant."

    def check_model_ready(self) -> bool:
        """Preflight check to ensure dolphin3:8b is available in Ollama."""
        try:
            url = f"{self.base_url.rstrip('/')}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                # Check for both "dolphin3:8b" and "dolphin3"
                return any(self.model in name for name in models)
        except Exception as e:
            self.logger.error(f"Ollama preflight check failed: {e}")
            return False

    def generate_hooks(self, description: str, tags: List[str], complexity: str, is_chaos: bool) -> List[str]:
        """Generate 4 distinct story hooks."""
        chaos_text = " (CHAOS MODE ENABLED: Be surreal and unconventional)" if is_chaos else ""
        prompt = (
            f"Image Description: {description}\n"
            f"Tags: {', '.join(tags)}\n"
            f"Complexity: {complexity}{chaos_text}\n\n"
            "Generate 4 distinct story hooks (directions) for this image. "
            "Output them as a JSON list of strings."
        )

        options = {}
        if is_chaos:
            options = {
                "temperature": 1.2,
                "top_p": 0.95
            }

        response = self._call_ollama(prompt, options)
        try:
            # Attempt to find JSON list in response
            import re
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                hooks = json.loads(match.group(0))
                if isinstance(hooks, list):
                    return hooks[:4]
        except Exception as e:
            self.logger.warning(
                f"Failed to parse hooks JSON: {e}. Raw response: {response}")

        # Fallback split by lines if JSON fails
        lines = [l.strip().lstrip('1234. -')
                 for l in response.splitlines() if l.strip()]
        return lines[:4]

    def generate_narrative(self, hook: str, complexity: str, is_chaos: bool, quick_mode: bool = False) -> str:
        """Generate a full story based on a selected hook."""
        max_paragraphs = 1 if complexity == "Simple" else 2
        chaos_text = " (CHAOS MODE ENABLED: Be surreal and unconventional)" if is_chaos else ""

        if quick_mode:
            prompt = (
                f"Selected Hook: {hook}\n"
                f"Constraint: Write exactly {max_paragraphs} paragraph(s) max.{chaos_text}\n"
                "Keep the prose concise, concrete, and fast to generate.\n\n"
                "Write the full story now."
            )
        else:
            prompt = (
                f"Selected Hook: {hook}\n"
                f"Constraint: Write exactly {max_paragraphs} paragraph(s) max.{chaos_text}\n\n"
                "Write the full story now."
            )

        options = {}
        if is_chaos:
            options = {
                "temperature": 1.2,
                "top_p": 0.95
            }

        return self._call_ollama(prompt, options)

    def _call_ollama(self, prompt: str, options: Dict[str, Any] = None) -> str:
        """Internal helper to call Ollama API."""
        payload = {
            "model": self.model,
            "system": self.system_prompt,
            "prompt": prompt,
            "stream": False,
        }
        if options:
            payload["options"] = options

        try:
            started = time.time()
            self.logger.info(
                "StoryEngine Ollama request started: model=%s timeout=%ss prompt_chars=%s",
                self.model,
                self.request_timeout_seconds,
                len(prompt),
            )
            req = urllib.request.Request(
                url=f"{self.base_url.rstrip('/')}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.request_timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - started
                self.logger.info(
                    "StoryEngine Ollama request completed: model=%s elapsed=%.2fs",
                    self.model,
                    elapsed,
                )
                return (data.get("response") or "").strip()
        except Exception as e:
            self.logger.error(f"Ollama story generation error: {e}")
            return f"Error: {e}"
