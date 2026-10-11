from service.core.date_utils import end_exclusive, date_bounds
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageOps
from starlette.background import BackgroundTask

from service.core.acl import ensure_photo_allowed, filter_photo_rows
from service.core.config import settings
from service.db import mysql
from service.scan.manager import scan_manager

router = APIRouter()


class DownloadRequest(BaseModel):
    photo_ids: list[int]
    dest_dir: str


class DownloadZipPrepareRequest(BaseModel):
    photo_ids: list[int]


class TrashPhotosRequest(BaseModel):
    photo_ids: list[int]


class RenamePhotoRequest(BaseModel):
    new_stem: str


_DOWNLOAD_TASKS_LOCK = threading.Lock()
_DOWNLOAD_TASKS: dict[str, dict] = {}
_DOWNLOAD_TASK_TTL_SECONDS = 3600
_PRE_DELETED_DIR = Path(settings.config_path).resolve().parent / "pre_deleted"
_PRE_DELETED_MANIFEST = "_manifest.jsonl"
_INVALID_WIN_NAME_CHARS_RE = re.compile(r'[\\\\/:*?"<>|]')
_WIN_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _normalize_photo_ids(photo_ids: list[int] | None) -> list[int]:
    cleaned = [int(pid) for pid in (photo_ids or []) if int(pid) > 0]
    seen: set[int] = set()
    result: list[int] = []
    for pid in cleaned:
        if pid in seen:
            continue
        seen.add(pid)
        result.append(pid)
    return result


def _path_is_under_root(src: Path, root: Path) -> bool:
    try:
        src_norm = os.path.normcase(str(src.resolve(strict=False)))
        root_norm = os.path.normcase(str(root.resolve(strict=False)))
        common = os.path.commonpath([src_norm, root_norm])
        return common == root_norm
    except Exception:
        return False


def _resolve_photo_root_info(src: Path):
    src_resolved = src.resolve(strict=False)
    for idx, root_raw in enumerate(settings.paths.photo_roots or []):
        root = Path(root_raw).resolve(strict=False)
        if not _path_is_under_root(src_resolved, root):
            continue
        relative = Path(os.path.relpath(str(src_resolved), str(root)))
        return idx, root, relative
    return None


def _build_trash_dest_path(photo_id: int, src: Path, root_idx: int, relative_path: Path) -> Path:
    parent = _PRE_DELETED_DIR / f"root_{root_idx + 1}" / relative_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    candidate = parent / f"{photo_id}_{src.name}"
    if not candidate.exists():
        return candidate
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = parent / f"{photo_id}_{src.stem}_{stamp}"
    suffix = src.suffix
    idx = 1
    candidate = Path(f"{base}{suffix}")
    while candidate.exists():
        candidate = Path(f"{base}_{idx}{suffix}")
        idx += 1
    return candidate


def _remove_photo_thumbs(photo_id: int) -> int:
    thumb_dir = Path(settings.paths.thumb_dir)
    if not thumb_dir.exists():
        return 0
    removed = 0
    for path in thumb_dir.glob(f"{int(photo_id)}_*"):
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        except Exception:
            continue
    return removed


def _append_pre_deleted_manifest(records: list[dict]) -> None:
    if not records:
        return
    _PRE_DELETED_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = _PRE_DELETED_DIR / _PRE_DELETED_MANIFEST
    with manifest_path.open("a", encoding="utf-8") as fw:
        for rec in records:
            fw.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _normalize_new_stem(raw: str) -> str:
    stem = str(raw or "").strip().rstrip(".")
    if not stem:
        raise HTTPException(status_code=400, detail="新名称不能为空")
    if len(stem) > 120:
        raise HTTPException(status_code=400, detail="新名称过长（最多120字符）")
    if _INVALID_WIN_NAME_CHARS_RE.search(stem):
        raise HTTPException(status_code=400, detail="名称包含Windows非法字符")
    if "\\" in stem or "/" in stem:
        raise HTTPException(status_code=400, detail="名称不能包含路径分隔符")
    upper = stem.upper()
    if upper in _WIN_RESERVED_NAMES:
        raise HTTPException(status_code=400, detail="名称不能使用Windows保留字")
    return stem


