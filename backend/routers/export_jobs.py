"""Export jobs router — POST to start an export, GET SSE for progress."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import ExportJob
from backend.services import exporter

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    game_ids: list[int]
    export_dir: str
    output_format: str = "original"  # original, uncompressed, zip, 7z
    dedup_mode: str = "single"        # single, all
    lang_priority: str = "En,Zh,Ja"  # comma-separated priority list
    rename_files: bool = True
    only_preferred_languages: bool = False


class ExportJobOut(BaseModel):
    id: int
    export_dir: str
    output_format: str
    dedup_mode: str
    lang_priority: str
    rename_files: bool = True
    only_preferred_languages: bool = False
    status: str
    total_games: int
    exported_games: int
    skipped_games: int
    errors: int

    class Config:
        from_attributes = True


@router.post("", response_model=ExportJobOut)
async def start_export(
    req: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a background export job."""
    job = ExportJob(
        game_ids=json.dumps(req.game_ids),
        export_dir=req.export_dir,
        output_format=req.output_format,
        dedup_mode=req.dedup_mode,
        lang_priority=req.lang_priority,
        rename_files=req.rename_files,
        only_preferred_languages=req.only_preferred_languages,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id

    background_tasks.add_task(exporter.start_export, job_id)

    return job


@router.get("/{job_id}/status")
async def export_status_sse(job_id: int, db: Session = Depends(get_db)):
    """SSE endpoint — stream export progress events."""
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        async for event in exporter.stream_export_progress(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("", response_model=list[ExportJobOut])
def list_export_jobs(db: Session = Depends(get_db)):
    return db.query(ExportJob).order_by(ExportJob.created_at.desc()).limit(50).all()


@router.get("/{job_id}", response_model=ExportJobOut)
def get_export_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
