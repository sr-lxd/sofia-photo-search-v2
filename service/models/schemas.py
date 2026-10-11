from pydantic import BaseModel
from typing import List, Optional


class SearchHit(BaseModel):
    embedding_id: int
    score: float
    face_id: Optional[int] = None
    photo_id: Optional[int] = None
    face_count: Optional[int] = None
    file_path: Optional[str] = None
    exif_datetime: Optional[str] = None
    bbox: Optional[List[int]] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    distance_km: Optional[float] = None


class SearchResponse(BaseModel):
    stage: int
    total: int
    results: List[SearchHit]
    debug: Optional[dict] = None
    search_id: Optional[str] = None
    batch: Optional[int] = None
    batch_size: Optional[int] = None
    total_batches: Optional[int] = None
    has_prev: Optional[bool] = None
    has_next: Optional[bool] = None


class StatusResponse(BaseModel):
    photos: int
    faces: int
    index_path: str
    index_ready: bool
    vision_index_path: Optional[str] = None
    vision_index_ready: Optional[bool] = None
    vision_photos: Optional[int] = None
    vision_last_embedding_id: Optional[int] = None
    index_health: Optional[dict] = None
    vision_index_health: Optional[dict] = None
    scan_running: bool
    scan_paused: bool
    runtime_warm: Optional[dict] = None
    policy_warm: Optional[dict] = None
    search_ready: Optional[bool] = None
    search_ready_message: Optional[str] = None


class VisionStatusResponse(BaseModel):
    photos_total: int
    vision_photos: int
    percent: float
    index_path: str
    index_ready: bool


class FaceStatusResponse(BaseModel):
    photos_total: int
    faces_total: int
    percent: float


class ScanProgressResponse(BaseModel):
    scan_type: Optional[str] = None
    processed_photos: int
    total_photos: int
    percent: float
    last_path: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
