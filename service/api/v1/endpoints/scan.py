from fastapi import APIRouter, HTTPException
import os
import threading
import time
import uuid
from pathlib import Path
from service.core.config import settings
from service.db import mysql
from service.models.schemas import ScanProgressResponse
from service.scan.manager import scan_manager
from service.scan import scanner

router = APIRouter()
_EXIF_REPAIR_LOCK = threading.Lock()
_EXIF_REPAIR_STATE: dict = {
    "task_id": "",
    "status": "idle",
    "message": "未开始",
    "target_dir": "",
    "available_dirs": [],
    "started_at": None,
    "finished_at": None,
    "total": 0,
    "processed": 0,
    "updated": 0,
    "fallback_mtime": 0,
    "missing": 0,
    "failed": 0,
    "unchanged": 0,
    "current_path": "",
}


def _snapshot_exif_repair_state() -> dict:
    with _EXIF_REPAIR_LOCK:
        data = dict(_EXIF_REPAIR_STATE)
        data["available_dirs"] = list(_EXIF_REPAIR_STATE.get("available_dirs") or [])
        return data


def _set_exif_repair_state(**kwargs) -> None:
    with _EXIF_REPAIR_LOCK:
        _EXIF_REPAIR_STATE.update(kwargs)


def _update_exif_repair_state(task_id: str, **kwargs) -> bool:
    with _EXIF_REPAIR_LOCK:
        if str(_EXIF_REPAIR_STATE.get("task_id") or "") != str(task_id or ""):
            return False
        _EXIF_REPAIR_STATE.update(kwargs)
        return True


def _run_exif_repair_task(task_id: str, selected: str) -> None:
    def _progress_cb(payload: dict) -> None:
        total = int(payload.get("total") or 0)
        processed = int(payload.get("processed") or 0)
        updated = int(payload.get("updated") or 0)
        fallback_mtime = int(payload.get("fallback_mtime") or 0)
        missing = int(payload.get("missing") or 0)
        failed = int(payload.get("failed") or 0)
        unchanged = int(payload.get("unchanged") or 0)
        message = f"时间修复中：{processed}/{total if total else '?'} 文件"
        _update_exif_repair_state(
            task_id,
            total=total,
            processed=processed,
            updated=updated,
            fallback_mtime=fallback_mtime,
            missing=missing,
            failed=failed,
            unchanged=unchanged,
            current_path=str(payload.get("current_path") or ""),
            message=message,
        )

    try:
        result = scanner.repair_exif_datetime_by_dir(selected, on_progress=_progress_cb)
        total = int(result.get("total") or 0)
        processed = int(result.get("processed") or 0)
        updated = int(result.get("updated") or 0)
        fallback_mtime = int(result.get("fallback_mtime") or 0)
        missing = int(result.get("missing") or 0)
        failed = int(result.get("failed") or 0)
        unchanged = int(result.get("unchanged") or 0)
        _update_exif_repair_state(
            task_id,
            status="completed",
            message=f"时间修复完成：{processed}/{total if total else 0} 文件",
            total=total,
            processed=processed,
            updated=updated,
            fallback_mtime=fallback_mtime,
            missing=missing,
            failed=failed,
            unchanged=unchanged,
            current_path="",
            finished_at=time.time(),
        )
    except Exception as exc:
        _update_exif_repair_state(
            task_id,
            status="failed",
            message=f"时间修复失败：{exc}",
            current_path="",
            finished_at=time.time(),
        )


def _get_exif_repair_dirs() -> list[str]:
    roots = [str(v or "").strip() for v in (settings.paths.photo_roots or [])]
    cleaned: list[str] = []
    seen: set[str] = set()
    for root in roots:
        if not root:
            continue
        norm = root.replace("/", "\\").rstrip("\\").lower()
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append(root.replace("/", "\\").rstrip("\\"))
    return cleaned


def _normalize_target_dir(value: str) -> str:
    return str(Path(str(value or "").strip())).replace("/", "\\").rstrip("\\")


def _is_under_root(target_dir: str, root_dir: str) -> bool:
    try:
        target_norm = os.path.normcase(str(Path(target_dir).resolve(strict=False)))
        root_norm = os.path.normcase(str(Path(root_dir).resolve(strict=False)))
        common = os.path.commonpath([target_norm, root_norm])
        return common == root_norm
    except Exception:
        return False


_ACTIVE_SCAN_PROGRESS_STATUSES = {"running", "counting"}


def _get_latest_scan_progress_reconciled() -> dict | None:
    row = mysql.get_latest_scan_progress()
    if not row:
        return None
    status = str(row.get("status") or "").strip().lower()
    if status not in _ACTIVE_SCAN_PROGRESS_STATUSES:
        return row
    manager_state = scan_manager.status()
    if bool(manager_state.get("running")):
        return row
    progress_id = row.get("id")
    if not progress_id:
        return row
    try:
        mysql.finish_scan_progress(int(progress_id), status="stopped")
    except Exception:
        return row
    return mysql.get_latest_scan_progress() or row


@router.post("/scan")
def start_scan(full: bool = False, resume: bool = False):
    if _snapshot_exif_repair_state().get("status") == "running":
        raise HTTPException(status_code=409, detail="时间修复进行中，禁止启动扫描。")
    return scan_manager.start(full=full, resume=resume)


