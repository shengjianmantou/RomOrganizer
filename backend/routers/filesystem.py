"""Filesystem router — native folder picking dialog & directory browsing."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.services.dialog import pick_directory

router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


class PickDirectoryRequest(BaseModel):
    prompt: Optional[str] = "Select Directory"


class PickDirectoryResponse(BaseModel):
    path: Optional[str] = None
    canceled: bool = False


@router.post("/pick-directory", response_model=PickDirectoryResponse)
async def open_directory_dialog(req: PickDirectoryRequest = PickDirectoryRequest()):
    """Trigger the native OS folder selection dialog."""
    path = await pick_directory(prompt=req.prompt or "Select Directory")
    if not path:
        return PickDirectoryResponse(path=None, canceled=True)
    return PickDirectoryResponse(path=path, canceled=False)


@router.get("/browse")
def browse_directories(path: Optional[str] = None):
    """List subdirectories of a given path (useful for breadcrumb browsing)."""
    target = Path(path).expanduser().resolve() if path else Path.home()
    if not target.exists() or not target.is_dir():
        target = Path.home()

    subdirs = []
    try:
        for entry in os.scandir(target):
            if entry.is_dir() and not entry.name.startswith("."):
                subdirs.append({
                    "name": entry.name,
                    "path": entry.path,
                })
    except PermissionError:
        pass

    subdirs.sort(key=lambda x: x["name"].lower())

    return {
        "current_path": str(target),
        "parent_path": str(target.parent) if target.parent != target else None,
        "directories": subdirs,
    }
