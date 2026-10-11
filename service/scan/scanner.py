import hashlib
import logging
import calendar
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import ExifTags, Image, UnidentifiedImageError

from service.core.config import settings
from service.db import mysql
from service.face.engine import get_face_engine
from service.index.manager import get_index_manager, get_vision_index_manager
from service.utils.files import iter_image_files
from service.utils.pillow_heif_support import enable_heif_support
from service.vision.engine import get_vision_engine

log = logging.getLogger(__name__)
enable_heif_support(log)

EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}
GPS_TAGS = ExifTags.GPSTAGS
EXIF_DATETIME_TAGS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")
CACHEABLE_ERROR_MARKERS = (
    "cannot identify image file",
    "image file is truncated",
    "broken data stream",
    "decompression bomb",
)


def _norm_path(value) -> str:
    return str(Path(value)).replace("/", "\\").lower()


def _stat_signature(path: Path, stat_info=None) -> tuple[object, str, int]:
    stat = stat_info or path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return stat, mtime, int(stat.st_size)


def _short_error_message(exc: Exception, max_len: int = 240) -> str:
    msg = str(exc).strip().replace("\n", " ")
    return msg[:max_len]


def _is_cacheable_scan_error(exc: Exception) -> bool:
    if isinstance(exc, (UnidentifiedImageError, Image.DecompressionBombError)):
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in CACHEABLE_ERROR_MARKERS)


def _extract_exif_datetime(img: Image.Image) -> Optional[str]:
    try:
        exif = img.getexif()
        if not exif:
            return None
        for tag_name in EXIF_DATETIME_TAGS:
            tag = EXIF_TAGS.get(tag_name)
            if not tag or tag not in exif:
                continue
            parsed = _parse_exif_datetime_value(exif.get(tag))
            if parsed:
                return parsed
    except Exception:
        return None
    return None


def _parse_exif_datetime_value(value) -> Optional[str]:
    text = _to_text(value).strip().strip("\x00")
    if not text:
        return None
    text = text.replace("T", " ")
    text = " ".join(text.split())
    candidates = []
    if len(text) >= 19:
        candidates.append(text[:19])
    if len(text) >= 16:
        candidates.append(text[:16])
    candidates.append(text)
    for raw in candidates:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
    return None


def _infer_datetime_from_path(path_value: str, fallback_dt: Optional[datetime] = None) -> Optional[str]:
    try:
        parts = [str(p).strip() for p in Path(path_value).parts if str(p).strip()]
    except Exception:
        return None
    year_re = re.compile(r"^(19|20)\d{2}$")
    fallback = fallback_dt or datetime.now()
    for idx in range(len(parts) - 1):
        year_raw = parts[idx]
        month_raw = parts[idx + 1]
        if not year_re.match(year_raw):
            continue
        if not month_raw.isdigit():
            continue
        year = int(year_raw)
        month = int(month_raw)
        if month < 1 or month > 12:
            continue
        max_day = calendar.monthrange(year, month)[1]
        day = max(1, min(int(getattr(fallback, "day", 1) or 1), max_day))
        hour = max(0, min(int(getattr(fallback, "hour", 0) or 0), 23))
        minute = max(0, min(int(getattr(fallback, "minute", 0) or 0), 59))
        second = max(0, min(int(getattr(fallback, "second", 0) or 0), 59))
        try:
            dt = datetime(year, month, day, hour, minute, second)
        except Exception:
            continue
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return None


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return ""
    return str(value)


def _dms_to_decimal(dms) -> Optional[float]:
    if not dms or len(dms) < 3:
        return None
    try:
        degree = float(dms[0])
        minute = float(dms[1])
        second = float(dms[2])
        return degree + minute / 60.0 + second / 3600.0
    except Exception:
        return None


def _extract_exif_gps(img: Image.Image) -> tuple[Optional[float], Optional[float]]:
    try:
        exif = img.getexif()
        gps_tag = EXIF_TAGS.get("GPSInfo")
        if not gps_tag or gps_tag not in exif:
            return (None, None)
        gps_map = {}
        try:
            gps_ifd = exif.get_ifd(gps_tag)
        except Exception:
            gps_ifd = None
        if isinstance(gps_ifd, dict) and gps_ifd:
            for key, value in gps_ifd.items():
                gps_key = GPS_TAGS.get(key, key)
                gps_map[gps_key] = value
        if not gps_map:
            gps_info = exif.get(gps_tag)
            if hasattr(gps_info, "items"):
                for key, value in gps_info.items():
                    gps_key = GPS_TAGS.get(key, key)
                    gps_map[gps_key] = value
            elif isinstance(gps_info, dict):
                gps_map = gps_info
        if not gps_map:
            return (None, None)

        lat = _dms_to_decimal(gps_map.get("GPSLatitude"))
        lon = _dms_to_decimal(gps_map.get("GPSLongitude"))
        if lat is None or lon is None:
            return (None, None)
        lat_ref = _to_text(gps_map.get("GPSLatitudeRef")).upper()
        lon_ref = _to_text(gps_map.get("GPSLongitudeRef")).upper()
        if lat_ref == "S":
            lat = -abs(lat)
        if lon_ref == "W":
            lon = -abs(lon)
        return (round(lat, 7), round(lon, 7))
    except Exception:
        return (None, None)


