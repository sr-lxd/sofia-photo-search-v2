from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel
from service.core.acl import ensure_photo_allowed
from service.db import mysql

router = APIRouter()


class StandardPhotoSet(BaseModel):
    photo_id: int


class StandardPhotoDelete(BaseModel):
    photo_ids: list[int] | None = None


@router.get("/standard")
def get_standard_photos(request: Request):
    policy = request.state.policy
    rows = mysql.list_standard_photos(policy.id)
    photo_ids = []
    for row in rows:
        try:
            pid = int(row["photo_id"])
        except Exception:
            continue
        if pid > 0:
            photo_ids.append(pid)
    face_counts = mysql.fetch_face_counts_by_photo_ids(photo_ids) if photo_ids else {}
    items = []
    for row in rows:
        pid = int(row["photo_id"])
        items.append(
            {
                "photo_id": pid,
                "file_path": row.get("file_path"),
                "exif_datetime": str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                "face_count": int(face_counts.get(pid, 0)),
            }
        )
    return {"items": items}


@router.post("/standard")
def set_standard_photo(payload: StandardPhotoSet, request: Request):
    policy = request.state.policy
    ensure_photo_allowed(policy, payload.photo_id)
    mysql.add_standard_photo(policy.id, payload.photo_id)
    return get_standard_photos(request)


@router.delete("/standard")
def clear_standard_photo(request: Request, payload: StandardPhotoDelete | None = Body(default=None)):
    policy = request.state.policy
    ids = (payload.photo_ids if payload else None) or []
    if ids:
        allowed_ids = []
        for photo_id in ids:
            ensure_photo_allowed(policy, int(photo_id))
            allowed_ids.append(int(photo_id))
        deleted = mysql.remove_standard_photos(policy.id, allowed_ids)
        return {"ok": True, "deleted": int(deleted)}
    mysql.clear_standard_photos(policy.id)
    return {"ok": True, "deleted": "all"}
