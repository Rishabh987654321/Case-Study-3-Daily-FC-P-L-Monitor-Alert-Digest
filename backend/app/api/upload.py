"""Upload and management endpoints."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import NotFoundError
from app.models import Upload
from app.schemas import PaginatedResponse, UploadCreateResponse, UploadSummary
from app.services import storage
from app.services.processor import process_upload

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadCreateResponse, status_code=201)
async def create_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    db: Session = Depends(get_db),
) -> UploadCreateResponse:
    storage.validate_file(file)
    upload_id = str(uuid.uuid4())
    await storage.save_upload(upload_id, file)

    upload = Upload(id=upload_id, filename=file.filename, name=name, status="processing")
    db.add(upload)
    db.commit()

    background_tasks.add_task(process_upload, upload_id)

    return UploadCreateResponse(upload_id=upload_id, status="processing", filename=file.filename)


@router.get("/upload/{upload_id}", response_model=UploadSummary)
def get_upload(upload_id: str, db: Session = Depends(get_db)) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise NotFoundError(f"Upload {upload_id} not found.")
    return upload


@router.get("/uploads", response_model=PaginatedResponse[UploadSummary])
def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse:
    total = db.query(Upload).count()
    items = (
        db.query(Upload)
        .order_by(Upload.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total, total_pages=total_pages)


@router.delete("/upload/{upload_id}", status_code=204)
def delete_upload(upload_id: str, db: Session = Depends(get_db)) -> None:
    upload = db.get(Upload, upload_id)
    if upload is None:
        raise NotFoundError(f"Upload {upload_id} not found.")
    db.delete(upload)  # cascades to fc_days / anomalies / digests
    db.commit()
    storage.delete_upload_files(upload_id)