def _format_file_mtime(path: Path) -> str:
    try:
        ts = float(path.stat().st_mtime)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def _cleanup_stale_download_tasks() -> None:
    now = time.time()
    stale_task_ids: list[str] = []
    with _DOWNLOAD_TASKS_LOCK:
        for task_id, task in _DOWNLOAD_TASKS.items():
            updated_at = float(task.get("updated_at_ts") or now)
            if now - updated_at > _DOWNLOAD_TASK_TTL_SECONDS:
                stale_task_ids.append(task_id)
        for task_id in stale_task_ids:
            task = _DOWNLOAD_TASKS.pop(task_id, None)
            if not task:
                continue
            zip_path = task.get("zip_path")
            if zip_path:
                try:
                    Path(zip_path).unlink(missing_ok=True)
                except Exception:
                    pass


def _set_download_task(task_id: str, **kwargs) -> None:
    with _DOWNLOAD_TASKS_LOCK:
        task = _DOWNLOAD_TASKS.get(task_id)
        if not task:
            return
        task.update(kwargs)
        task["updated_at_ts"] = time.time()


def _delete_download_task(task_id: str, zip_path: str | None = None) -> None:
    with _DOWNLOAD_TASKS_LOCK:
        _DOWNLOAD_TASKS.pop(task_id, None)
    if zip_path:
        try:
            Path(zip_path).unlink(missing_ok=True)
        except Exception:
            pass


def _build_download_zip(task_id: str, photo_ids: list[int]) -> None:
    try:
        placeholders = ",".join(["%s"] * len(photo_ids))
        rows = mysql.fetch_all(
            f"SELECT id, file_path FROM photos WHERE id IN ({placeholders}) AND status='active'",
            photo_ids,
        ) or []
        if not rows:
            _set_download_task(task_id, status="error", message="未找到可下载照片。")
            return

        export_dir = Path(settings.paths.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"photos_{ts}_{task_id[:8]}.zip"
        zip_path = export_dir / zip_name

        total = len(rows)
        processed = 0
        packed = 0
        skipped = 0
        _set_download_task(
            task_id,
            status="preparing",
            total_files=total,
            processed_files=0,
            packed_files=0,
            skipped_files=0,
            percent=0.0,
            message=f"正在打包（0/{total}）...",
        )

        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            used_names: set[str] = set()
            for row in rows:
                src = Path(row["file_path"])
                processed += 1
                if not src.exists() or not src.is_file():
                    skipped += 1
                else:
                    base_name = f"{row['id']}_{src.name}"
                    arc_name = base_name
                    idx = 1
                    while arc_name in used_names:
                        arc_name = f"{row['id']}_{src.stem}_{idx}{src.suffix}"
                        idx += 1
                    used_names.add(arc_name)
                    try:
                        zf.write(src, arcname=arc_name)
                        packed += 1
                    except Exception:
                        skipped += 1
                percent = round(processed * 100.0 / total, 2) if total else 100.0
                _set_download_task(
                    task_id,
                    status="preparing",
                    processed_files=processed,
                    packed_files=packed,
                    skipped_files=skipped,
                    percent=percent,
                    message=f"正在打包（{processed}/{total}）...",
                )

        if packed == 0:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
            _set_download_task(task_id, status="error", message="没有可打包的有效照片。")
            return

        size_bytes = zip_path.stat().st_size if zip_path.exists() else 0
        _set_download_task(
            task_id,
            status="ready",
            zip_path=str(zip_path),
            zip_name=zip_name,
            size_bytes=int(size_bytes),
            processed_files=processed,
            packed_files=packed,
            skipped_files=skipped,
            percent=100.0,
            message=f"打包完成，共 {packed} 张。",
        )
    except Exception as exc:
        _set_download_task(task_id, status="error", message=f"打包失败：{exc}")


def _get_download_task_for_policy(task_id: str, policy_id: str) -> dict:
    with _DOWNLOAD_TASKS_LOCK:
        task = _DOWNLOAD_TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="download task not found")
        if str(task.get("policy_id") or "") != str(policy_id or ""):
            raise HTTPException(status_code=404, detail="download task not found")
        return dict(task)


def _append_policy_where(sql: str, params: list, policy) -> str:
    if not policy or policy.is_admin:
        return sql
    roots = [str(root or "").replace("\\", "/").rstrip("/") for root in (policy.roots or []) if str(root or "").strip()]
    if not roots:
        sql += " AND 1=0"
        return sql
    clauses = []
    for root in roots:
        clauses.append("(REPLACE(file_path, '\\\\', '/') = %s OR REPLACE(file_path, '\\\\', '/') LIKE %s)")
        params.extend([root, root + "/%"])
    sql += " AND (" + " OR ".join(clauses) + ")"
    return sql