@router.post("/scan/pause")
def pause_scan():
    return scan_manager.pause()


@router.post("/scan/stop")
def stop_scan():
    return scan_manager.stop()


@router.post("/scan/resume")
def resume_scan():
    return scan_manager.resume()


@router.get("/scan/status")
def scan_status():
    return scan_manager.status()


@router.get("/scan/progress", response_model=ScanProgressResponse)
def scan_progress():
    row = _get_latest_scan_progress_reconciled()
    if not row:
        return ScanProgressResponse(processed_photos=0, total_photos=0, percent=0.0)
    total = int(row.get("total_photos") or 0)
    processed = int(row.get("processed_photos") or 0)
    percent = (processed / total * 100.0) if total else 0.0
    return ScanProgressResponse(
        scan_type=row.get("scan_type"),
        processed_photos=processed,
        total_photos=total,
        percent=round(min(percent, 100.0), 2),
        last_path=row.get("last_path"),
        status=row.get("status"),
        started_at=str(row.get("started_at")) if row.get("started_at") else None,
        updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
    )


@router.post("/scan/exif_repair")
def exif_repair(target_dir: str | None = None):
    state = scan_manager.status()
    if state.get("running"):
        raise HTTPException(status_code=409, detail="扫描进行中，禁止执行时间修复。")
    running_state = _snapshot_exif_repair_state()
    if running_state.get("status") == "running":
        raise HTTPException(status_code=409, detail="已有时间修复任务在运行。")
    dirs = _get_exif_repair_dirs()
    if not dirs:
        raise HTTPException(status_code=400, detail="未配置照片根目录，无法执行时间修复。")
    selected = _normalize_target_dir(target_dir or "")
    if not selected:
        selected = dirs[0]
    if not any(_is_under_root(selected, root) for root in dirs):
        raise HTTPException(status_code=400, detail="target_dir 不在可选照片根目录下。")
    selected_path = Path(selected)
    if not selected_path.exists() or not selected_path.is_dir():
        raise HTTPException(status_code=400, detail="target_dir 不存在或不是目录。")
    task_id = uuid.uuid4().hex
    _set_exif_repair_state(
        task_id=task_id,
        status="running",
        message="时间修复任务已启动。",
        target_dir=selected,
        available_dirs=list(dirs),
        started_at=time.time(),
        finished_at=None,
        total=0,
        processed=0,
        updated=0,
        fallback_mtime=0,
        missing=0,
        failed=0,
        unchanged=0,
        current_path="",
    )
    thread = threading.Thread(target=_run_exif_repair_task, args=(task_id, selected), daemon=True)
    thread.start()
    return {"task_id": task_id, "status": "running", "target_dir": selected, "message": "时间修复任务已启动。"}


@router.get("/scan/exif_repair_status")
def exif_repair_status(task_id: str | None = None):
    state = _snapshot_exif_repair_state()
    current_id = str(state.get("task_id") or "")
    if task_id:
        target_id = str(task_id).strip()
        if not current_id:
            raise HTTPException(status_code=404, detail="time repair task not found")
        if current_id != target_id:
            raise HTTPException(status_code=404, detail="time repair task not found")
    total = int(state.get("total") or 0)
    processed = int(state.get("processed") or 0)
    percent = round((processed / total * 100.0), 2) if total else 0.0
    state["percent"] = min(max(percent, 0.0), 100.0)
    return state


@router.get("/scan/exif_repair_dirs")
def exif_repair_dirs():
    dirs = _get_exif_repair_dirs()
    return {
        "dirs": dirs,
        "default_dir": dirs[0] if dirs else "",
    }

def _list_child_dirs(target_dir: str, roots: list[str]) -> list[dict[str, str]]:
    target_path = Path(target_dir)
    children: list[dict[str, str]] = []
    try:
        for child in target_path.iterdir():
            if not child.is_dir():
                continue
            child_norm = _normalize_target_dir(str(child))
            if not any(_is_under_root(child_norm, root) for root in roots):
                continue
            children.append({"name": child.name, "path": child_norm})
    except Exception:
        return []
    children.sort(key=lambda item: str(item.get("name") or "").casefold())
    return children


@router.get("/scan/exif_repair_browse")
def exif_repair_browse(path: str | None = None):
    roots = _get_exif_repair_dirs()
    if not roots:
        raise HTTPException(status_code=400, detail="未配置照片根目录。")

    selected = _normalize_target_dir(path or "")
    if not selected:
        selected = roots[0]
    if not any(_is_under_root(selected, root) for root in roots):
        raise HTTPException(status_code=400, detail="path 不在可选照片根目录下。")

    target_path = Path(selected)
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=400, detail="path 不存在或不是目录。")

    parent_dir = ""
    for root in roots:
        if not _is_under_root(selected, root):
            continue
        root_norm = _normalize_target_dir(root)
        selected_norm = _normalize_target_dir(selected)
        if selected_norm != root_norm:
            parent_candidate = _normalize_target_dir(str(target_path.parent))
            if _is_under_root(parent_candidate, root):
                parent_dir = parent_candidate
        break

    return {
        "roots": roots,
        "path": _normalize_target_dir(str(target_path)),
        "parent": parent_dir,
        "subdirs": _list_child_dirs(str(target_path), roots),
    }


