import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from core.story_engine import StoryEngine  # noqa: E402


def _make_story_engine():
    config = {
        "providers": {
            "ollama": {
                "base_url": "http://localhost:11434",
            }
        }
    }
    return StoryEngine(config)


def test_generate_hooks_uses_chaos_sampling(monkeypatch):
    engine = _make_story_engine()
    captured = {}

    def _fake_call(prompt, options=None):
        captured["prompt"] = prompt
        captured["options"] = options
        return '["One", "Two", "Three", "Four"]'

    monkeypatch.setattr(engine, "_call_ollama", _fake_call)

    hooks = engine.generate_hooks("desc", ["tag1", "tag2"], "Complex", True)

    assert hooks == ["One", "Two", "Three", "Four"]
    assert captured["options"] == {"temperature": 1.2, "top_p": 0.95}
    assert "CHAOS MODE ENABLED" in captured["prompt"]


def test_generate_narrative_uses_complexity_limit(monkeypatch):
    engine = _make_story_engine()
    captured = {}

    def _fake_call(prompt, options=None):
        captured["prompt"] = prompt
        captured["options"] = options
        return "Story text"

    monkeypatch.setattr(engine, "_call_ollama", _fake_call)

    story = engine.generate_narrative("Hook text", "Simple", False)

    assert story == "Story text"
    assert "exactly 1 paragraph(s) max" in captured["prompt"]
    assert captured["options"] == {}


def test_generate_narrative_quick_mode_changes_prompt(monkeypatch):
    engine = _make_story_engine()
    captured = {}

    def _fake_call(prompt, options=None):
        captured["prompt"] = prompt
        return "Quick story"

    monkeypatch.setattr(engine, "_call_ollama", _fake_call)

    story = engine.generate_narrative("Hook text", "Complex", False, quick_mode=True)

    assert story == "Quick story"
    assert "Keep the prose concise, concrete, and fast to generate." in captured["prompt"]