@router.get("/photos")
def list_photos(
    request: Request,
    date_from: str | None = None,
    date_to: str | None = None,
    face_min: int = Query(0, ge=0),
    path_like: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    policy = request.state.policy
    date_bounds(date_from, date_to)
    sql = """
    SELECT id, file_path, file_name, parent_dir_name, file_hash, file_size,
           COALESCE(exif_datetime, file_mtime) AS exif_datetime,
           file_mtime, width, height, gps_lat, gps_lon, face_count, status, created_at, updated_at
    FROM photos
    WHERE status='active'
    """
    params = []
    sql = _append_policy_where(sql, params, policy)
    if date_from:
        sql += " AND COALESCE(exif_datetime, file_mtime) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND COALESCE(exif_datetime, file_mtime) < %s"
        params.append(end_exclusive(date_to))
    if face_min:
        sql += " AND face_count >= %s"
        params.append(face_min)
    if path_like:
        sql += " AND file_path LIKE %s"
        params.append(f"%{path_like}%")
    sql += " ORDER BY COALESCE(exif_datetime, file_mtime) DESC,id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    return list(mysql.fetch_all(sql, params) or ())


def _get_photo_path(policy, photo_id: int) -> Path:
    row = ensure_photo_allowed(policy, photo_id)
    path = Path(row["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return path


def _ensure_thumb(photo_id: int, src: Path, size: int) -> Path:
    size = max(64, min(size, 1024))
    thumb_dir = Path(settings.paths.thumb_dir)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{photo_id}_{size}_v2.jpg"
    try:
        if thumb_path.exists() and thumb_path.stat().st_mtime >= src.stat().st_mtime:
            return thumb_path
    except Exception:
        pass
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((size, size))
        img.save(thumb_path, "JPEG", quality=85)
    return thumb_path


@router.get("/photos/{photo_id}/thumb")
def photo_thumb(request: Request, photo_id: int, size: int = Query(256, ge=64, le=1024)):
    src = _get_photo_path(request.state.policy, photo_id)
    thumb_path = _ensure_thumb(photo_id, src, size)
    return FileResponse(thumb_path)


@router.get("/photos/{photo_id}/file")
def photo_file(request: Request, photo_id: int):
    src = _get_photo_path(request.state.policy, photo_id)
    return FileResponse(src, filename=src.name)


@router.post("/photos/download")
def download_photos(payload: DownloadRequest, request: Request):
    if settings.paths.source_read_only:
        raise HTTPException(403, detail="v2源照片只读：请使用浏览器下载，不能修改或移动原照片")
    policy = request.state.policy
    photo_ids = _normalize_photo_ids(payload.photo_ids)
    if not photo_ids:
        raise HTTPException(status_code=400, detail="photo_ids required")
    dest_dir = Path(payload.dest_dir)
    if not dest_dir.exists() or not dest_dir.is_dir():
        raise HTTPException(status_code=400, detail="dest_dir not found")

    copied = []
    for photo_id in photo_ids:
        row = ensure_photo_allowed(policy, photo_id)
        src = Path(row["file_path"])
        if not src.exists():
            continue
        dest_path = dest_dir / src.name
        if dest_path.exists():
            stem = src.stem
            suffix = src.suffix
            i = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{i}{suffix}"
                i += 1
        shutil.copy2(src, dest_path)
        copied.append(str(dest_path))

    return {"count": len(copied), "files": copied}


@router.post("/photos/{photo_id}/rename")
def rename_photo(photo_id: int, payload: RenamePhotoRequest, request: Request):
    if settings.paths.source_read_only:
        raise HTTPException(403, detail="v2源照片只读：请使用浏览器下载，不能修改或移动原照片")
    policy = request.state.policy
    scan_state = scan_manager.status()
    if scan_state.get("running"):
        raise HTTPException(status_code=409, detail="扫描进行中，禁止重命名。")

    row = ensure_photo_allowed(policy, photo_id)
    src = Path(str(row.get("file_path") or ""))
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=404, detail="source file not found")
    if not _resolve_photo_root_info(src):
        raise HTTPException(status_code=400, detail="source file is outside configured photo roots")

    new_stem = _normalize_new_stem(payload.new_stem)
    old_name = src.name
    old_path = str(src)
    suffix = src.suffix or ""
    new_name = f"{new_stem}{suffix}"
    if new_name == old_name:
        return {
            "ok": True,
            "photo_id": int(photo_id),
            "unchanged": True,
            "old_name": old_name,
            "new_name": new_name,
            "old_path": old_path,
            "new_path": old_path,
        }

    dst = src.with_name(new_name)
    if dst.exists():
        raise HTTPException(status_code=409, detail="target file already exists")

    try:
        shutil.move(str(src), str(dst))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"rename file failed: {exc}")

    new_path = str(dst)
    file_mtime = _format_file_mtime(dst)
    parent_dir_name = dst.parent.name
    try:
        affected = int(
            mysql.rename_photo_file_record(
                int(photo_id),
                old_path=old_path,
                new_path=new_path,
                file_name=new_name,
                parent_dir_name=parent_dir_name,
                file_mtime=file_mtime,
            )
        )
        if affected <= 0:
            raise RuntimeError("photo record not updated")
    except Exception as exc:
        rollback_err = ""
        try:
            if dst.exists():
                shutil.move(str(dst), old_path)
        except Exception as rb_exc:
            rollback_err = f"；文件回滚失败: {rb_exc}"
        raise HTTPException(status_code=500, detail=f"update db failed: {exc}{rollback_err}")

    _remove_photo_thumbs(int(photo_id))
    return {
        "ok": True,
        "photo_id": int(photo_id),
        "old_name": old_name,
        "new_name": new_name,
        "old_path": old_path,
        "new_path": new_path,
    }


@router.post("/photos/trash")
def trash_photos(payload: TrashPhotosRequest, request: Request):
    if settings.paths.source_read_only:
        raise HTTPException(403, detail="v2源照片只读：请使用浏览器下载，不能修改或移动原照片")
    policy = request.state.policy
    scan_state = scan_manager.status()
    if scan_state.get("running"):
        raise HTTPException(status_code=409, detail="扫描进行中，请结束后再执行“移入回收箱”。")

    photo_ids = _normalize_photo_ids(payload.photo_ids)
    if not photo_ids:
        raise HTTPException(status_code=400, detail="photo_ids required")

    _PRE_DELETED_DIR.mkdir(parents=True, exist_ok=True)

    details: list[dict] = []
    moved_records: list[dict] = []
    manifest_records: list[dict] = []
    for pid in photo_ids:
        try:
            row = ensure_photo_allowed(policy, pid)
        except HTTPException as exc:
            details.append({"photo_id": pid, "ok": False, "message": str(exc.detail)})
            continue
        src = Path(str(row.get("file_path") or ""))
        if not src.exists() or not src.is_file():
            details.append({"photo_id": pid, "ok": False, "message": "源文件不存在"})
            continue
        root_info = _resolve_photo_root_info(src)
        if not root_info:
            details.append({"photo_id": pid, "ok": False, "message": "源文件不在已配置的照片目录内"})
            continue
        root_idx, _root_path, rel = root_info
        dst = _build_trash_dest_path(pid, src, root_idx, rel)
        try:
            shutil.move(str(src), str(dst))
            moved_records.append(
                {
                    "photo_id": pid,
                    "src_path": str(src),
                    "dst_path": str(dst),
                }
            )
            details.append(
                {
                    "photo_id": pid,
                    "ok": True,
                    "message": "已移入回收箱",
                    "src_path": str(src),
                    "trash_path": str(dst),
                }
            )
            manifest_records.append(
                {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "photo_id": pid,
                    "src_path": str(src),
                    "trash_path": str(dst),
                }
            )
        except Exception as exc:
            details.append({"photo_id": pid, "ok": False, "message": f"移动失败: {exc}"})

    moved_ids = [int(item["photo_id"]) for item in moved_records]
    processed_ids: list[int] = []
    db_deleted = 0
    db_error = ""
    if moved_ids:
        try:
            db_deleted = int(mysql.mark_photos_deleted_and_cleanup(moved_ids))
            processed_ids = moved_ids[:]
            _append_pre_deleted_manifest(manifest_records)
            for pid in processed_ids:
                _remove_photo_thumbs(pid)
        except Exception as exc:
            db_error = str(exc)
            rollback_errors = []
            rolled_back = 0
            for item in moved_records:
                src = Path(item["src_path"])
                dst = Path(item["dst_path"])
                try:
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dst), str(src))
                    rolled_back += 1
                except Exception as rollback_exc:
                    rollback_errors.append(f"ID {item['photo_id']}: {rollback_exc}")
            for item in details:
                if item.get("ok") is True:
                    item["ok"] = False
                    item["message"] = "数据库清理失败，文件移动已回滚"
            if rollback_errors:
                details.append({"photo_id": 0, "ok": False, "message": "；".join(rollback_errors)})
            moved_ids = []
            processed_ids = []

    failed = sum(1 for item in details if item.get("ok") is not True)
    result = {
        "ok": failed == 0,
        "requested": len(photo_ids),
        "processed": len(processed_ids),
        "processed_ids": processed_ids,
        "failed": failed,
        "db_deleted": db_deleted,
        "trash_dir": str(_PRE_DELETED_DIR),
        "details": details,
    }
    if db_error:
        result["message"] = f"数据库清理失败：{db_error}"
    return result


