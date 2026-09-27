import io
import zipfile

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ZIP_MAGIC = b"PK\x03\x04"


def detect_mime_type(data: bytes) -> str | None:
    """Identify a supported upload type from its leading bytes, ignoring any client-declared type."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF"):
        return "application/pdf"
    return None


def is_docx(data: bytes) -> bool:
    """A zip archive (PK signature) with a word/ entry, which is what makes a zip a Word document."""
    if not data.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return any(name.startswith("word/") for name in archive.namelist())
    except zipfile.BadZipFile:
        return False


def detect_paper_mime_type(data: bytes) -> str | None:
    """As detect_mime_type, plus DOCX: question papers are often typed, unlike students' scripts."""
    return detect_mime_type(data) or (DOCX_MIME_TYPE if is_docx(data) else None)
