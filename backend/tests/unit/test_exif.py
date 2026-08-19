import io
from datetime import datetime

import piexif  # dev-only, test-fixture generation — NOT added as a runtime dependency
from PIL import Image

from src.lib.exif import extract_capture_time


def _jpeg_with_datetime_original(dt_str: str) -> bytes:
    """Build a minimal in-memory JPEG with a DateTimeOriginal EXIF tag for testing.
    Uses piexif only to construct the test fixture bytes — not a plan dependency."""
    img = Image.new("RGB", (4, 4))
    exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: dt_str.encode()}}
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="jpeg", exif=exif_bytes)
    return buf.getvalue()


def test_extracts_datetime_original_from_jpeg():
    photo = _jpeg_with_datetime_original("2026:07:15 08:30:00")
    result = extract_capture_time(photo, "image/jpeg")
    assert result == datetime(2026, 7, 15, 8, 30, 0)


def test_returns_none_for_jpeg_with_no_exif():
    img = Image.new("RGB", (4, 4))
    buf = io.BytesIO()
    img.save(buf, format="jpeg")
    assert extract_capture_time(buf.getvalue(), "image/jpeg") is None


def test_returns_none_for_heic_without_raising():
    # Stock Pillow cannot decode HEIC at all (Decision 5) — must degrade gracefully, never 500.
    fake_heic_bytes = b"not a real heic file, just bytes with the right content-type"
    assert extract_capture_time(fake_heic_bytes, "image/heic") is None


def test_returns_none_for_corrupt_bytes_without_raising():
    assert extract_capture_time(b"\x00\x01garbage", "image/jpeg") is None
