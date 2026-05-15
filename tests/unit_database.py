import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from core.database import DatabaseManager  # noqa: E402
from core.image_handler import ImageHandler  # noqa: E402


def _create_test_image(path: Path, size=(50, 40), color=(10, 20, 30)) -> Path:
    image = Image.new("RGB", size, color)
    image.save(path, format="PNG")
    return path


def test_add_and_get_image(tmp_path):
    db_path = tmp_path / "images.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    image_path = _create_test_image(tmp_path / "db.png")
    metadata = handler.create_metadata(str(image_path))

    assert metadata is not None
    metadata.tags = ["sample"]
    metadata.keywords = ["keyword"]
    metadata.categories = ["test"]
    metadata.rating = 3
    metadata.description = "A test image"

    assert db.add_image(metadata) is True

    stored = db.get_image(metadata.file_path)
    assert stored is not None
    assert stored.filename == "db.png"
    assert stored.rating == 3
    assert stored.tags == ["sample"]


def test_update_metadata(tmp_path):
    db_path = tmp_path / "images.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    image_path = _create_test_image(tmp_path / "update.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None

    db.add_image(metadata)

    assert db.update_metadata(
        metadata.file_path,
        description="Updated",
        tags=["a", "b"],
        keywords=["k1"],
        categories=["cat"],
        rating=5,
    )

    stored = db.get_image(metadata.file_path)
    assert stored is not None
    assert stored.description == "Updated"
    assert stored.tags == ["a", "b"]
    assert stored.keywords == ["k1"]
    assert stored.categories == ["cat"]
    assert stored.rating == 5


def test_statistics(tmp_path):
    db_path = tmp_path / "images.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    image_path = _create_test_image(tmp_path / "stats.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    db.add_image(metadata)

    stats = db.get_statistics()
    assert stats.get("total_images") == 1


def test_save_and_get_stories(tmp_path):
    db_path = tmp_path / "stories.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    image_path = _create_test_image(tmp_path / "story.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    assert db.add_image(metadata) is True

    assert db.save_story(metadata.file_path, "Hook A", "Story body", "Chaos/Complex") is True

    stories = db.get_stories(metadata.file_path)
    assert len(stories) == 1
    assert stories[0]["selected_hook"] == "Hook A"
    assert stories[0]["full_story"] == "Story body"
    assert stories[0]["mode"] == "Chaos/Complex"


def test_update_image_path_updates_images_and_stories(tmp_path):
    db_path = tmp_path / "paths.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    image_path = _create_test_image(tmp_path / "before.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    assert db.add_image(metadata) is True
    assert db.save_story(metadata.file_path, "Hook", "Story", "Simple") is True

    renamed_path = str(tmp_path / "after.png")
    assert db.update_image_path(metadata.file_path, renamed_path) is True

    assert db.get_image(metadata.file_path) is None
    moved_metadata = db.get_image(renamed_path)
    assert moved_metadata is not None
    assert moved_metadata.filename == "after.png"

    stories = db.get_stories(renamed_path)
    assert len(stories) == 1
    assert stories[0]["image_file_path"] == renamed_path


def test_remove_missing_files_cleans_database(tmp_path):
    db_path = tmp_path / "missing.db"
    handler = ImageHandler()
    db = DatabaseManager(str(db_path))

    existing_path = _create_test_image(tmp_path / "keep.png")
    missing_path = _create_test_image(tmp_path / "gone.png")

    existing_metadata = handler.create_metadata(str(existing_path))
    missing_metadata = handler.create_metadata(str(missing_path))
    assert existing_metadata is not None
    assert missing_metadata is not None
    assert db.add_image(existing_metadata) is True
    assert db.add_image(missing_metadata) is True

    missing_path.unlink()

    removed_paths = db.remove_missing_files()
    assert removed_paths == [str(missing_path)]
    assert db.get_image(str(missing_path)) is None
    assert db.get_image(str(existing_path)) is not None
