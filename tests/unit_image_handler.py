import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from core.database import DatabaseManager  # noqa: E402
from core.image_handler import FileOperator, ImageHandler  # noqa: E402


def _create_test_image(path: Path, size=(64, 48), color=(120, 200, 80)) -> Path:
    image = Image.new("RGB", size, color)
    image.save(path, format="PNG")
    return path


def test_is_supported_image(tmp_path):
    handler = ImageHandler()
    image_path = _create_test_image(tmp_path / "sample.png")

    assert handler.is_supported_image(str(image_path)) is True
    assert handler.is_supported_image(str(tmp_path / "notes.txt")) is False


def test_create_metadata(tmp_path):
    handler = ImageHandler()
    image_path = _create_test_image(tmp_path / "meta.png", size=(80, 60))

    metadata = handler.create_metadata(str(image_path))

    assert metadata is not None
    assert metadata.filename == "meta.png"
    assert metadata.width == 80
    assert metadata.height == 60
    assert metadata.format.lower() in {"png", "unknown"}
    assert isinstance(metadata.exif_data, dict)


def test_create_thumbnail(tmp_path):
    handler = ImageHandler(thumbnail_size=32)
    image_path = _create_test_image(tmp_path / "thumb.png", size=(120, 90))

    thumbnail = handler.create_thumbnail(str(image_path))

    assert thumbnail is not None
    assert thumbnail.size[0] <= 32
    assert thumbnail.size[1] <= 32


def test_file_operator_rename_updates_database(tmp_path):
    db = DatabaseManager(str(tmp_path / "rename.db"))
    handler = ImageHandler()
    file_operator = FileOperator(db)

    image_path = _create_test_image(tmp_path / "rename-me.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    assert db.add_image(metadata) is True

    renamed_path = file_operator.rename_image(str(image_path), "renamed.png")

    assert Path(renamed_path).exists()
    assert db.get_image(str(image_path)) is None
    stored = db.get_image(renamed_path)
    assert stored is not None
    assert stored.filename == "renamed.png"


def test_file_operator_move_updates_database(tmp_path):
    db = DatabaseManager(str(tmp_path / "move.db"))
    handler = ImageHandler()
    file_operator = FileOperator(db)

    image_path = _create_test_image(tmp_path / "move-me.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    assert db.add_image(metadata) is True

    destination = tmp_path / "dest"
    destination.mkdir()
    moved_path = file_operator.move_image(str(image_path), str(destination))

    assert Path(moved_path).exists()
    assert db.get_image(str(image_path)) is None
    stored = db.get_image(moved_path)
    assert stored is not None
    assert stored.file_path == moved_path


def test_file_operator_delete_removes_file_and_database_entry(tmp_path):
    db = DatabaseManager(str(tmp_path / "delete.db"))
    handler = ImageHandler()
    file_operator = FileOperator(db)

    image_path = _create_test_image(tmp_path / "delete-me.png")
    metadata = handler.create_metadata(str(image_path))
    assert metadata is not None
    assert db.add_image(metadata) is True

    file_operator.delete_image(str(image_path))

    assert not image_path.exists()
    assert db.get_image(str(image_path)) is None
