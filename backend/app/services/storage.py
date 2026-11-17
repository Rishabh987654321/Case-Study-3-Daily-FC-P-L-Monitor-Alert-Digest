"""Storage service — upload files live at {upload_dir}/{upload_id}/{original_filename}."""

import shutil
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings
from app.errors import InvalidFileError, NoDataError

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _upload_dir(upload_id: str) -> Path:
    return get_settings().upload_dir_path / upload_id


def validate_file(upload_file: UploadFile) -> None:
    filename = upload_file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileError(
            f"Unsupported file type '{ext or '(none)'}'. Use .csv, .xlsx, or .xls."
        )
    settings = get_settings()
    max_bytes = settings.max_file_mb * 1024 * 1024
    if upload_file.size is not None and upload_file.size > max_bytes:
        raise InvalidFileError(f"File exceeds max size of {settings.max_file_mb}MB.")


async def save_upload(upload_id: str, upload_file: UploadFile) -> Path:
    """Persist the uploaded file to disk and return its saved path."""
    content = await upload_file.read()
    if not content:
        raise NoDataError("Uploaded file is empty.")

    settings = get_settings()
    max_bytes = settings.max_file_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise InvalidFileError(f"File exceeds max size of {settings.max_file_mb}MB.")

    directory = _upload_dir(upload_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = upload_file.filename or "upload.csv"
    dest = directory / filename
    dest.write_bytes(content)
    return dest


def get_file_path(upload_id: str) -> Path | None:
    directory = _upload_dir(upload_id)
    if not directory.exists():
        return None
    files = [f for f in directory.iterdir() if f.is_file()]
    return files[0] if files else None


def report_path(upload_id: str) -> Path:
    return _upload_dir(upload_id) / "pnl_report.xlsx"


def delete_upload_files(upload_id: str) -> None:
    directory = _upload_dir(upload_id)
    if directory.exists():
        shutil.rmtree(directory)