@router.post("/photos/download_zip_prepare")
def download_zip_prepare(payload: DownloadZipPrepareRequest, request: Request):
    policy = request.state.policy
    photo_ids = _normalize_photo_ids(payload.photo_ids)
    if not photo_ids:
        raise HTTPException(status_code=400, detail="photo_ids required")
    allowed_ids = []
    for pid in photo_ids:
        ensure_photo_allowed(policy, pid)
        allowed_ids.append(pid)

    _cleanup_stale_download_tasks()
    task_id = uuid.uuid4().hex
    with _DOWNLOAD_TASKS_LOCK:
        _DOWNLOAD_TASKS[task_id] = {
            "task_id": task_id,
            "status": "preparing",
            "message": "任务已创建，正在准备打包...",
            "policy_id": policy.id,
            "photo_ids": list(allowed_ids),
            "total_files": len(allowed_ids),
            "processed_files": 0,
            "packed_files": 0,
            "skipped_files": 0,
            "percent": 0.0,
            "zip_name": None,
            "size_bytes": 0,
            "zip_path": None,
            "created_at_ts": time.time(),
            "updated_at_ts": time.time(),
        }
    thread = threading.Thread(target=_build_download_zip, args=(task_id, allowed_ids), daemon=True)
    thread.start()
    return {"task_id": task_id, "status": "preparing", "message": "开始后台打包..."}


