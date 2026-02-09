import sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from core.classifier import ClassificationEngine  # noqa: E402
from core.database import DatabaseManager, ImageMetadata  # noqa: E402
from core.image_handler import ImageHandler  # noqa: E402


def _create_test_image(path: Path, size=(120, 80), color=(20, 40, 60)) -> Path:
    image = Image.new("RGB", size, color)
    image.save(path, format="PNG")
    return path


def _make_engine(tmp_path, **config_overrides):
    config = {
        "providers": {
            "ollama": {
                "enabled": True,
                "base_url": "http://localhost:11434",
                "model": "llava:latest",
                "timeout_seconds": 120,
            },
        },
        "classification": {
            "primary_provider": "ollama",
        },
        "thumbnail_size": 64,
        "max_image_size": 256,
        "cache_duration": 86400,
        "rate_limit_delay": 0.0,
    }
    if "providers" in config_overrides:
        merged_providers = dict(config["providers"])
        merged_providers.update(config_overrides["providers"])
        config_overrides = dict(config_overrides)
        config_overrides["providers"] = merged_providers
    config.update(config_overrides)
    db = DatabaseManager(str(tmp_path / "images.db"))
    return ClassificationEngine(config, db), db


def test_encode_image_for_api(tmp_path):
    engine, _db = _make_engine(tmp_path)
    image_path = _create_test_image(tmp_path / "encode.png")

    encoded = engine._encode_image_for_api(str(image_path))

    assert encoded is not None
    assert isinstance(encoded, str)
    assert len(encoded) > 0


def test_classify_image_local_returns_fields(tmp_path):
    engine, _db = _make_engine(tmp_path)
    image_path = _create_test_image(tmp_path / "local.png", size=(90, 60))

    result = engine.classify_image_local(str(image_path))

    assert "error" not in result
    assert result["api_used"] == "local"
    assert result["model"] == "heuristic"
    assert "description" in result
    assert "scene" in result
    assert "mood" in result
    assert "quality" in result


import pytest


@pytest.mark.asyncio
async def test_classify_image_ollama_disabled(tmp_path):
    engine, _db = _make_engine(
        tmp_path,
        providers={
            "ollama": {"enabled": False},
        },
    )
    image_path = _create_test_image(tmp_path / "ollama_disabled.png")

    result = await engine.classify_image_ollama(str(image_path))
    assert "error" in result
    assert result["error"] == "Ollama provider is disabled in settings.json"


@pytest.mark.asyncio
async def test_process_image_ollama_slots(tmp_path, monkeypatch):
    engine, _db = _make_engine(tmp_path)
    image_path = _create_test_image(tmp_path / "ollama_mock.png")

    def _fake_describe(**_kwargs):
        return "\n".join(
            [
                "SUBJECT: A cozy cat on a chair",
                "SETTING: A quiet indoor room with warm decor",
                "COLORS: brown, gold, cream",
                "LIGHTING: warm ambient light",
                "MOOD: calm and inviting",
                "STYLE: gentle intimate style",
                "TAGS: cat, chair, room, interior",
            ]
        )

    monkeypatch.setattr(
        "core.classifier.ollama_llava_describe_image",
        _fake_describe,
    )

    metadata = await engine.process_image(str(image_path), force_refresh=True)

    assert metadata is not None
    assert metadata.description.startswith("Subject: A cozy cat on a chair.")
    assert metadata.tags == ["cat", "chair", "room", "interior"]
    assert "brown" in metadata.keywords
    assert "warm ambient light" in metadata.keywords
    assert metadata.categories


def test_cache_validation(tmp_path):
    engine, _db = _make_engine(tmp_path, cache_duration=86400)

    recent = ImageMetadata(
        file_path="x",
        filename="x.png",
        file_size=1,
        width=1,
        height=1,
        format="PNG",
        created_date=datetime.now(),
        modified_date=datetime.now(),
        exif_data={},
        tags=[],
        categories=[],
        keywords=[],
        rating=0,
        description="",
        classification="{}",
        embedding=None,
        api_cached=True,
        cache_date=datetime.now() - timedelta(hours=1),
    )
    stale = ImageMetadata(
        file_path="y",
        filename="y.png",
        file_size=1,
        width=1,
        height=1,
        format="PNG",
        created_date=datetime.now(),
        modified_date=datetime.now(),
        exif_data={},
        tags=[],
        categories=[],
        keywords=[],
        rating=0,
        description="",
        classification="{}",
        embedding=None,
        api_cached=True,
        cache_date=datetime.now() - timedelta(days=2),
    )

    assert engine._is_cache_valid(recent) is True
    assert engine._is_cache_valid(stale) is False