def process_photo(
    path: Path,
    engine,
    index_manager,
    vision_engine=None,
    vision_index=None,
    full: bool = False,
    stat_info=None,
    mtime: str | None = None,
    size: int | None = None,
) -> dict:
    if stat_info is None or mtime is None or size is None:
        stat_info, mtime, size = _stat_signature(path, stat_info)

    file_name = path.name
    parent_dir_name = path.parent.name if path.parent else ""

    existing = mysql.get_photo_by_path(str(path))
    is_unchanged = (
        existing
        and str(existing.get("file_mtime")) == str(mtime)
        and int(existing.get("file_size", 0)) == int(size)
    )
    needs_datetime = bool(existing) and not existing.get("exif_datetime")
    existing_has_gps = bool(existing) and existing.get("gps_lat") is not None and existing.get("gps_lon") is not None
    existing_gps_checked = bool(existing) and int(existing.get("gps_checked") or 0) == 1
    needs_gps = bool(existing) and (not existing_has_gps) and (not existing_gps_checked)
    needs_vision = False
    if settings.vision.enabled:
        if existing:
            needs_vision = mysql.get_photo_embedding(int(existing["id"])) is None
        else:
            needs_vision = True
    if not full and is_unchanged and not needs_vision and not needs_datetime and not needs_gps:
        return {"status": "skipped", "path": str(path)}

    with Image.open(path) as img:
        exif_dt = _extract_exif_datetime(img)
        gps_lat, gps_lon = _extract_exif_gps(img)
        img.load()
        img = img.convert("RGB")
        if not exif_dt:
            inferred_dt = _infer_datetime_from_path(str(path), datetime.fromtimestamp(stat_info.st_mtime))
            if inferred_dt:
                exif_dt = inferred_dt
            else:
                exif_dt = mtime
        if gps_lat is None or gps_lon is None:
            if existing and is_unchanged and existing.get("gps_lat") is not None and existing.get("gps_lon") is not None:
                gps_lat = float(existing.get("gps_lat"))
                gps_lon = float(existing.get("gps_lon"))
        width, height = img.size

    do_face = full or not is_unchanged
    need_vision_embed = bool(settings.vision.enabled and vision_engine and vision_index and (needs_vision or full))
    need_image_bytes = bool(do_face or need_vision_embed)

    image_bytes = None
    if existing and is_unchanged and existing.get("file_hash"):
        file_hash = existing.get("file_hash")
    else:
        image_bytes = path.read_bytes()
        file_hash = hashlib.md5(image_bytes).hexdigest()

    if need_image_bytes and image_bytes is None:
        image_bytes = path.read_bytes()

    faces = []
    if do_face:
        try:
            faces = engine.detect_and_embed_bytes(image_bytes)
        except Exception as exc:
            log.warning("face engine not ready: %s", exc)
            faces = []

    if do_face and faces:
        embedding_ids = mysql.reserve_embedding_ids(len(faces))
        for i, face in enumerate(faces):
            face["embedding_id"] = embedding_ids[i]
            face["model_name"] = settings.face.engine

    meta = {
        "file_path": str(path),
        "file_name": file_name,
        "parent_dir_name": parent_dir_name,
        "file_hash": file_hash,
        "file_size": int(size),
        "file_mtime": mtime,
        "exif_datetime": exif_dt,
        "width": width,
        "height": height,
        "gps_lat": gps_lat,
        "gps_lon": gps_lon,
        "gps_checked": 1,
        "face_count": len(faces) if do_face else int(existing.get("face_count", 0)) if existing else 0,
    }

    photo_id = mysql.upsert_photo(meta)
    if do_face:
        mysql.delete_faces_by_photo(photo_id)
        mysql.insert_faces(photo_id, faces)

        if faces:
            vectors = [f["embedding"] for f in faces]
            ids = [f["embedding_id"] for f in faces]
            index_manager.add(vectors, ids)

    if need_vision_embed:
        try:
            vec = vision_engine.embed_image_bytes(image_bytes, mode="scene")
            emb_id = mysql.reserve_embedding_ids_vision(1)[0]
            mysql.upsert_photo_embedding(photo_id, emb_id, f"open_clip:{vision_engine.model_name}:{vision_engine.pretrained}")
            vision_index.add([vec], [emb_id])
        except Exception as exc:
            log.warning("vision embedding failed: %s", exc)

    return {"status": "processed", "path": str(path), "faces": len(faces)}


