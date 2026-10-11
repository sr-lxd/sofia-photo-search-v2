from datetime import datetime
from pathlib import Path
import shutil

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from service.core.acl import ensure_photo_allowed, policy_can_access_path
from service.core.config import settings

router = APIRouter()


class ExportRequest(BaseModel):
    photo_ids: list[int] = []
    file_paths: list[str] = []
    mode: str = "copy"  # copy or zip (zip reserved)


@router.post("/export")
def export_photos(payload: ExportRequest, request: Request):
    policy = request.state.policy
    if payload.mode not in ("copy", "zip"):
        raise HTTPException(status_code=400, detail="invalid mode")

    paths = [
        str(path_value)
        for path_value in (payload.file_paths or [])
        if policy_can_access_path(policy, path_value)
    ]
    for photo_id in payload.photo_ids or []:
        row = ensure_photo_allowed(policy, int(photo_id))
        paths.append(str(row["file_path"]))

    if not paths:
        raise HTTPException(status_code=400, detail="no photos to export")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path(settings.paths.export_dir) / stamp
    export_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    for src in paths:
        src_path = Path(src)
        if not src_path.exists():
            continue
        dest_path = export_dir / src_path.name
        shutil.copy2(src_path, dest_path)
        exported.append(str(dest_path))

    return {"export_dir": str(export_dir), "count": len(exported), "files": exported}
