from fastapi import APIRouter, Request

from service.core.runtime_warm import get_policy_warm_status, get_startup_warm_status
from service.db import mysql
from service.index.manager import get_index_manager, get_vision_index_manager
from service.models.schemas import FaceStatusResponse, StatusResponse, VisionStatusResponse
from service.scan.manager import scan_manager

router = APIRouter()


@router.get("/status", response_model=StatusResponse)
def status(request: Request):
    index = get_index_manager()
    vision_index = get_vision_index_manager()
    vision_state = mysql.get_index_state_vision()
    scan_state = scan_manager.status()
    policy = getattr(request.state, "policy", None)
    startup_warm = get_startup_warm_status()
    policy_warm = None if (not policy or bool(getattr(policy, "is_admin", False))) else get_policy_warm_status(getattr(policy, "id", ""))
    search_ready = bool(startup_warm.get("ready"))
    search_ready_message = str(startup_warm.get("message") or "")
    if policy_warm is not None and not bool(policy_warm.get("ready")):
        search_ready = False
        search_ready_message = str(policy_warm.get("message") or search_ready_message or "系统预热中")
    return StatusResponse(
        photos=mysql.count_photos(),
        faces=mysql.count_faces(),
        index_path=index.index_path,
        index_ready=index.exists(),
        vision_index_path=vision_index.index_path,
        vision_index_ready=vision_index.exists(),
        vision_photos=mysql.count_photo_embeddings(),
        vision_last_embedding_id=int(vision_state["last_embedding_id"]) if vision_state else 0,
        index_health=index.get_health(),
        vision_index_health=vision_index.get_health(),
        scan_running=scan_state.get("running", False),
        scan_paused=scan_state.get("paused", False),
        runtime_warm=startup_warm,
        policy_warm=policy_warm,
        search_ready=search_ready,
        search_ready_message=search_ready_message,
    )


@router.get("/vision/status", response_model=VisionStatusResponse)
def vision_status():
    photos_total = mysql.count_photos()
    vision_photos = mysql.count_photo_embeddings()
    percent = (vision_photos / photos_total * 100.0) if photos_total else 0.0
    vision_index = get_vision_index_manager()
    return VisionStatusResponse(
        photos_total=photos_total,
        vision_photos=vision_photos,
        percent=round(percent, 2),
        index_path=vision_index.index_path,
        index_ready=vision_index.exists(),
    )


@router.get("/face/status", response_model=FaceStatusResponse)
def face_status():
    photos_total = mysql.count_photos()
    faces_total = mysql.count_faces()
    percent = (faces_total / max(1, photos_total) * 100.0) if photos_total else 0.0
    return FaceStatusResponse(
        photos_total=photos_total,
        faces_total=faces_total,
        percent=round(min(percent, 100.0), 2),
    )
