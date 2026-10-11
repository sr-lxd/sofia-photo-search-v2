from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from service.core.acl import ensure_photo_allowed
from service.db import mysql

router = APIRouter()


class FavoriteCreate(BaseModel):
    name: str


class FavoriteAdd(BaseModel):
    face_id: int


@router.post("/favorites")
def create_favorite(payload: FavoriteCreate, request: Request):
    policy = request.state.policy
    name = str(payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    row = mysql.create_favorite(policy.id, name)
    return row


@router.get("/favorites")
def list_favorites(request: Request):
    policy = request.state.policy
    return mysql.list_favorites_by_policy(policy.id)


@router.post("/favorites/{favorite_id}/add_face")
def add_face_to_favorite(favorite_id: int, payload: FavoriteAdd, request: Request):
    policy = request.state.policy
    favorite = mysql.get_favorite_by_policy(favorite_id, policy.id)
    if not favorite:
        raise HTTPException(status_code=404, detail="favorite not found")
    face = mysql.fetch_one(
        """
        SELECT f.id, f.photo_id
        FROM faces f
        JOIN photos p ON p.id = f.photo_id
        WHERE f.id=%s AND p.status='active'
        LIMIT 1
        """,
        (payload.face_id,),
    )
    if not face:
        raise HTTPException(status_code=404, detail="face_id not found")
    ensure_photo_allowed(policy, int(face["photo_id"]))
    mysql.add_face_to_favorite(favorite_id, payload.face_id)
    return {"ok": True}


@router.post("/search/favorite/{favorite_id}")
def search_favorite(favorite_id: int, request: Request, topk: int = 50, stage: int = 3):
    policy = request.state.policy
    row = mysql.get_favorite_embedding_row(favorite_id, policy.id)
    if not row:
        raise HTTPException(status_code=404, detail="favorite empty")
    embedding_id = int(row["embedding_id"])
    return {"favorite_id": favorite_id, "embedding_id": embedding_id, "topk": topk, "stage": stage}
