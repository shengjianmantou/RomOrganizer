"""Import jobs router — POST to start an import, GET SSE for progress."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import ImportJob
from backend.services import importer

router = APIRouter(prefix="/api/import", tags=["import"])


class ImportRequest(BaseModel):
    source_directories: list[str]


class ImportJobOut(BaseModel):
    id: int
    status: str
    total_files: int
    processed_files: int
    imported_games: int
    skipped_duplicates: int
    errors: int

    class Config:
        from_attributes = True


@router.post("", response_model=ImportJobOut)
async def start_import(
    req: ImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a background import job for the given source directories."""
    job = ImportJob(
        source_directories=json.dumps(req.source_directories),
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id

    background_tasks.add_task(importer.start_import, job_id, req.source_directories)

    return job


@router.get("/{job_id}/status")
async def import_status_sse(job_id: int, db: Session = Depends(get_db)):
    """SSE endpoint — stream import progress events."""
    job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        async for event in importer.stream_progress(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("", response_model=list[ImportJobOut])
def list_import_jobs(db: Session = Depends(get_db)):
    return db.query(ImportJob).order_by(ImportJob.created_at.desc()).limit(50).all()


@router.get("/{job_id}", response_model=ImportJobOut)
def get_import_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