def scan_roots(
    roots,
    on_progress=None,
    should_pause=None,
    stop_event=None,
    batch_size: int = 100,
    idle_controller=None,
    full: bool = False,
    resume_from: str | None = None,
    start_count: int = 0,
):
    engine = get_face_engine()
    index_manager = get_index_manager()
    processed = 0
    seen_paths = []
    sync_missing = True
    missing_roots = [str(r) for r in roots if not Path(r).exists()]
    if missing_roots:
        sync_missing = False
        log.warning("skip delete sync because roots missing: %s", missing_roots)
    roots_for_scan = list(roots)
    resume_target_norm = None
    if resume_from:
        resume_path = Path(resume_from)
        resume_norm = _norm_path(resume_path)
        matched_idx = None
        for idx, root in enumerate(roots_for_scan):
            root_norm = _norm_path(root).rstrip("\\")
            if resume_norm == root_norm or resume_norm.startswith(root_norm + "\\"):
                matched_idx = idx
                break
        if matched_idx is None:
            log.warning("resume path not under roots, starting from beginning: %s", resume_from)
            resume_from = None
            start_count = 0
        elif not resume_path.exists():
            log.warning("resume path not found, starting from beginning: %s", resume_from)
            resume_from = None
            start_count = 0
        else:
            if matched_idx > 0:
                skipped_roots = roots_for_scan[:matched_idx]
                log.info("resume skips %s root(s) before target root: %s", len(skipped_roots), skipped_roots)
            roots_for_scan = roots_for_scan[matched_idx:]
            resume_target_norm = resume_norm
    resume_hit = resume_from is None
    resume_seek_start = time.time()
    resume_seek_skipped = 0
    resume_seek_fallback_files = 5000
    resume_seek_report_every = 1000
    if sync_missing:
        mysql.ensure_scan_seen_table()
        if resume_from:
            if mysql.count_scan_seen() == 0:
                sync_missing = False
                log.warning("resume requested but scan_seen empty; skip delete sync")
        else:
            mysql.clear_scan_seen()
    failed_signatures: dict[str, tuple[int, str]] = {}
    if not full:
        try:
            failed_signatures = mysql.load_scan_failed_signatures()
            if failed_signatures:
                log.info("loaded %s cached failed file signatures", len(failed_signatures))
        except Exception as exc:
            log.warning("load scan_failed signatures failed: %s", exc)
    vision_engine = None
    vision_index = None
    if settings.vision.enabled:
        try:
            vision_engine = get_vision_engine()
            vision_index = get_vision_index_manager()
        except Exception as exc:
            log.warning("vision engine init failed: %s", exc)

    for path in iter_image_files(roots_for_scan):
        if stop_event and stop_event.is_set():
            break
        if should_pause and should_pause():
            time.sleep(1)
            continue
        if idle_controller and not idle_controller.is_idle():
            idle_controller.wait_for_idle(stop_event)

        if not resume_hit:
            resume_seek_skipped += 1
            if _norm_path(path) == resume_target_norm:
                resume_hit = True
                continue

            if on_progress and resume_seek_skipped % resume_seek_report_every == 0:
                on_progress(
                    {
                        "processed": start_count,
                        "message": "seeking_resume",
                        "path": str(path),
                    }
                )

            if resume_seek_skipped >= resume_seek_fallback_files:
                log.warning(
                    "resume target not reached after skipping %s files (%.1fs); fallback to current position",
                    resume_seek_skipped,
                    time.time() - resume_seek_start,
                )
                resume_hit = True
            continue

        path_str = str(path)
        stat_info = None
        mtime = None
        size = None

        if sync_missing:
            seen_paths.append(path_str)
            if len(seen_paths) >= 500:
                mysql.add_scan_seen_paths(seen_paths)
                seen_paths.clear()

        if not full and path_str in failed_signatures:
            try:
                stat_info, mtime, size = _stat_signature(path)
                failed_size, failed_mtime = failed_signatures[path_str]
                if int(failed_size) == int(size) and str(failed_mtime) == str(mtime):
                    result = {"status": "failed_cached", "path": path_str}
                    processed += 1
                    if on_progress:
                        on_progress({"processed": processed + start_count, "message": result["status"], "path": path_str})
                    continue
            except OSError as exc:
                log.warning("failed to stat %s: %s", path, exc)

        try:
            result = process_photo(
                path,
                engine,
                index_manager,
                vision_engine=vision_engine,
                vision_index=vision_index,
                full=full,
                stat_info=stat_info,
                mtime=mtime,
                size=size,
            )
            if path_str in failed_signatures:
                mysql.clear_scan_failed_path(path_str)
                failed_signatures.pop(path_str, None)
        except Exception as exc:
            cacheable = _is_cacheable_scan_error(exc)
            if cacheable:
                try:
                    if stat_info is None or mtime is None or size is None:
                        stat_info, mtime, size = _stat_signature(path, stat_info)
                    mysql.upsert_scan_failed_path(
                        path_str,
                        int(size),
                        str(mtime),
                        type(exc).__name__,
                        _short_error_message(exc),
                    )
                    failed_signatures[path_str] = (int(size), str(mtime))
                except Exception as inner_exc:
                    log.warning("record scan_failed entry failed for %s: %s", path, inner_exc)
            log.warning("failed to process %s: %s", path, exc)
            result = {"status": "failed", "path": path_str}

        processed += 1
        if on_progress:
            on_progress({"processed": processed + start_count, "message": result.get("status"), "path": result.get("path")})
        if batch_size and processed % batch_size == 0:
            time.sleep(0.1)

    if sync_missing:
        if seen_paths:
            mysql.add_scan_seen_paths(seen_paths)
            seen_paths.clear()
        if stop_event and stop_event.is_set():
            log.info("scan stopped; skip delete sync")
        else:
            deleted = mysql.mark_missing_photos_deleted()
            mysql.cleanup_deleted_records()
            log.info("delete sync completed, marked %s photos deleted", deleted)
            mysql.clear_scan_seen()

    return processed + start_count


