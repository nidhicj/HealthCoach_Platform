"""EXIF capture-time extraction for meal photos (D-26). Deliberately conservative:
any failure to parse (unsupported format, corrupt bytes, missing tag) returns None
rather than raising — a meal log must never fail to save because of unreadable EXIF.
See PHASE-03 Design Decisions 1 and 5 for why missing/HEIC both resolve to None here,
not an error and not a synthesized fallback timestamp."""
from __future__ import annotations

import io
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import ExifTags, Image

_DATETIME_ORIGINAL_TAG = next(
    tag_id for tag_id, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"
)

# EXIF DateTimeOriginal is camera-local wall-clock time with no offset info.
# This codebase assumes IST throughout for its India-first users (e.g. s3.py,
# the check-in reminder cron) — treat capture times the same way.
_IST = ZoneInfo("Asia/Kolkata")

# EXIF's own datetime string format, e.g. "2026:07:15 08:30:00" — colons in the date
# portion, not hyphens, per the EXIF 2.3 spec.
_EXIF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


def extract_capture_time(image_bytes: bytes, mime_type: str) -> datetime | None:
    """Best-effort extraction of DateTimeOriginal. Returns None for any of:
    unsupported format (incl. all HEIC — stock Pillow can't decode it, Decision 5),
    no EXIF block, no DateTimeOriginal tag, or an unparseable value. Never raises."""
    if mime_type == "image/heic":
        return None

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            exif = img.getexif()
            # DateTimeOriginal lives in the Exif sub-IFD (pointed to by IFD0 tag
            # 0x8769), not in the top-level IFD0 dict — img.getexif() alone only
            # returns IFD0. get_ifd() follows the pointer to fetch it.
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            raw_value = exif_ifd.get(_DATETIME_ORIGINAL_TAG)
            if not raw_value:
                return None
            naive = datetime.strptime(raw_value, _EXIF_DATETIME_FORMAT)
            # Interpret as IST rather than leaving it naive — asyncpg encodes
            # naive datetimes via .astimezone(utc), i.e. in the server
            # process's own timezone (UTC in production), which would
            # otherwise silently shift every capture time by up to 5h30m.
            return naive.replace(tzinfo=_IST)
    except Exception:
        return None
