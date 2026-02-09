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
