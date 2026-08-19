import io
from datetime import datetime, timezone

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
    # EXIF DateTimeOriginal is camera-local wall-clock time, no offset info.
    # This codebase's IST-first assumption means "2026:07:15 08:30:00" is
    # 08:30 IST, which is 03:00 UTC (IST = UTC+5:30). The result must be a
    # tz-aware datetime whose UTC instant is correct — a naive-equality
    # assertion here would have missed the original 5h30m bug (C1).
    photo = _jpeg_with_datetime_original("2026:07:15 08:30:00")
    result = extract_capture_time(photo, "image/jpeg")
    assert result is not None
    assert result.tzinfo is not None
    assert result.astimezone(timezone.utc) == datetime(2026, 7, 15, 3, 0, 0, tzinfo=timezone.utc)


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
