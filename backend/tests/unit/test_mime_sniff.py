from src.lib.mime_sniff import sniff_mime


def test_sniff_mime_pdf():
    """Detect PDF via %PDF magic bytes."""
    pdf_content = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
    assert sniff_mime(pdf_content) == "application/pdf"


def test_sniff_mime_pdf_minimal():
    """Detect minimal PDF signature."""
    assert sniff_mime(b"%PDF") == "application/pdf"


def test_sniff_mime_jpeg():
    """Detect JPEG via \xff\xd8\xff magic bytes."""
    jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    assert sniff_mime(jpeg_content) == "image/jpeg"


def test_sniff_mime_jpeg_minimal():
    """Detect minimal JPEG signature."""
    assert sniff_mime(b"\xff\xd8\xff") == "image/jpeg"


def test_sniff_mime_png():
    """Detect PNG via \x89PNG\r\n\x1a\n magic bytes."""
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert sniff_mime(png_content) == "image/png"


def test_sniff_mime_png_minimal():
    """Detect minimal PNG signature."""
    assert sniff_mime(b"\x89PNG\r\n\x1a\n") == "image/png"


def test_sniff_mime_exe_not_recognized():
    """Reject .exe files (MZ magic bytes) — clearly not PDF/JPEG/PNG."""
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    assert sniff_mime(exe_content) is None


def test_sniff_mime_empty():
    """Return None for empty content."""
    assert sniff_mime(b"") is None


def test_sniff_mime_random_bytes():
    """Return None for unrecognized byte sequences."""
    random_content = b"This is just random text that doesn't match any signature"
    assert sniff_mime(random_content) is None


def test_sniff_mime_truncated_pdf():
    """Partial PDF signature should be recognized."""
    assert sniff_mime(b"%PD") is None  # Not enough bytes, but should still return None
