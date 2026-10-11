import os
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from service.core.config import settings
from service.db import mysql
from service.index.manager import get_index_manager, get_vision_index_manager
from service.scan.manager import scan_manager

router = APIRouter()

COMPACT_CONFIRM_TEXT = "我已备份并确认压实"
_JOB_LOCK = threading.Lock()
_JOB_STATE: dict = {
    "status": "idle",
    "job_id": "",
    "target": "",
    "dry_run": False,
    "started_at": None,
    "finished_at": None,
    "message": "未开始",
    "steps": [],
    "result": {},
    "warning": "",
}


class CompactStartPayload(BaseModel):
    target: str = "all"  # face | vision | all
    dry_run: bool = False
    confirm_text: str = ""


def _snapshot_state() -> dict:
    with _JOB_LOCK:
        data = dict(_JOB_STATE)
        data["steps"] = [dict(step) for step in (_JOB_STATE.get("steps") or [])]
        data["result"] = dict(_JOB_STATE.get("result") or {})
        return data


def _set_state(**kwargs) -> None:
    with _JOB_LOCK:
        _JOB_STATE.update(kwargs)


def _update_step(name: str, **kwargs) -> None:
    with _JOB_LOCK:
        steps = list(_JOB_STATE.get("steps") or [])
        idx = next((i for i, step in enumerate(steps) if step.get("name") == name), -1)
        if idx < 0:
            step = {"name": name, "status": "pending"}
            step.update(kwargs)
            steps.append(step)
        else:
            step = dict(steps[idx])
            step.update(kwargs)
            steps[idx] = step
        _JOB_STATE["steps"] = steps


def _normalize_target(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("face", "vision", "all"):
        return raw
    raise HTTPException(status_code=400, detail="target must be one of: face, vision, all")


def _selected_targets(target: str) -> list[str]:
    if target == "face":
        return ["face"]
    if target == "vision":
        return ["vision"]
    return ["face", "vision"]


def _index_info(kind: str) -> dict:
    mgr = get_index_manager() if kind == "face" else get_vision_index_manager()
    path = mgr.index_path
    size = int(os.path.getsize(path)) if os.path.exists(path) else 0
    return {"kind": kind, "path": path, "size": size}


def _disk_precheck(targets: list[str]) -> dict:
    infos = [_index_info(kind) for kind in targets]
    index_dir = Path(settings.paths.index_dir)
    free = int(shutil.disk_usage(index_dir).free)
    current_total = int(sum(item["size"] for item in infos))
    required_min = max(256 * 1024 * 1024, int(current_total * 1.15))
    recommended = max(required_min, int(current_total * 1.6))
    return {
        "index_dir": str(index_dir),
        "targets": infos,
        "free_bytes": free,
        "required_min_bytes": required_min,
        "recommended_bytes": recommended,
        "enough_min": free >= required_min,
        "enough_recommended": free >= recommended,
    }


def _compact_one(kind: str, *, dry_run: bool, job_id: str) -> dict:
    if kind == "face":
        mgr = get_index_manager()
        ids = mysql.fetch_active_face_embedding_ids()
    else:
        mgr = get_vision_index_manager()
        ids = mysql.fetch_active_photo_embedding_ids()

    info = _index_info(kind)
    _update_step(kind, status="running", message=f"正在压实 {kind} 索引...", total_ids=len(ids), processed=0)

    def _progress_cb(payload: dict):
        state = _snapshot_state()
        if state.get("job_id") != job_id or state.get("status") != "running":
            return
        _update_step(
            kind,
            status="running",
            phase=str(payload.get("phase") or ""),
            processed=int(payload.get("processed") or 0),
            total=int(payload.get("total") or 0),
            added=int(payload.get("added") or 0),
            skipped=int(payload.get("skipped") or 0),
        )

    result = mgr.compact_with_embedding_ids(ids, dry_run=dry_run, progress_cb=_progress_cb)
    new_size = int(os.path.getsize(info["path"])) if os.path.exists(info["path"]) else 0
    output = {
        "kind": kind,
        "index_path": info["path"],
        "before_size": int(info["size"]),
        "after_size": int(new_size),
        "saved_bytes": max(0, int(info["size"]) - int(new_size)),
    }
    output.update(result)
    _update_step(kind, status="completed", message=f"{kind} 压实完成", **output)
    return output


def _run_compaction(job_id: str, target: str, dry_run: bool) -> None:
    try:
        summary = {}
        targets = _selected_targets(target)
        for kind in targets:
            state = _snapshot_state()
            if state.get("job_id") != job_id or state.get("status") != "running":
                return
            summary[kind] = _compact_one(kind, dry_run=dry_run, job_id=job_id)
        _set_state(
            status="completed",
            finished_at=time.time(),
            message="压实完成" if not dry_run else "体检完成（未改写索引）",
            result={"targets": summary},
        )
    except Exception as exc:
        _set_state(
            status="failed",
            finished_at=time.time(),
            message=f"压实失败：{exc}",
        )


@router.get("/index/compact/status")
def compact_status():
    state = _snapshot_state()
    state["confirm_text_required"] = COMPACT_CONFIRM_TEXT
    return state


@router.post("/index/compact/start")
def compact_start(payload: CompactStartPayload):
    target = _normalize_target(payload.target)
    dry_run = bool(payload.dry_run)
    if scan_manager.status().get("running"):
        raise HTTPException(status_code=400, detail="扫描任务正在运行，请先停止扫描再进行索引压实。")

    with _JOB_LOCK:
        if _JOB_STATE.get("status") == "running":
            raise HTTPException(status_code=409, detail="已有索引压实任务在运行。")

    targets = _selected_targets(target)
    disk = _disk_precheck(targets)
    warning = (
        "压实将重建索引并替换线上文件。请确认已备份，并避免同时执行扫描。"
        "执行期间检索可能变慢。"
    )
    if not dry_run:
        if payload.confirm_text.strip() != COMPACT_CONFIRM_TEXT:
            raise HTTPException(
                status_code=400,
                detail=f"为避免误操作，请在确认框输入：{COMPACT_CONFIRM_TEXT}",
            )
        if not disk.get("enough_min"):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"磁盘空间不足，最少需要 {disk['required_min_bytes']} 字节，"
                    f"当前可用 {disk['free_bytes']} 字节。"
                ),
            )

    job_id = uuid.uuid4().hex
    now = time.time()
    _set_state(
        status="running",
        job_id=job_id,
        target=target,
        dry_run=dry_run,
        started_at=now,
        finished_at=None,
        message="开始执行索引压实..." if not dry_run else "开始执行索引体检...",
        steps=[{"name": kind, "status": "pending"} for kind in targets],
        result={"disk_precheck": disk},
        warning=warning,
    )
    thread = threading.Thread(target=_run_compaction, args=(job_id, target, dry_run), daemon=True)
    thread.start()
    return _snapshot_state()