def repair_exif_datetime_by_dir(dir_path: str, on_progress=None) -> dict:
    target = str(Path(dir_path)).replace("/", "\\").rstrip("\\")
    if not target:
        return {"total": 0, "processed": 0, "updated": 0, "fallback_mtime": 0, "missing": 0, "failed": 0, "unchanged": 0}
    target_forward = target.replace("\\", "/")
    rows = mysql.fetch_all(
        """
        SELECT id, file_path, exif_datetime, file_mtime
        FROM photos
        WHERE status='active'
          AND (
            REPLACE(file_path, '\\\\', '/') = %s
            OR LEFT(REPLACE(file_path, '\\\\', '/'), CHAR_LENGTH(%s) + 1) = CONCAT(%s, '/')
          )
        ORDER BY id ASC
        """,
        (target_forward, target_forward, target_forward),
    ) or []

    total = len(rows)
    processed = 0
    updated = 0
    fallback_mtime = 0
    missing = 0
    failed = 0
    unchanged = 0

    def _emit_progress(current_path: str = "") -> None:
        if not callable(on_progress):
            return
        try:
            on_progress(
                {
                    "total": total,
                    "processed": processed,
                    "updated": updated,
                    "fallback_mtime": fallback_mtime,
                    "missing": missing,
                    "failed": failed,
                    "unchanged": unchanged,
                    "current_path": current_path,
                }
            )
        except Exception:
            pass

    _emit_progress()
    for row in rows:
        processed += 1
        photo_id = int(row.get("id") or 0)
        file_path = str(row.get("file_path") or "")
        old_exif = str(row.get("exif_datetime") or "")
        path = Path(file_path)
        try:
            if not path.exists() or not path.is_file():
                missing += 1
                continue
            stat = path.stat()
            file_mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            with Image.open(path) as img:
                exif_dt = _extract_exif_datetime(img)
            if not exif_dt:
                inferred_dt = _infer_datetime_from_path(file_path, datetime.fromtimestamp(stat.st_mtime))
                if inferred_dt:
                    exif_dt = inferred_dt
                else:
                    exif_dt = file_mtime
                    fallback_mtime += 1
            if old_exif == exif_dt and str(row.get("file_mtime") or "") == file_mtime:
                unchanged += 1
                continue
            mysql.execute(
                "UPDATE photos SET exif_datetime=%s, file_mtime=%s WHERE id=%s AND status='active'",
                (exif_dt, file_mtime, photo_id),
            )
            updated += 1
        except Exception as exc:
            failed += 1
            log.warning("repair exif failed for %s: %s", file_path, exc)
        finally:
            _emit_progress(file_path)
    return {
        "total": total,
        "processed": processed,
        "updated": updated,
        "fallback_mtime": fallback_mtime,
        "missing": missing,
        "failed": failed,
        "unchanged": unchanged,
    }


def count_image_files(roots):
    count = 0
    for _ in iter_image_files(roots):
        count += 1
    return count
