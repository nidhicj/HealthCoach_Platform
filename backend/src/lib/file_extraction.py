"""Text extraction from uploaded files for LLM prompt assembly. Per ADR-0003."""
from io import BytesIO


async def extract_text(content: bytes, mime_type: str) -> str:
    if mime_type in ("text/plain", "text/markdown"):
        return content.decode("utf-8", errors="replace")
    elif mime_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            from docx import Document
            doc = Document(BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            # python-docx may be incompatible with Pyodide at runtime (Decision I)
            return ""
    return ""
