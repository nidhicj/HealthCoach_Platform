"""Pure magic-byte MIME type detection. Signature-based, filename/Content-Type independent."""


def sniff_mime(content: bytes) -> str | None:
    """
    Detect MIME type by checking magic bytes at the start of content.

    Supports: application/pdf, image/jpeg, image/png.
    Returns None if none match.

    Args:
        content: Raw file bytes to sniff.

    Returns:
        MIME type string if a signature matches, None otherwise.
    """
    if not content:
        return None

    # PDF: starts with %PDF
    if content.startswith(b"%PDF"):
        return "application/pdf"

    # JPEG: starts with \xff\xd8\xff
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # PNG: starts with \x89PNG\r\n\x1a\n (8 bytes)
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    return None
