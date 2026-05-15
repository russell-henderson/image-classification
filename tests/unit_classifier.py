import sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from core.classifier import ClassificationEngine, description_needs_repair  # noqa: E402
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


def test_description_needs_repair_for_speculative_language():
    assert description_needs_repair(
        "A woman stands near a bed and looks ready to begin a photoshoot."
    ) is True
    assert description_needs_repair(
        "A woman stands near a bed in a room with beige walls and red accents."
    ) is True


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
    calls = {"count": 0}

    def _fake_describe(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
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
        return (
            "A cozy cat rests on a chair in a quiet indoor room, surrounded by warm decor "
            "and soft household details that make the space feel intimate and lived in. "
            "Brown, gold, and cream tones dominate the scene while warm ambient light "
            "settles gently across the furniture and the cat's fur. The overall mood is "
            "calm and inviting, with a soft, intimate style that feels like a candid "
            "moment captured inside a peaceful home."
        )

    monkeypatch.setattr(
        "core.classifier.ollama_llava_describe_image",
        _fake_describe,
    )

    metadata = await engine.process_image(str(image_path), force_refresh=True)

    assert metadata is not None
    assert metadata.description.startswith("A cozy cat rests on a chair")
    assert metadata.tags[:4] == ["cat", "chair", "room", "interior"]
    assert "cozy" in metadata.tags
    assert "brown" in metadata.keywords
    assert "warm ambient light" in metadata.keywords
    assert metadata.categories
    assert metadata.api_cached is True
    assert metadata.cache_date is not None
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_process_image_partial_ollama_backfills_missing_fields(tmp_path, monkeypatch):
    engine, _db = _make_engine(tmp_path)
    image_path = _create_test_image(tmp_path / "partial_slots.png")
    calls = {"count": 0}

    def _fake_describe(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "\n".join(
                [
                    "SUBJECT: A document on a desk",
                    "SETTING: ",
                    "COLORS: white, gray",
                    "LIGHTING: overhead office light",
                    "MOOD: neutral",
                    "STYLE: ",
                    "TAGS: document",
                ]
            )
        return (
            "A paper document lies flat on a desk surface under bright overhead office light, "
            "with white and gray tones defining most of the scene. The composition feels plain "
            "and practical, suggesting a work or administrative environment rather than a stylized "
            "photograph. The mood is neutral and functional, with the focus staying on the document "
            "itself and the uncluttered workspace around it."
        )

    def _fake_local(_path):
        return {
            "description": "A standard/square image with medium quality and neutral lighting",
            "subjects": "unknown",
            "scene": "standard/square",
            "colors": "",
            "mood": "neutral",
            "quality": "medium",
            "api_used": "local",
            "model": "heuristic",
            "timestamp": datetime.now().isoformat(),
            "statistics": {},
        }

    monkeypatch.setattr(
        "core.classifier.ollama_llava_describe_image",
        _fake_describe,
    )
    monkeypatch.setattr(engine, "classify_image_local", _fake_local)

    metadata = await engine.process_image(str(image_path), force_refresh=True)

    assert metadata is not None
    assert metadata.description
    assert metadata.tags
    assert metadata.keywords
    assert metadata.categories
    assert metadata.ai_provider == "ollama"
    assert metadata.api_cached is True
    assert metadata.cache_date is not None
    assert metadata.description.startswith("A paper document lies flat on a desk surface")
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_process_image_legacy_ollama_backfills_missing_fields(tmp_path, monkeypatch):
    engine, _db = _make_engine(tmp_path)
    image_path = _create_test_image(tmp_path / "partial_legacy.png")
    calls = {"count": 0}

    def _fake_describe(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return "SUBJECT: receipt\nSETTING:\nCOLORS: white\nLIGHTING:\nMOOD:\nSTYLE:\nTAGS:"
        if calls["count"] == 2:
            return "\n".join(
                [
                    "CAPTION: receipt on a tabletop",
                    "DESCRIPTION: ",
                    "TAGS: receipt, paper",
                    "KEYWORDS: tabletop, indoor",
                    "CATEGORIES: ",
                ]
            )
        return (
            "A small receipt sits on a tabletop in a simple indoor setting, with pale paper tones "
            "standing out against the flatter surface beneath it. The scene is visually minimal and "
            "utilitarian, likely photographed to capture or review the document rather than for artistic "
            "effect. The lighting appears even and neutral, giving the image a straightforward, matter-of-fact atmosphere."
        )

    def _fake_local(_path):
        return {
            "description": "A standard/square image with low/blurry quality and neutral lighting",
            "subjects": "unknown",
            "scene": "standard/square",
            "colors": "",
            "mood": "neutral",
            "quality": "low/blurry",
            "api_used": "local",
            "model": "heuristic",
            "timestamp": datetime.now().isoformat(),
            "statistics": {},
        }

    monkeypatch.setattr(
        "core.classifier.ollama_llava_describe_image",
        _fake_describe,
    )
    monkeypatch.setattr(engine, "classify_image_local", _fake_local)

    metadata = await engine.process_image(str(image_path), force_refresh=True)

    assert metadata is not None
    assert metadata.description
    assert metadata.tags
    assert metadata.keywords
    assert metadata.categories
    assert metadata.ai_provider == "ollama"
    assert metadata.api_cached is True
    assert metadata.description.startswith("A small receipt sits on a tabletop")
    assert calls["count"] == 3


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


@pytest.mark.asyncio
async def test_batch_process_skips_already_classified_images(tmp_path, monkeypatch):
    engine, db = _make_engine(tmp_path)
    first_path = _create_test_image(tmp_path / "already_done.png")
    second_path = _create_test_image(tmp_path / "needs_work.png")

    handler = ImageHandler()
    existing = handler.create_metadata(str(first_path))
    assert existing is not None
    existing.description = "Already classified description"
    existing.tags = ["done"]
    existing.classification = '{"api_used":"ollama"}'
    existing.api_cached = True
    existing.cache_date = datetime.now()
    assert db.add_image(existing) is True

    calls = []

    async def _fake_process(image_path, force_refresh=False, status_callback=None):
        calls.append((image_path, force_refresh))
        metadata = handler.create_metadata(image_path)
        assert metadata is not None
        metadata.description = "Processed now"
        metadata.classification = '{"api_used":"ollama"}'
        metadata.api_cached = True
        metadata.cache_date = datetime.now()
        return metadata

    monkeypatch.setattr(engine, "process_image", _fake_process)

    results = await engine.batch_process_images(
        [str(first_path), str(second_path)],
        force_refresh=False,
        skip_existing=True,
    )

    assert len(results) == 1
    assert results[0].file_path == str(second_path)
    assert calls == [(str(second_path), False)]