@router.get("/photos/download_zip_status")
def download_zip_status(task_id: str, request: Request):
    policy = request.state.policy
    _cleanup_stale_download_tasks()
    task = _get_download_task_for_policy(task_id, policy.id)
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "message": task.get("message"),
        "total_files": int(task.get("total_files") or 0),
        "processed_files": int(task.get("processed_files") or 0),
        "packed_files": int(task.get("packed_files") or 0),
        "skipped_files": int(task.get("skipped_files") or 0),
        "percent": float(task.get("percent") or 0.0),
        "zip_name": task.get("zip_name"),
        "size_bytes": int(task.get("size_bytes") or 0),
    }


@router.get("/photos/download_zip_file")
def download_zip_file(task_id: str, request: Request):
    policy = request.state.policy
    task = _get_download_task_for_policy(task_id, policy.id)
    for photo_id in task.get("photo_ids", []):
        ensure_photo_allowed(policy, photo_id)
    status = str(task.get("status") or "")
    if status != "ready":
        raise HTTPException(status_code=409, detail="zip not ready")
    zip_path = str(task.get("zip_path") or "")
    zip_name = str(task.get("zip_name") or "photos.zip")
    if not zip_path or not Path(zip_path).exists():
        _set_download_task(task_id, status="error", message="压缩包不存在，请重新打包。")
        raise HTTPException(status_code=404, detail="zip file not found")
    return FileResponse(
        zip_path,
        filename=zip_name,
        media_type="application/zip",
        background=BackgroundTask(_delete_download_task, task_id, zip_path),
    )


@router.get("/photos/choose_dir")
def choose_dir():
    # 禁用服务端 Tk 目录弹窗：该路径会引入 _tkinter/tcl86，已出现多次 python.exe 崩溃。
    raise HTTPException(
        status_code=410,
        detail="server-side directory dialog disabled; use web input selection instead",
    )
