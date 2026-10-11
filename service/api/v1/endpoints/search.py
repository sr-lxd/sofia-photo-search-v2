from service.core.date_utils import date_bounds
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body
from collections import OrderedDict
from threading import Lock
from typing import List
from pathlib import Path
from datetime import datetime
import io
import hashlib
import math
import time
import uuid
from fastapi import Request
from PIL import Image
from service.core.acl import ensure_photo_allowed, filter_hits, filter_photo_rows
from service.face.engine import get_face_engine
from service.index.manager import get_index_manager, get_vision_index_manager
from service.vision.engine import get_vision_engine
from service.db import mysql
from service.models.schemas import SearchResponse, SearchHit

router = APIRouter()

SUPPORTED_ELEMENTS = {"face", "scene", "focus", "object", "building", "location", "text"}
SEARCH_BATCH_SIZE = 55
SEARCH_SESSION_TTL_SECONDS = 60 * 30
SEARCH_SESSION_MAX = 20
SEARCH_SESSION_BATCH_CACHE_MAX = 12
GLOBAL_SORT_MODES = {"face_count_asc", "face_count_desc", "face_count_exact"}
FACE_MODE_DEFAULT = "or"
ELEMENT_MODE_DEFAULT = "and"
FOCUS_MODE_DEFAULT = "center"
FOCUS_MODE_ALLOWED = ("center", "vertical", "cross", "horizontal")
FACE_AND_MATCH_MIN_SCORE = 0.12
FACE_AND_MATCH_MIN_SCORE_MANY = 0.08
FACE_MATCH_MIN_RATIO = 0.72
FACE_MATCH_MIN_ABS = 0.10
VISION_MATCH_MIN_RATIO = 0.78
VISION_MATCH_MIN_ABS = 0.12
_SEARCH_SESSION_LOCK = Lock()
_SEARCH_SESSIONS: "OrderedDict[str, dict]" = OrderedDict()
_POLICY_SCOPE_CACHE_LOCK = Lock()
_POLICY_SCOPE_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_POLICY_SCOPE_CACHE_MAX = 16
_POLICY_SCOPE_CACHE_TTL_SECONDS = 60 * 30
_TEXT_QUERY_CACHE_LOCK = Lock()
_TEXT_QUERY_CACHE: "OrderedDict[tuple, dict]" = OrderedDict()
_TEXT_QUERY_CACHE_MAX = 24
_TEXT_QUERY_CACHE_TTL_SECONDS = 60 * 15


def _serialize_hit(hit: SearchHit) -> dict:
    if hasattr(hit, "model_dump"):
        return hit.model_dump()
    return hit.dict()


def _fill_face_counts_for_rows(rows: list[dict]) -> None:
    if not rows:
        return
    missing_photo_ids = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("photo_id")
        if pid is None or row.get("face_count") is not None:
            continue
        try:
            pid_int = int(pid)
        except Exception:
            continue
        if pid_int > 0:
            missing_photo_ids.append(pid_int)
    if not missing_photo_ids:
        return
    face_counts = mysql.fetch_face_counts_by_photo_ids(missing_photo_ids)
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = row.get("photo_id")
        if pid is None or row.get("face_count") is not None:
            continue
        try:
            pid_int = int(pid)
        except Exception:
            continue
        if pid_int > 0:
            row["face_count"] = int(face_counts.get(pid_int, 0))


def _fill_face_counts_for_hits(results: list[SearchHit]) -> list[SearchHit]:
    if not results:
        return results
    missing_photo_ids = []
    for hit in results:
        if hit.photo_id is None or hit.face_count is not None:
            continue
        pid_int = int(hit.photo_id)
        if pid_int > 0:
            missing_photo_ids.append(pid_int)
    if not missing_photo_ids:
        return results
    face_counts = mysql.fetch_face_counts_by_photo_ids(missing_photo_ids)
    for hit in results:
        if hit.photo_id is None or hit.face_count is not None:
            continue
        pid_int = int(hit.photo_id)
        if pid_int > 0:
            hit.face_count = int(face_counts.get(pid_int, 0))
    return results


def _normalize_sort_mode(value: str | None) -> str | None:
    mode = (value or "").strip().lower()
    return mode if mode in GLOBAL_SORT_MODES else None


def _normalize_face_count_exact(value) -> int | None:
    if value is None:
        return None
    try:
        num = int(value)
    except Exception:
        return None
    return max(0, num)


def _parse_exif_sort_ts(value) -> float:
    if value is None:
        return float("-inf")
    text = str(value).strip()
    if not text:
        return float("-inf")
    try:
        return datetime.fromisoformat(text.replace(" ", "T")).timestamp()
    except Exception:
        return float("-inf")


def _sort_rows_by_face_count(rows: list[dict], sort_mode: str) -> None:
    reverse_count = sort_mode == "face_count_desc"

    def _key(row: dict):
        face_count_raw = row.get("face_count") if isinstance(row, dict) else None
        face_count_ok = isinstance(face_count_raw, (int, float)) and float(face_count_raw) >= 0
        face_count = int(face_count_raw) if face_count_ok else 0
        count_key = -face_count if reverse_count else face_count
        exif_key = -_parse_exif_sort_ts(row.get("exif_datetime") if isinstance(row, dict) else None)
        file_key = str((row or {}).get("file_path") or "")
        # Known face_count first; ties and unknown face_count group both use EXIF descending.
        return (0 if face_count_ok else 1, count_key, exif_key, file_key)

    rows.sort(key=_key)


def _get_rows_for_mode(state: dict, sort_mode: str | None, *, face_count_exact: int | None = None) -> list[dict]:
    base_rows = state.get("results") or []
    if sort_mode is None:
        return base_rows
    sorted_cache = state.get("sorted_results_cache")
    if not isinstance(sorted_cache, dict):
        sorted_cache = {}
        state["sorted_results_cache"] = sorted_cache
    face_count_exact = _normalize_face_count_exact(face_count_exact)
    cache_key = (sort_mode, face_count_exact) if sort_mode == "face_count_exact" else sort_mode
    cached = sorted_cache.get(cache_key)
    if isinstance(cached, list):
        return cached
    _fill_face_counts_for_rows(base_rows)
    if sort_mode == "face_count_exact":
        target = 0 if face_count_exact is None else int(face_count_exact)
        sorted_rows = []
        for row in base_rows:
            if not isinstance(row, dict):
                continue
            face_count_raw = row.get("face_count")
            face_count_ok = isinstance(face_count_raw, (int, float)) and float(face_count_raw) >= 0
            face_count = int(face_count_raw) if face_count_ok else 0
            if face_count == target:
                sorted_rows.append(row)

        def _exact_key(row: dict):
            exif_key = -_parse_exif_sort_ts(row.get("exif_datetime") if isinstance(row, dict) else None)
            file_key = str((row or {}).get("file_path") or "")
            return (exif_key, file_key)

        sorted_rows.sort(key=_exact_key)
    else:
        sorted_rows = list(base_rows)
        _sort_rows_by_face_count(sorted_rows, sort_mode)
    sorted_cache[cache_key] = sorted_rows
    return sorted_rows


def _get_face_count_max_for_state(state: dict) -> int:
    cached = state.get("face_count_max")
    if isinstance(cached, int) and cached >= 0:
        return cached
    rows = state.get("results") or []
    _fill_face_counts_for_rows(rows)
    max_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("face_count")
        if isinstance(raw, (int, float)) and float(raw) >= 0:
            count = int(raw)
        else:
            count = 0
        if count > max_count:
            max_count = count
    state["face_count_max"] = int(max_count)
    return int(max_count)


def _cleanup_search_sessions(now_ts: float | None = None) -> None:
    now_ts = now_ts if now_ts is not None else time.time()
    expired = [
        sid
        for sid, state in list(_SEARCH_SESSIONS.items())
        if now_ts - float(state.get("updated_at") or 0.0) > SEARCH_SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _SEARCH_SESSIONS.pop(sid, None)
    while len(_SEARCH_SESSIONS) > SEARCH_SESSION_MAX:
        _SEARCH_SESSIONS.popitem(last=False)


def _save_search_session(
    stage: int,
    results: list[SearchHit],
    policy_id: str,
    debug: dict | None = None,
) -> str:
    now_ts = time.time()
    state = {
        "stage": int(stage),
        "total": len(results),
        "policy_id": str(policy_id or ""),
        "results": [_serialize_hit(hit) for hit in results],
        "debug": dict(debug) if isinstance(debug, dict) else None,
        "batch_cache": OrderedDict(),
        "sorted_results_cache": {},
        "created_at": now_ts,
        "updated_at": now_ts,
    }
    search_id = uuid.uuid4().hex
    with _SEARCH_SESSION_LOCK:
        _cleanup_search_sessions(now_ts)
        _SEARCH_SESSIONS[search_id] = state
    return search_id


def _get_search_session(search_id: str, policy_id: str) -> dict | None:
    if not search_id:
        return None
    now_ts = time.time()
    with _SEARCH_SESSION_LOCK:
        _cleanup_search_sessions(now_ts)
        state = _SEARCH_SESSIONS.get(search_id)
        if not state:
            return None
        if str(state.get("policy_id") or "") != str(policy_id or ""):
            return None
        state["updated_at"] = now_ts
        _SEARCH_SESSIONS.move_to_end(search_id, last=True)
        return state


def _build_search_batch_response(
    search_id: str,
    state: dict,
    batch: int,
    sort_mode: str | None = None,
    face_count_exact: int | None = None,
) -> SearchResponse:
    normalized_sort_mode = _normalize_sort_mode(sort_mode)
    normalized_face_count_exact = _normalize_face_count_exact(face_count_exact)
    if normalized_sort_mode != "face_count_exact":
        normalized_face_count_exact = None
    mode_key = (
        f"{normalized_sort_mode}:{normalized_face_count_exact}"
        if normalized_sort_mode == "face_count_exact"
        else (normalized_sort_mode or "default")
    )
    stage = int(state.get("stage") or 3)
    with _SEARCH_SESSION_LOCK:
        source_rows = _get_rows_for_mode(
            state,
            normalized_sort_mode,
            face_count_exact=normalized_face_count_exact,
        )
        total = len(source_rows)
        total_batches = max(1, math.ceil(total / SEARCH_BATCH_SIZE))
        safe_batch = max(1, min(int(batch), total_batches))
        start = (safe_batch - 1) * SEARCH_BATCH_SIZE
        end = start + SEARCH_BATCH_SIZE
        batch_cache = state.get("batch_cache")
        if not isinstance(batch_cache, OrderedDict):
            batch_cache = OrderedDict()
            state["batch_cache"] = batch_cache
        cache_key = (mode_key, safe_batch)
        rows = batch_cache.get(cache_key)
        if rows is None:
            rows = source_rows[start:end]
            batch_cache[cache_key] = rows
        batch_cache.move_to_end(cache_key, last=True)
        while len(batch_cache) > SEARCH_SESSION_BATCH_CACHE_MAX:
            batch_cache.popitem(last=False)
        debug_raw = state.get("debug") if isinstance(state.get("debug"), dict) else None
        face_count_max = int(_get_face_count_max_for_state(state))
    _fill_face_counts_for_rows(rows)
    results = [SearchHit(**row) for row in rows]
    debug = dict(debug_raw) if isinstance(debug_raw, dict) else {}
    debug["face_count_max"] = face_count_max
    if normalized_sort_mode == "face_count_exact":
        debug["face_count_exact"] = int(normalized_face_count_exact or 0)
    if not debug:
        debug = None
    return SearchResponse(
        stage=stage,
        total=total,
        results=results,
        debug=debug,
        search_id=search_id,
        batch=safe_batch,
        batch_size=SEARCH_BATCH_SIZE,
        total_batches=total_batches,
        has_prev=safe_batch > 1,
        has_next=safe_batch < total_batches,
    )


def _new_search_response(
    stage: int,
    results: list[SearchHit],
    policy_id: str,
    batch: int = 1,
    debug: dict | None = None,
    sort_mode: str | None = None,
    face_count_exact: int | None = None,
) -> SearchResponse:
    search_id = _save_search_session(stage=stage, results=results, policy_id=policy_id, debug=debug)
    state = _get_search_session(search_id, policy_id)
    if not state:
        return SearchResponse(
            stage=int(stage),
            total=len(results),
            results=_fill_face_counts_for_hits(results),
            debug=dict(debug) if isinstance(debug, dict) else None,
        )
    return _build_search_batch_response(
        search_id=search_id,
        state=state,
        batch=batch,
        sort_mode=sort_mode,
        face_count_exact=face_count_exact,
    )


def _pick_best_face(faces: list) -> dict | None:
    if not faces:
        return None
    def _score(face: dict):
        score = face.get("quality_score") or 0.0
        bbox = face.get("bbox") or [0, 0, 0, 0]
        area = max(0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        return (score, area)
    return max(faces, key=_score)


def _distance_score(distance_km: float, radius_km: float) -> float:
    safe_radius = max(0.001, float(radius_km))
    value = 1.0 - float(distance_km) / safe_radius
    return max(0.0, min(1.0, value))


def _normalize_mode(value: str | None, default: str = "or") -> str:
    mode = (value or default).strip().lower()
    return mode if mode in ("and", "or") else default


def _normalize_focus_modes(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for raw in values or []:
        mode = str(raw or "").strip().lower()
        if mode in FOCUS_MODE_ALLOWED and mode not in normalized:
            normalized.append(mode)
    return normalized or [FOCUS_MODE_DEFAULT]


def _resolve_face_required_match_count(
    query_face_count: int,
    *,
    face_mode: str,
    min_match_faces: int | None,
) -> int:
    total = max(0, int(query_face_count or 0))
    if total <= 0:
        return 0
    if min_match_faces is not None:
        requested = max(1, int(min_match_faces))
        return min(requested, total)
    mode = _normalize_mode(face_mode, default=FACE_MODE_DEFAULT)
    if mode == "and":
        return min(2, total)
    return 1


def _prune_scores_by_best(score_map: dict[int, float], *, min_ratio: float, min_abs: float) -> dict[int, float]:
    if not score_map:
        return {}
    best = max(float(v) for v in score_map.values())
    threshold = max(float(min_abs), float(best) * float(min_ratio))
    return {int(pid): float(score) for pid, score in score_map.items() if float(score) >= threshold}


def _center_pad_image_bytes(image_bytes: bytes, scale: float) -> bytes | None:
    if not image_bytes:
        return None
    try:
        src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None
    w, h = src.size
    if w <= 1 or h <= 1:
        return None
    safe_scale = max(1.01, float(scale))
    out_w = max(w + 2, int(round(w * safe_scale)))
    out_h = max(h + 2, int(round(h * safe_scale)))
    # Neutral gray canvas keeps contrast stable while giving detector more context.
    canvas = Image.new("RGB", (out_w, out_h), (128, 128, 128))
    canvas.paste(src, ((out_w - w) // 2, (out_h - h) // 2))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _collect_query_face_embeddings(image_bytes_list: list[bytes]) -> list:
    engine = get_face_engine()
    embeddings = []
    for image_bytes in image_bytes_list:
        faces = engine.detect_and_embed_bytes(image_bytes)
        if not faces:
            # Some query images are tightly cropped face thumbnails.
            # Retry with centered padding to improve detector recall.
            for scale in (2.0, 3.0):
                padded = _center_pad_image_bytes(image_bytes, scale)
                if not padded:
                    continue
                faces = engine.detect_and_embed_bytes(padded)
                if faces:
                    break
        for face in faces:
            emb = face.get("embedding")
            if emb is not None:
                embeddings.append(emb)
    return embeddings


def _search_face_scores(
    query_embeddings: list,
    *,
    topk: int,
    date_from: str | None,
    date_to: str | None,
    photo_ids: list[int] | None = None,
    candidate_embedding_ids: list[int] | None = None,
    face_mode: str = FACE_MODE_DEFAULT,
    min_match_faces: int | None = None,
    prune_scores: bool = True,
    min_ratio: float = FACE_MATCH_MIN_RATIO,
    min_abs: float = FACE_MATCH_MIN_ABS,
) -> tuple[dict[int, float], dict[int, dict], dict]:
    meta = {
        "query_face_count": max(0, len(query_embeddings or [])),
        "min_match_faces_requested": int(min_match_faces) if min_match_faces is not None else None,
        "min_match_faces_effective": 0,
    }
    if not query_embeddings:
        return {}, {}, meta

    index = get_index_manager()
    face_mode = _normalize_mode(face_mode, default=FACE_MODE_DEFAULT)
    subset_ids = None
    subset_vecs = None
    if candidate_embedding_ids is not None:
        subset_ids, subset_vecs = index.prepare_subset(candidate_embedding_ids)
        if not subset_ids or subset_vecs.size == 0:
            return {}, {}, meta
        topk = min(max(1, int(topk)), len(subset_ids))
    query_hits_list = []
    all_embedding_ids = []
    for query_embedding in query_embeddings:
        if subset_ids is not None and subset_vecs is not None:
            hits = index.search_prepared_subset(query_embedding, subset_ids, subset_vecs, topk=topk)
        else:
            hits = index.search(query_embedding, topk=topk)
        query_hits_list.append(hits)
        for hid, _ in hits:
            if hid >= 0:
                all_embedding_ids.append(int(hid))
    all_embedding_ids = list(dict.fromkeys(all_embedding_ids))
    if not all_embedding_ids:
        return {}, {}, meta

    rows = mysql.fetch_photos_by_embedding_ids(
        all_embedding_ids,
        date_from=date_from,
        date_to=date_to,
        photo_ids=photo_ids,
    )
    if not rows:
        return {}, {}, meta

    rows_by_embedding = {}
    for row in rows:
        eid = int(row["embedding_id"])
        rows_by_embedding.setdefault(eid, []).append(row)

    query_photo_scores = []
    photo_info = {}
    photo_best_row_score = {}
    for hits in query_hits_list:
        photo_scores = {}
        for hid, raw_score in hits:
            if hid < 0:
                continue
            score = float(raw_score)
            related_rows = rows_by_embedding.get(int(hid)) or []
            for row in related_rows:
                pid = int(row["photo_id"])
                if score > photo_scores.get(pid, -1.0):
                    photo_scores[pid] = score
                if score > photo_best_row_score.get(pid, -1.0):
                    photo_best_row_score[pid] = score
                    photo_info[pid] = row
        if prune_scores:
            photo_scores = _prune_scores_by_best(
                photo_scores,
                min_ratio=min_ratio,
                min_abs=min_abs,
            )
        else:
            photo_scores = {int(pid): float(score) for pid, score in photo_scores.items()}
        query_photo_scores.append(photo_scores)

    if not query_photo_scores:
        return {}, {}, meta

    required_match_count = _resolve_face_required_match_count(
        len(query_photo_scores),
        face_mode=face_mode,
        min_match_faces=min_match_faces,
    )
    meta["min_match_faces_effective"] = int(required_match_count)

    if required_match_count > 1:
        min_required = FACE_AND_MATCH_MIN_SCORE_MANY if len(query_photo_scores) >= 3 else FACE_AND_MATCH_MIN_SCORE
        matched_scores = {}
        for score_map in query_photo_scores:
            for pid, score in score_map.items():
                if score >= min_required:
                    matched_scores.setdefault(pid, []).append(score)
        face_scores = {}
        for pid, scores in matched_scores.items():
            if len(scores) < required_match_count:
                continue
            top_scores = sorted(scores, reverse=True)[:required_match_count]
            face_scores[pid] = sum(top_scores) / required_match_count
        return face_scores, photo_info, meta

    face_scores = {}
    for score_map in query_photo_scores:
        for pid, score in score_map.items():
            if score > face_scores.get(pid, -1.0):
                face_scores[pid] = score
    return face_scores, photo_info, meta


def _to_int_id_set(values) -> set[int]:
    ids = set()
    if values is None:
        return ids
    for raw in values:
        try:
            pid = int(raw)
        except Exception:
            continue
        if pid > 0:
            ids.add(pid)
    return ids


def _normalize_element_score_maps(
    element_scores: dict[str, dict[int, float]],
    element_keys: list[str],
) -> dict[str, dict[int, float]]:
    normalized_scores: dict[str, dict[int, float]] = {}
    for key in element_keys:
        raw_map = element_scores.get(key) or {}
        norm_map: dict[int, float] = {}
        for raw_pid, raw_score in raw_map.items():
            try:
                pid = int(raw_pid)
            except Exception:
                continue
            if pid <= 0:
                continue
            score = float(raw_score)
            if score > norm_map.get(pid, -1.0):
                norm_map[pid] = score
        normalized_scores[key] = norm_map
    return normalized_scores


def _build_search_debug_payload(
    element_scores: dict[str, dict[int, float]],
    elem_list: list[str],
    *,
    element_mode: str = ELEMENT_MODE_DEFAULT,
    candidate_ids: set[int] | list[int] | None = None,
    combined_count: int | None = None,
    face_mode: str | None = None,
    face_prune_scores: bool | None = None,
    text_mode: str | None = None,
    text_scope: str | None = None,
    extra: dict | None = None,
) -> dict:
    element_keys = [k for k in elem_list if k in element_scores]
    normalized_scores = _normalize_element_score_maps(element_scores, element_keys)
    mode = _normalize_mode(element_mode, default=ELEMENT_MODE_DEFAULT)
    candidate_set = _to_int_id_set(candidate_ids) if candidate_ids is not None else None

    element_counts = {}
    for key in element_keys:
        element_counts[key] = len((normalized_scores.get(key) or {}).keys())

    if not element_keys:
        computed_ids = set()
    elif mode == "and":
        computed_ids = None
        for key in element_keys:
            key_ids = set((normalized_scores.get(key) or {}).keys())
            computed_ids = key_ids if computed_ids is None else (computed_ids & key_ids)
        computed_ids = computed_ids or set()
    else:
        computed_ids = set()
        for key in element_keys:
            computed_ids |= set((normalized_scores.get(key) or {}).keys())

    if candidate_set is not None:
        computed_ids &= candidate_set

    payload: dict = {
        "elements": element_keys,
        "element_mode": mode,
        "element_counts": element_counts,
        "computed_count": len(computed_ids),
    }
    if candidate_set is not None:
        payload["candidate_count"] = len(candidate_set)
    if combined_count is not None:
        payload["combined_count"] = int(combined_count)
    if "face" in normalized_scores and "text" in normalized_scores:
        overlap_ids = set((normalized_scores.get("face") or {}).keys()) & set((normalized_scores.get("text") or {}).keys())
        if candidate_set is not None:
            overlap_ids &= candidate_set
        payload["face_text_overlap"] = len(overlap_ids)
    if face_mode is not None:
        payload["face_mode"] = _normalize_mode(face_mode, default=FACE_MODE_DEFAULT)
    if face_prune_scores is not None:
        payload["face_prune_scores"] = bool(face_prune_scores)
    if text_mode is not None:
        payload["text_mode"] = _normalize_mode(text_mode, default="and")
    if text_scope in ("parent", "any"):
        payload["text_scope"] = text_scope
    if isinstance(extra, dict):
        for key, value in extra.items():
            payload[key] = value
    return payload


def _debug_extra_face_text_overlap(
    element_scores: dict[str, dict[int, float]],
    *,
    text_query: str | None,
    date_from: str | None,
    date_to: str | None,
    text_scope: str,
    text_mode: str,
    candidate_ids: set[int] | list[int] | None = None,
) -> dict:
    result = {}
    face_scores = element_scores.get("face") or {}
    text_scores = element_scores.get("text") or {}
    face_ids = sorted(_to_int_id_set(face_scores.keys()))
    text_ids = sorted(_to_int_id_set(text_scores.keys()))
    result["face_sample_ids"] = face_ids[:5]
    result["text_sample_ids"] = text_ids[:5]
    if not text_query or not face_ids:
        result["face_text_overlap_db"] = 0
        return result
    if candidate_ids is not None:
        face_id_set = set(face_ids) & _to_int_id_set(candidate_ids)
        face_ids = sorted(face_id_set)
    if not face_ids:
        result["face_text_overlap_db"] = 0
        return result
    max_ids = 5000
    sampled = len(face_ids) > max_ids
    check_ids = face_ids[:max_ids]
    try:
        rows = mysql.fetch_photos_by_text_query(
            text_query,
            date_from=date_from,
            date_to=date_to,
            photo_ids=check_ids,
            scope=text_scope,
            query_mode=text_mode,
        )
        result["face_text_overlap_db"] = len(rows)
        if sampled:
            result["face_text_overlap_db_sampled"] = True
    except Exception as exc:
        result["face_text_overlap_db_error"] = str(exc)
    return result


def _combine_element_scores(
    element_scores: dict[str, dict[int, float]],
    elem_list: list[str],
    *,
    element_mode: str = ELEMENT_MODE_DEFAULT,
    candidate_ids: set[int] | None = None,
) -> list[tuple[int, float]]:
    element_keys = [k for k in elem_list if k in element_scores]
    if not element_keys:
        return []

    normalized_scores = _normalize_element_score_maps(element_scores, element_keys)

    mode = _normalize_mode(element_mode, default=ELEMENT_MODE_DEFAULT)
    if mode == "and":
        for key in element_keys:
            if not normalized_scores.get(key):
                return []
        photo_ids = set(normalized_scores[element_keys[0]].keys())
        for key in element_keys[1:]:
            photo_ids &= set(normalized_scores[key].keys())
    else:
        photo_ids = set()
        for key in element_keys:
            score_map = normalized_scores.get(key) or {}
            photo_ids |= set(score_map.keys())

    if candidate_ids is not None:
        photo_ids &= _to_int_id_set(candidate_ids)
    if not photo_ids:
        return []

    combined = []
    for pid in photo_ids:
        matched_scores = [float(normalized_scores[key][pid]) for key in element_keys if pid in normalized_scores[key]]
        if not matched_scores:
            continue
        score = sum(matched_scores) / len(matched_scores)
        combined.append((int(pid), float(score)))
    combined.sort(key=lambda x: x[1], reverse=True)
    return combined


def _load_photo_bytes_from_ids(policy, photo_ids: list[int]) -> list[bytes]:
    if not photo_ids:
        return []
    ids = [int(pid) for pid in dict.fromkeys(photo_ids) if int(pid) > 0]
    if not ids:
        return []
    bytes_list = []
    for pid in ids:
        row = ensure_photo_allowed(policy, pid)
        file_path = row.get("file_path")
        try:
            image_bytes = Path(file_path).read_bytes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"failed to read photo_id {pid}: {exc}")
        bytes_list.append(image_bytes)
    return bytes_list


def _build_query_image_bytes(policy, uploaded_bytes: list[bytes], standard_photo_ids: list[int] | None) -> list[bytes]:
    # Merge uploaded and selected standard photos into one unified query set.
    all_bytes = list(uploaded_bytes or [])
    all_bytes.extend(_load_photo_bytes_from_ids(policy, standard_photo_ids or []))
    merged = []
    seen = set()
    for image_bytes in all_bytes:
        digest = hashlib.sha1(image_bytes).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        merged.append(image_bytes)
    return merged


def _get_face_index_ntotal() -> int:
    try:
        index = get_index_manager()
        index.load()
        raw = getattr(index, "_index", None)
        if raw is None:
            return 0
        return int(getattr(raw, "ntotal", 0))
    except Exception:
        return 0


def _get_policy_roots(policy) -> list[str] | None:
    if not policy or bool(getattr(policy, "is_admin", False)):
        return None
    roots: list[str] = []
    seen: set[str] = set()
    for raw in getattr(policy, "roots", []) or []:
        text = str(raw or "").replace("\\", "/").rstrip("/")
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        roots.append(text)
    return roots


def _get_policy_candidate_photo_ids(
    policy,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[int] | None:
    return _get_policy_search_scope(policy, date_from=date_from, date_to=date_to).get("photo_ids")


def _cleanup_policy_scope_cache(now_ts: float | None = None) -> None:
    now_ts = now_ts if now_ts is not None else time.time()
    expired = [
        key
        for key, state in list(_POLICY_SCOPE_CACHE.items())
        if now_ts - float(state.get("updated_at") or 0.0) > _POLICY_SCOPE_CACHE_TTL_SECONDS
    ]
    for key in expired:
        _POLICY_SCOPE_CACHE.pop(key, None)
    while len(_POLICY_SCOPE_CACHE) > _POLICY_SCOPE_CACHE_MAX:
        _POLICY_SCOPE_CACHE.popitem(last=False)


def _build_policy_scope_cache_key(policy, date_from: str | None = None, date_to: str | None = None):
    roots = tuple(_get_policy_roots(policy) or ())
    return (
        str(getattr(policy, "id", "") or ""),
        roots,
        str(date_from or ""),
        str(date_to or ""),
    )


def _get_policy_search_scope(
    policy,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    need_face: bool = False,
    need_vision: bool = False,
    warm_face_subset: bool = False,
    warm_vision_subset: bool = False,
) -> dict:
    roots = _get_policy_roots(policy)
    if roots is None:
        return {
            "photo_ids": None,
            "photo_id_set": None,
            "face_embedding_ids": None,
            "photo_embedding_ids": None,
        }
    cache_key = _build_policy_scope_cache_key(policy, date_from=date_from, date_to=date_to)
    now_ts = time.time()
    with _POLICY_SCOPE_CACHE_LOCK:
        _cleanup_policy_scope_cache(now_ts)
        cached = _POLICY_SCOPE_CACHE.get(cache_key)
        if cached:
            _POLICY_SCOPE_CACHE.move_to_end(cache_key, last=True)
    entry = dict(cached) if isinstance(cached, dict) else {
        "photo_ids": None,
        "photo_id_set": None,
        "face_embedding_ids": None,
        "photo_embedding_ids": None,
        "face_subset_warmed": False,
        "vision_subset_warmed": False,
    }

    photo_ids = entry.get("photo_ids")
    if photo_ids is None:
        photo_ids = mysql.fetch_active_photo_ids_by_roots(roots, date_from=date_from, date_to=date_to)
        entry["photo_ids"] = photo_ids
        entry["photo_id_set"] = set(photo_ids)

    if need_face and entry.get("face_embedding_ids") is None:
        entry["face_embedding_ids"] = mysql.fetch_face_embedding_ids_by_photo_ids(photo_ids)
    if need_vision and entry.get("photo_embedding_ids") is None:
        entry["photo_embedding_ids"] = mysql.fetch_photo_embedding_ids_by_photo_ids(photo_ids)

    if warm_face_subset and not entry.get("face_subset_warmed"):
        get_index_manager().prepare_subset(entry.get("face_embedding_ids") or [])
        entry["face_subset_warmed"] = True
    if warm_vision_subset and not entry.get("vision_subset_warmed"):
        get_vision_index_manager().prepare_subset(entry.get("photo_embedding_ids") or [])
        entry["vision_subset_warmed"] = True

    entry["updated_at"] = now_ts
    with _POLICY_SCOPE_CACHE_LOCK:
        _POLICY_SCOPE_CACHE[cache_key] = entry
        _POLICY_SCOPE_CACHE.move_to_end(cache_key, last=True)
        _cleanup_policy_scope_cache(now_ts)
    return entry


def warm_policy_search_cache(policy) -> None:
    if not policy or bool(getattr(policy, "is_admin", False)):
        return
    try:
        _get_policy_search_scope(
            policy,
            need_face=True,
            need_vision=True,
            warm_face_subset=True,
            warm_vision_subset=True,
        )
    except Exception:
        pass


def _cleanup_text_query_cache(now_ts: float | None = None) -> None:
    now_ts = now_ts if now_ts is not None else time.time()
    expired = [
        key
        for key, state in list(_TEXT_QUERY_CACHE.items())
        if now_ts - float(state.get("updated_at") or 0.0) > _TEXT_QUERY_CACHE_TTL_SECONDS
    ]
    for key in expired:
        _TEXT_QUERY_CACHE.pop(key, None)
    while len(_TEXT_QUERY_CACHE) > _TEXT_QUERY_CACHE_MAX:
        _TEXT_QUERY_CACHE.popitem(last=False)


def _build_text_query_cache_key(
    policy,
    *,
    query: str,
    date_from: str | None,
    date_to: str | None,
    text_scope: str,
    text_mode: str,
    roots: list[str] | None,
):
    return (
        str(getattr(policy, "id", "") or ""),
        tuple(roots or ()),
        str(query or "").strip().lower(),
        str(date_from or ""),
        str(date_to or ""),
        str(text_scope or "parent"),
        str(text_mode or "and"),
    )


def _fetch_text_only_rows(
    policy,
    *,
    query: str,
    date_from: str | None,
    date_to: str | None,
    text_scope: str,
    text_mode: str,
) -> tuple[list[dict], bool]:
    roots = _get_policy_roots(policy)
    use_cache = roots is not None
    if not use_cache:
        rows = mysql.fetch_photos_by_text_query(
            query,
            date_from=date_from,
            date_to=date_to,
            roots=roots,
            scope=text_scope,
            query_mode=text_mode,
        )
        return rows, False

    cache_key = _build_text_query_cache_key(
        policy,
        query=query,
        date_from=date_from,
        date_to=date_to,
        text_scope=text_scope,
        text_mode=text_mode,
        roots=roots,
    )
    now_ts = time.time()
    with _TEXT_QUERY_CACHE_LOCK:
        _cleanup_text_query_cache(now_ts)
        cached = _TEXT_QUERY_CACHE.get(cache_key)
        if cached:
            _TEXT_QUERY_CACHE.move_to_end(cache_key, last=True)
            rows = [dict(row) for row in (cached.get("rows") or [])]
            return rows, True

    rows = mysql.fetch_photos_by_text_query(
        query,
        date_from=date_from,
        date_to=date_to,
        roots=roots,
        scope=text_scope,
        query_mode=text_mode,
    )
    stored_rows = [dict(row) for row in rows]
    with _TEXT_QUERY_CACHE_LOCK:
        _TEXT_QUERY_CACHE[cache_key] = {
            "rows": stored_rows,
            "updated_at": now_ts,
        }
        _TEXT_QUERY_CACHE.move_to_end(cache_key, last=True)
        _cleanup_text_query_cache(now_ts)
    return [dict(row) for row in stored_rows], False


@router.get("/search/batch", response_model=SearchResponse)
def search_batch(
    request: Request,
    search_id: str = Query(...),
    batch: int = Query(1, ge=1),
    sort_mode: str | None = Query(None),
    face_count_exact: int | None = Query(None, ge=0),
):
    policy = request.state.policy
    state = _get_search_session(search_id, policy.id)
    if not state:
        raise HTTPException(status_code=404, detail="search session expired or not found")
    if state.get("gallery_policy"):
        from service.api.v1.endpoints.gallery import policy_version, library_version
        if state["gallery_policy"] != policy_version(policy) or state.get("gallery_revision") != library_version():
            raise HTTPException(409, detail={"code": "library_changed", "message": "照片库或权限已更新，请重新搜索"})
    return _build_search_batch_response(
        search_id=search_id,
        state=state,
        batch=batch,
        sort_mode=sort_mode,
        face_count_exact=face_count_exact,
    )


@router.post("/search/face", response_model=SearchResponse)
async def search_face(
    request: Request,
    file: UploadFile = File(...),
    stage: int = Query(3, ge=1, le=3),
    date_from: str | None = None,
    date_to: str | None = None,
):
    policy = request.state.policy
    image_bytes = await file.read()
    engine = get_face_engine()
    faces = engine.detect_and_embed_bytes(image_bytes)
    best = _pick_best_face(faces)
    if not best:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)
    embedding = best["embedding"]
    index = get_index_manager()
    scope = _get_policy_search_scope(policy, date_from=date_from, date_to=date_to, need_face=True)
    policy_candidate_photo_ids = scope.get("photo_ids")
    if policy_candidate_photo_ids is not None and not policy_candidate_photo_ids:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)
    candidate_face_embedding_ids = scope.get("face_embedding_ids")
    if candidate_face_embedding_ids is not None and not candidate_face_embedding_ids:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)
    full_topk = (
        max(1, len(candidate_face_embedding_ids))
        if candidate_face_embedding_ids is not None
        else max(1, mysql.count_faces())
    )
    hits = (
        index.search_subset(embedding, candidate_face_embedding_ids, topk=full_topk)
        if candidate_face_embedding_ids is not None
        else index.search(embedding, topk=full_topk)
    )
    ids = [hid for hid, _ in hits if hid >= 0]
    score_map = {hid: float(score) for hid, score in hits}
    rows = filter_photo_rows(
        policy,
        mysql.fetch_photos_by_embedding_ids(
            ids,
            date_from=date_from,
            date_to=date_to,
            photo_ids=policy_candidate_photo_ids,
        ),
    )
    results = []
    for row in rows:
        results.append(
            SearchHit(
                embedding_id=row["embedding_id"],
                score=score_map.get(row["embedding_id"], 0.0),
                face_id=row["face_id"],
                photo_id=row["photo_id"],
                file_path=row["file_path"],
                exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                bbox=[row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]],
                gps_lat=float(row["gps_lat"]) if row.get("gps_lat") is not None else None,
                gps_lon=float(row["gps_lon"]) if row.get("gps_lon") is not None else None,
            )
        )
    return _new_search_response(
        stage=stage,
        results=filter_hits(policy, results),
        policy_id=policy.id,
    )


@router.post("/search/multi", response_model=SearchResponse)
async def search_multi(
    request: Request,
    files: List[UploadFile] | None = File(None),
    standard_photo_ids: List[int] | None = Query(None),
    elements: List[str] | None = Query(None),
    stage: int = Query(3, ge=1, le=3),
    date_from: str | None = None,
    date_to: str | None = None,
    text_query: str | None = None,
    text_scope: str = Query("parent"),
    text_mode: str = Query("and"),
    focus_modes: List[str] | None = Query(None),
    face_mode: str = Query(FACE_MODE_DEFAULT),
    min_match_faces: int | None = Query(None, ge=1),
    face_prune: bool = Query(True),
    element_mode: str = Query(ELEMENT_MODE_DEFAULT),
    sort_mode: str | None = Query(None),
    face_count_exact: int | None = Query(None, ge=0),
):
    policy = request.state.policy
    files = files or []
    date_bounds(date_from, date_to)
    elem_list = [e for e in (elements or []) if e in SUPPORTED_ELEMENTS]
    if not elem_list:
        raise HTTPException(status_code=400, detail="elements required")

    text_query = (text_query or "").strip()
    text_scope = (text_scope or "parent").lower()
    text_mode = (text_mode or "and").lower()
    face_mode = (face_mode or FACE_MODE_DEFAULT).lower()
    element_mode = (element_mode or ELEMENT_MODE_DEFAULT).lower()
    if text_scope not in ("parent", "any"):
        raise HTTPException(status_code=400, detail="text_scope must be 'parent' or 'any'")
    if text_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="text_mode must be 'and' or 'or'")
    if face_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="face_mode must be 'and' or 'or'")
    if element_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="element_mode must be 'and' or 'or'")
    focus_modes_effective = _normalize_focus_modes(focus_modes) if "focus" in elem_list else []
    wants_text = "text" in elem_list
    non_text_elements = [e for e in elem_list if e != "text"]

    if wants_text and not text_query:
        raise HTTPException(status_code=400, detail="text_query required when text element selected")

    if wants_text and not non_text_elements:
        rows, text_cache_hit = _fetch_text_only_rows(
            policy,
            query=text_query,
            date_from=date_from,
            date_to=date_to,
            text_scope=text_scope,
            text_mode=text_mode,
        )
        rows = filter_photo_rows(policy, rows)
        results = []
        text_scores = {}
        for row in rows:
            pid = int(row["photo_id"])
            text_scores[pid] = 1.0
            results.append(
                SearchHit(
                    embedding_id=0,
                    score=1.0,
                    face_id=None,
                    photo_id=pid,
                    file_path=row["file_path"],
                    exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                    bbox=None,
                    gps_lat=float(row["gps_lat"]) if row.get("gps_lat") is not None else None,
                    gps_lon=float(row["gps_lon"]) if row.get("gps_lon") is not None else None,
                )
            )
        debug_payload = _build_search_debug_payload(
            {"text": text_scores},
            ["text"],
            element_mode=element_mode,
            candidate_ids=None,
            combined_count=len(results),
            text_mode=text_mode,
            text_scope=text_scope,
            extra={"text_cache_hit": bool(text_cache_hit)},
        )
        return _new_search_response(
            stage=stage,
            results=results,
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    scope = _get_policy_search_scope(
        policy,
        date_from=date_from,
        date_to=date_to,
        need_face=("face" in elem_list),
        need_vision=bool([e for e in elem_list if e not in ("face", "text")]),
    )
    policy_candidate_photo_ids = scope.get("photo_ids")
    policy_candidate_set = set(policy_candidate_photo_ids) if policy_candidate_photo_ids is not None else None
    if policy_candidate_photo_ids is not None and not policy_candidate_photo_ids:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)

    uploaded_image_bytes = [await f.read() for f in files]
    image_bytes_list = _build_query_image_bytes(policy, uploaded_image_bytes, standard_photo_ids)
    if non_text_elements and not image_bytes_list:
        raise HTTPException(status_code=400, detail="files or standard_photo_ids required for face/vision search")

    element_scores = {}
    photo_info = {}
    face_prune_scores: bool | None = None
    face_meta = {}
    face_db_total = max(1, mysql.count_faces())
    face_topk = face_db_total
    face_index_total = _get_face_index_ntotal()
    vision_db_total = max(1, mysql.count_photo_embeddings())
    vision_topk = vision_db_total
    face_candidate_embedding_ids = scope.get("face_embedding_ids")
    if face_candidate_embedding_ids is not None:
        face_topk = max(1, len(face_candidate_embedding_ids))
    vision_elements = [e for e in elem_list if e not in ("face", "text")]
    vision_candidate_embedding_ids = scope.get("photo_embedding_ids")
    if vision_candidate_embedding_ids is not None:
        vision_topk = max(1, len(vision_candidate_embedding_ids))

    if "face" in elem_list:
        face_prune_scores = bool(face_prune)
        query_embeddings = _collect_query_face_embeddings(image_bytes_list)
        query_face_count = len(query_embeddings)
        requested_min_match_faces = int(min_match_faces) if min_match_faces is not None else None
        if requested_min_match_faces is not None and query_face_count <= 0:
            # Graceful fallback: no face found in query image(s), return empty face matches
            # instead of hard erroring due to min_match setting.
            requested_min_match_faces = None
        if requested_min_match_faces is not None and requested_min_match_faces > query_face_count:
            raise HTTPException(
                status_code=400,
                detail=f"至少匹配人脸数({requested_min_match_faces})不能大于标准照片检测到的人脸总数({query_face_count})。",
            )
        face_scores, face_photo_info, face_meta = _search_face_scores(
            query_embeddings,
            topk=face_topk,
            date_from=date_from,
            date_to=date_to,
            photo_ids=policy_candidate_photo_ids,
            candidate_embedding_ids=face_candidate_embedding_ids,
            face_mode=face_mode,
            min_match_faces=requested_min_match_faces,
            prune_scores=face_prune_scores,
        )
        allowed_face_scores = {}
        for pid, row in face_photo_info.items():
            if not filter_photo_rows(policy, [row]):
                continue
            photo_info[int(pid)] = row
            if int(pid) in face_scores:
                allowed_face_scores[int(pid)] = float(face_scores[int(pid)])
        element_scores["face"] = allowed_face_scores

    if vision_elements:
        try:
            vision_engine = get_vision_engine()
            vision_index = get_vision_index_manager()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"vision engine not ready: {exc}")

        for element in vision_elements:
            if vision_candidate_embedding_ids is not None and not vision_candidate_embedding_ids:
                element_scores[element] = {}
                continue
            score_map = {}
            ids = []
            vision_modes = focus_modes_effective if element == "focus" else [element]
            vision_subset_ids = None
            vision_subset_vecs = None
            if vision_candidate_embedding_ids is not None:
                vision_subset_ids, vision_subset_vecs = vision_index.prepare_subset(vision_candidate_embedding_ids)
                if not vision_subset_ids or vision_subset_vecs.size == 0:
                    element_scores[element] = {}
                    continue
            for image_bytes in image_bytes_list:
                for mode_name in vision_modes:
                    embed_mode = f"focus_{mode_name}" if element == "focus" else mode_name
                    vec = vision_engine.embed_image_bytes(image_bytes, mode=embed_mode)
                    hits = (
                        vision_index.search_prepared_subset(vec, vision_subset_ids, vision_subset_vecs, topk=vision_topk)
                        if vision_subset_ids is not None and vision_subset_vecs is not None
                        else vision_index.search(vec, topk=vision_topk)
                    )
                    for hid, score in hits:
                        if hid < 0:
                            continue
                        score_map[hid] = max(score_map.get(hid, 0.0), float(score))
                        ids.append(hid)
            ids = list(dict.fromkeys(ids))
            rows = filter_photo_rows(
                policy,
                mysql.fetch_photos_by_photo_embedding_ids(
                    ids,
                    date_from=date_from,
                    date_to=date_to,
                    photo_ids=policy_candidate_photo_ids,
                ),
            )
            elem_scores = {}
            for row in rows:
                eid = row["embedding_id"]
                pid = int(row["photo_id"])
                score = score_map.get(eid, 0.0)
                if score > elem_scores.get(pid, -1):
                    elem_scores[pid] = score
                    if pid not in photo_info:
                        photo_info[pid] = row
            elem_scores = _prune_scores_by_best(
                elem_scores,
                min_ratio=VISION_MATCH_MIN_RATIO,
                min_abs=VISION_MATCH_MIN_ABS,
            )
            element_scores[element] = elem_scores

    if wants_text and non_text_elements:
        rows = filter_photo_rows(
            policy,
            mysql.fetch_photos_by_text_query(
                text_query,
                date_from=date_from,
                date_to=date_to,
                photo_ids=policy_candidate_photo_ids,
                scope=text_scope,
                query_mode=text_mode,
            ),
        )
        text_scores = {}
        for row in rows:
            pid = int(row["photo_id"])
            text_scores[pid] = 1.0
            if pid not in photo_info:
                photo_info[pid] = row
        element_scores["text"] = text_scores

    debug_extra = {}
    if "face" in elem_list:
        debug_extra["face_db_total"] = int(face_db_total)
        debug_extra["face_search_space_total"] = int(face_topk)
        debug_extra["face_index_total"] = int(face_index_total)
        debug_extra["face_index_coverage"] = round(float(face_index_total) / float(max(1, face_db_total)), 6)
        debug_extra["query_face_count"] = int(face_meta.get("query_face_count") or 0)
        min_match_effective = face_meta.get("min_match_faces_effective")
        if min_match_effective is not None:
            debug_extra["min_match_faces"] = int(min_match_effective)
        min_match_requested = face_meta.get("min_match_faces_requested")
        if min_match_requested is not None:
            debug_extra["min_match_faces_requested"] = int(min_match_requested)
    if policy_candidate_photo_ids is not None:
        debug_extra["policy_candidate_photo_count"] = len(policy_candidate_photo_ids)
    if wants_text and "face" in element_scores and "text" in element_scores:
        overlap_extra = _debug_extra_face_text_overlap(
            element_scores,
            text_query=text_query,
            date_from=date_from,
            date_to=date_to,
            text_scope=text_scope,
            text_mode=text_mode,
            candidate_ids=policy_candidate_set,
        )
        debug_extra.update(overlap_extra)
        debug_extra["face_db_total"] = int(face_db_total)
        debug_extra["face_search_space_total"] = int(face_topk)
        debug_extra["face_index_total"] = int(face_index_total)
        debug_extra["face_index_coverage"] = round(float(face_index_total) / float(max(1, face_db_total)), 6)
    if wants_text:
        debug_extra["date_from"] = date_from
        debug_extra["date_to"] = date_to
    if "focus" in elem_list:
        debug_extra["focus_modes"] = focus_modes_effective

    if not element_scores:
        debug_payload = _build_search_debug_payload(
            element_scores,
            elem_list,
            element_mode=element_mode,
            candidate_ids=policy_candidate_set,
            face_mode=face_mode if "face" in elem_list else None,
            face_prune_scores=face_prune_scores,
            text_mode=text_mode if wants_text else None,
            text_scope=text_scope if wants_text else None,
            combined_count=0,
            extra=debug_extra,
        )
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    combined = _combine_element_scores(
        element_scores,
        elem_list,
        element_mode=element_mode,
        candidate_ids=policy_candidate_set,
    )
    debug_payload = _build_search_debug_payload(
        element_scores,
        elem_list,
        element_mode=element_mode,
        candidate_ids=policy_candidate_set,
        face_mode=face_mode if "face" in elem_list else None,
        face_prune_scores=face_prune_scores,
        text_mode=text_mode if wants_text else None,
        text_scope=text_scope if wants_text else None,
        combined_count=len(combined),
        extra=debug_extra,
    )
    if not combined:
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    results = []
    for pid, score in combined:
        row = photo_info.get(pid, {})
        results.append(
            SearchHit(
                embedding_id=int(row.get("embedding_id", 0)) if row else 0,
                score=score,
                face_id=row.get("face_id"),
                photo_id=pid,
                file_path=row.get("file_path"),
                exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                bbox=[row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]]
                if row and row.get("bbox_x1") is not None
                else None,
                gps_lat=float(row["gps_lat"]) if row and row.get("gps_lat") is not None else None,
                gps_lon=float(row["gps_lon"]) if row and row.get("gps_lon") is not None else None,
            )
        )

    return _new_search_response(
        stage=stage,
        results=filter_hits(policy, results),
        policy_id=policy.id,
        debug=debug_payload,
        sort_mode=sort_mode,
        face_count_exact=face_count_exact,
    )


@router.get("/search/gps", response_model=SearchResponse)
def search_gps(
    request: Request,
    center_photo_id: int = Query(..., ge=1),
    radius_km: float = Query(5.0, ge=1.0, le=50.0),
    stage: int = Query(3, ge=1, le=3),
    date_from: str | None = None,
    date_to: str | None = None,
    text_query: str | None = None,
    text_scope: str = Query("parent"),
    text_mode: str = Query("and"),
    sort_mode: str | None = Query(None),
    face_count_exact: int | None = Query(None, ge=0),
):
    policy = request.state.policy
    policy_roots = _get_policy_roots(policy)
    ensure_photo_allowed(policy, center_photo_id)
    center = mysql.get_photo_gps_info(center_photo_id)
    if not center:
        raise HTTPException(status_code=404, detail="center photo not found")
    center_lat = center.get("gps_lat")
    center_lon = center.get("gps_lon")
    if center_lat is None or center_lon is None:
        raise HTTPException(status_code=400, detail="center photo has no GPS info")

    rows = filter_photo_rows(
        policy,
        mysql.fetch_photos_by_gps_radius(
            center_lat=float(center_lat),
            center_lon=float(center_lon),
            radius_km=float(radius_km),
            date_from=date_from,
            date_to=date_to,
            roots=policy_roots,
            limit=None,
        ),
    )
    if not rows:
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    text_query = (text_query or "").strip()
    if text_query:
        text_scope = (text_scope or "parent").lower()
        text_mode = (text_mode or "and").lower()
        if text_scope not in ("parent", "any"):
            raise HTTPException(status_code=400, detail="text_scope must be 'parent' or 'any'")
        if text_mode not in ("and", "or"):
            raise HTTPException(status_code=400, detail="text_mode must be 'and' or 'or'")
        candidate_ids = [int(row["photo_id"]) for row in rows]
        text_rows = filter_photo_rows(
            policy,
            mysql.fetch_photos_by_text_query(
                text_query,
                date_from=date_from,
                date_to=date_to,
                photo_ids=candidate_ids,
                scope=text_scope,
                query_mode=text_mode,
            ),
        )
        keep_ids = {int(row["photo_id"]) for row in text_rows}
        rows = [row for row in rows if int(row["photo_id"]) in keep_ids]

    results = []
    for row in rows:
        dist = float(row.get("distance_km") or 0.0)
        results.append(
            SearchHit(
                embedding_id=0,
                score=_distance_score(dist, float(radius_km)),
                face_id=None,
                photo_id=int(row["photo_id"]),
                file_path=row.get("file_path"),
                exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                bbox=None,
                gps_lat=float(row["gps_lat"]) if row.get("gps_lat") is not None else None,
                gps_lon=float(row["gps_lon"]) if row.get("gps_lon") is not None else None,
                distance_km=round(dist, 3),
            )
        )
    return _new_search_response(
        stage=stage,
        results=filter_hits(policy, results),
        policy_id=policy.id,
        sort_mode=sort_mode,
        face_count_exact=face_count_exact,
    )


@router.post("/search/gps_multi", response_model=SearchResponse)
async def search_gps_multi(
    request: Request,
    files: List[UploadFile] | None = File(None),
    standard_photo_ids: List[int] | None = Query(None),
    elements: List[str] | None = Query(None),
    center_photo_id: int = Query(..., ge=1),
    radius_km: float = Query(5.0, ge=1.0, le=50.0),
    stage: int = Query(3, ge=1, le=3),
    date_from: str | None = None,
    date_to: str | None = None,
    text_query: str | None = None,
    text_scope: str = Query("parent"),
    text_mode: str = Query("and"),
    focus_modes: List[str] | None = Query(None),
    face_mode: str = Query(FACE_MODE_DEFAULT),
    min_match_faces: int | None = Query(None, ge=1),
    face_prune: bool = Query(True),
    element_mode: str = Query(ELEMENT_MODE_DEFAULT),
    sort_mode: str | None = Query(None),
    face_count_exact: int | None = Query(None, ge=0),
):
    policy = request.state.policy
    policy_roots = _get_policy_roots(policy)
    files = files or []
    date_bounds(date_from, date_to)
    elem_list = [e for e in (elements or []) if e in SUPPORTED_ELEMENTS]
    if not elem_list:
        raise HTTPException(status_code=400, detail="elements required")

    text_query = (text_query or "").strip()
    text_scope = (text_scope or "parent").lower()
    text_mode = (text_mode or "and").lower()
    face_mode = (face_mode or FACE_MODE_DEFAULT).lower()
    element_mode = (element_mode or ELEMENT_MODE_DEFAULT).lower()
    if text_scope not in ("parent", "any"):
        raise HTTPException(status_code=400, detail="text_scope must be 'parent' or 'any'")
    if text_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="text_mode must be 'and' or 'or'")
    if face_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="face_mode must be 'and' or 'or'")
    if element_mode not in ("and", "or"):
        raise HTTPException(status_code=400, detail="element_mode must be 'and' or 'or'")
    focus_modes_effective = _normalize_focus_modes(focus_modes) if "focus" in elem_list else []

    wants_text = "text" in elem_list
    non_text_elements = [e for e in elem_list if e != "text"]
    if wants_text and not text_query:
        raise HTTPException(status_code=400, detail="text_query required when text element selected")

    ensure_photo_allowed(policy, center_photo_id)
    center = mysql.get_photo_gps_info(center_photo_id)
    if not center:
        raise HTTPException(status_code=404, detail="center photo not found")
    center_lat = center.get("gps_lat")
    center_lon = center.get("gps_lon")
    if center_lat is None or center_lon is None:
        raise HTTPException(status_code=400, detail="center photo has no GPS info")

    gps_rows = filter_photo_rows(
        policy,
        mysql.fetch_photos_by_gps_radius(
            center_lat=float(center_lat),
            center_lon=float(center_lon),
            radius_km=float(radius_km),
            date_from=date_from,
            date_to=date_to,
            roots=policy_roots,
            limit=None,
        ),
    )
    if not gps_rows:
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    candidate_ids = [int(row["photo_id"]) for row in gps_rows]
    candidate_set = set(candidate_ids)
    distance_map = {int(row["photo_id"]): float(row.get("distance_km") or 0.0) for row in gps_rows}
    base_row_map = {int(row["photo_id"]): row for row in gps_rows}

    if wants_text and not non_text_elements:
        text_rows = filter_photo_rows(
            policy,
            mysql.fetch_photos_by_text_query(
                text_query,
                date_from=date_from,
                date_to=date_to,
                photo_ids=candidate_ids,
                scope=text_scope,
                query_mode=text_mode,
            ),
        )
        results = []
        text_scores = {}
        for row in text_rows:
            pid = int(row["photo_id"])
            text_scores[pid] = 1.0
            dist = distance_map.get(pid, float(radius_km))
            results.append(
                SearchHit(
                    embedding_id=0,
                    score=_distance_score(dist, float(radius_km)),
                    face_id=None,
                    photo_id=pid,
                    file_path=row.get("file_path"),
                    exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                    bbox=None,
                    gps_lat=float(row["gps_lat"]) if row.get("gps_lat") is not None else None,
                    gps_lon=float(row["gps_lon"]) if row.get("gps_lon") is not None else None,
                    distance_km=round(dist, 3),
                )
            )
        results.sort(key=lambda x: x.distance_km if x.distance_km is not None else 10**9)
        debug_payload = _build_search_debug_payload(
            {"text": text_scores},
            ["text"],
            element_mode=element_mode,
            candidate_ids=candidate_set,
            combined_count=len(results),
            text_mode=text_mode,
            text_scope=text_scope,
        )
        return _new_search_response(
            stage=stage,
            results=results,
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    uploaded_image_bytes = [await f.read() for f in files]
    image_bytes_list = _build_query_image_bytes(policy, uploaded_image_bytes, standard_photo_ids)
    if non_text_elements and not image_bytes_list:
        raise HTTPException(status_code=400, detail="files or standard_photo_ids required for face/vision search")

    element_scores = {}
    photo_info = {}
    face_prune_scores: bool | None = None
    face_meta = {}
    face_db_total = max(1, mysql.count_faces())
    face_topk = face_db_total
    face_index_total = _get_face_index_ntotal()
    vision_db_total = max(1, mysql.count_photo_embeddings())
    vision_topk = vision_db_total
    face_candidate_embedding_ids = (
        mysql.fetch_face_embedding_ids_by_photo_ids(candidate_ids)
        if "face" in elem_list
        else None
    )
    if face_candidate_embedding_ids is not None:
        face_topk = max(1, len(face_candidate_embedding_ids))
    vision_candidate_embedding_ids = (
        mysql.fetch_photo_embedding_ids_by_photo_ids(candidate_ids)
        if non_text_elements
        else None
    )
    if vision_candidate_embedding_ids is not None:
        vision_topk = max(1, len(vision_candidate_embedding_ids))

    if "face" in elem_list:
        face_prune_scores = bool(face_prune)
        query_embeddings = _collect_query_face_embeddings(image_bytes_list)
        query_face_count = len(query_embeddings)
        requested_min_match_faces = int(min_match_faces) if min_match_faces is not None else None
        if requested_min_match_faces is not None and query_face_count <= 0:
            # Graceful fallback: no face found in query image(s), return empty face matches
            # instead of hard erroring due to min_match setting.
            requested_min_match_faces = None
        if requested_min_match_faces is not None and requested_min_match_faces > query_face_count:
            raise HTTPException(
                status_code=400,
                detail=f"至少匹配人脸数({requested_min_match_faces})不能大于标准照片检测到的人脸总数({query_face_count})。",
            )
        face_scores, face_photo_info, face_meta = _search_face_scores(
            query_embeddings,
            topk=face_topk,
            date_from=date_from,
            date_to=date_to,
            photo_ids=candidate_ids,
            candidate_embedding_ids=face_candidate_embedding_ids,
            face_mode=face_mode,
            min_match_faces=requested_min_match_faces,
            prune_scores=face_prune_scores,
        )
        allowed_face_scores = {}
        for pid, row in face_photo_info.items():
            if int(pid) not in candidate_set:
                continue
            if not filter_photo_rows(policy, [row]):
                continue
            photo_info[int(pid)] = row
            if int(pid) in face_scores:
                allowed_face_scores[int(pid)] = float(face_scores[int(pid)])
        element_scores["face"] = allowed_face_scores

    vision_elements = [e for e in elem_list if e not in ("face", "text")]
    if vision_elements:
        try:
            vision_engine = get_vision_engine()
            vision_index = get_vision_index_manager()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"vision engine not ready: {exc}")

        for element in vision_elements:
            if vision_candidate_embedding_ids is not None and not vision_candidate_embedding_ids:
                element_scores[element] = {}
                continue
            score_map = {}
            ids = []
            vision_modes = focus_modes_effective if element == "focus" else [element]
            vision_subset_ids = None
            vision_subset_vecs = None
            if vision_candidate_embedding_ids is not None:
                vision_subset_ids, vision_subset_vecs = vision_index.prepare_subset(vision_candidate_embedding_ids)
                if not vision_subset_ids or vision_subset_vecs.size == 0:
                    element_scores[element] = {}
                    continue
            for image_bytes in image_bytes_list:
                for mode_name in vision_modes:
                    embed_mode = f"focus_{mode_name}" if element == "focus" else mode_name
                    vec = vision_engine.embed_image_bytes(image_bytes, mode=embed_mode)
                    hits = (
                        vision_index.search_prepared_subset(vec, vision_subset_ids, vision_subset_vecs, topk=vision_topk)
                        if vision_subset_ids is not None and vision_subset_vecs is not None
                        else vision_index.search(vec, topk=vision_topk)
                    )
                    for hid, score in hits:
                        if hid < 0:
                            continue
                        score_map[hid] = max(score_map.get(hid, 0.0), float(score))
                        ids.append(hid)
            ids = list(dict.fromkeys(ids))
            rows = filter_photo_rows(
                policy,
                mysql.fetch_photos_by_photo_embedding_ids(
                    ids,
                    date_from=date_from,
                    date_to=date_to,
                    photo_ids=candidate_ids,
                ),
            )
            elem_scores = {}
            for row in rows:
                pid = int(row["photo_id"])
                if pid not in candidate_set:
                    continue
                eid = row["embedding_id"]
                score = score_map.get(eid, 0.0)
                if score > elem_scores.get(pid, -1):
                    elem_scores[pid] = score
                    if pid not in photo_info:
                        photo_info[pid] = row
            elem_scores = _prune_scores_by_best(
                elem_scores,
                min_ratio=VISION_MATCH_MIN_RATIO,
                min_abs=VISION_MATCH_MIN_ABS,
            )
            element_scores[element] = elem_scores

    if wants_text and non_text_elements:
        text_rows = filter_photo_rows(
            policy,
            mysql.fetch_photos_by_text_query(
                text_query,
                date_from=date_from,
                date_to=date_to,
                photo_ids=candidate_ids,
                scope=text_scope,
                query_mode=text_mode,
            ),
        )
        text_scores = {}
        for row in text_rows:
            pid = int(row["photo_id"])
            if pid in candidate_set:
                text_scores[pid] = 1.0
                if pid not in photo_info:
                    photo_info[pid] = row
        element_scores["text"] = text_scores

    debug_extra = {}
    if "face" in elem_list:
        debug_extra["face_db_total"] = int(face_db_total)
        debug_extra["face_search_space_total"] = int(face_topk)
        debug_extra["face_index_total"] = int(face_index_total)
        debug_extra["face_index_coverage"] = round(float(face_index_total) / float(max(1, face_db_total)), 6)
        debug_extra["query_face_count"] = int(face_meta.get("query_face_count") or 0)
        min_match_effective = face_meta.get("min_match_faces_effective")
        if min_match_effective is not None:
            debug_extra["min_match_faces"] = int(min_match_effective)
        min_match_requested = face_meta.get("min_match_faces_requested")
        if min_match_requested is not None:
            debug_extra["min_match_faces_requested"] = int(min_match_requested)
    if wants_text and "face" in element_scores and "text" in element_scores:
        overlap_extra = _debug_extra_face_text_overlap(
            element_scores,
            text_query=text_query,
            date_from=date_from,
            date_to=date_to,
            text_scope=text_scope,
            text_mode=text_mode,
            candidate_ids=candidate_set,
        )
        debug_extra.update(overlap_extra)
        debug_extra["face_db_total"] = int(face_db_total)
        debug_extra["face_search_space_total"] = int(face_topk)
        debug_extra["face_index_total"] = int(face_index_total)
        debug_extra["face_index_coverage"] = round(float(face_index_total) / float(max(1, face_db_total)), 6)
    if wants_text:
        debug_extra["date_from"] = date_from
        debug_extra["date_to"] = date_to
    if "focus" in elem_list:
        debug_extra["focus_modes"] = focus_modes_effective

    if not element_scores:
        debug_payload = _build_search_debug_payload(
            element_scores,
            elem_list,
            element_mode=element_mode,
            candidate_ids=candidate_set,
            face_mode=face_mode if "face" in elem_list else None,
            face_prune_scores=face_prune_scores,
            text_mode=text_mode if wants_text else None,
            text_scope=text_scope if wants_text else None,
            combined_count=0,
            extra=debug_extra,
        )
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    combined_base = _combine_element_scores(
        element_scores,
        elem_list,
        element_mode=element_mode,
        candidate_ids=candidate_set,
    )
    debug_payload = _build_search_debug_payload(
        element_scores,
        elem_list,
        element_mode=element_mode,
        candidate_ids=candidate_set,
        face_mode=face_mode if "face" in elem_list else None,
        face_prune_scores=face_prune_scores,
        text_mode=text_mode if wants_text else None,
        text_scope=text_scope if wants_text else None,
        combined_count=len(combined_base),
        extra=debug_extra,
    )
    if not combined_base:
        return _new_search_response(
            stage=stage,
            results=[],
            policy_id=policy.id,
            debug=debug_payload,
            sort_mode=sort_mode,
            face_count_exact=face_count_exact,
        )

    combined = []
    for pid, elem_score in combined_base:
        dist = distance_map.get(pid, float(radius_km))
        dist_score = _distance_score(dist, float(radius_km))
        final_score = elem_score * 0.8 + dist_score * 0.2
        combined.append((pid, final_score, dist))

    combined.sort(key=lambda x: (x[1], -x[2]), reverse=True)

    results = []
    for pid, score, dist in combined:
        row = photo_info.get(pid) or base_row_map.get(pid, {})
        results.append(
            SearchHit(
                embedding_id=int(row.get("embedding_id", 0)) if row else 0,
                score=score,
                face_id=row.get("face_id"),
                photo_id=pid,
                file_path=row.get("file_path"),
                exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                bbox=[row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]]
                if row and row.get("bbox_x1") is not None
                else None,
                gps_lat=float(row["gps_lat"]) if row and row.get("gps_lat") is not None else None,
                gps_lon=float(row["gps_lon"]) if row and row.get("gps_lon") is not None else None,
                distance_km=round(float(dist), 3),
            )
        )
    return _new_search_response(
        stage=stage,
        results=filter_hits(policy, results),
        policy_id=policy.id,
        debug=debug_payload,
        sort_mode=sort_mode,
        face_count_exact=face_count_exact,
    )


@router.post("/search/person", response_model=SearchResponse)
def search_person(
    request: Request,
    face_id: int = Body(..., embed=True),
    stage: int = Query(3, ge=1, le=3),
):
    policy = request.state.policy
    scope = _get_policy_search_scope(policy, need_face=True)
    policy_candidate_photo_ids = scope.get("photo_ids")
    row = mysql.fetch_one(
        """
        SELECT f.embedding_id, f.photo_id
        FROM faces f
        JOIN photos p ON p.id = f.photo_id
        WHERE f.id=%s AND p.status='active'
        LIMIT 1
        """,
        (face_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="face_id not found")
    ensure_photo_allowed(policy, int(row["photo_id"]))
    embedding_id = int(row["embedding_id"])
    index = get_index_manager()
    vector = index.reconstruct(embedding_id)
    if policy_candidate_photo_ids is not None and not policy_candidate_photo_ids:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)
    candidate_face_embedding_ids = scope.get("face_embedding_ids")
    if candidate_face_embedding_ids is not None and not candidate_face_embedding_ids:
        return _new_search_response(stage=stage, results=[], policy_id=policy.id)
    full_topk = (
        max(1, len(candidate_face_embedding_ids))
        if candidate_face_embedding_ids is not None
        else max(1, mysql.count_faces())
    )
    hits = (
        index.search_subset(vector, candidate_face_embedding_ids, topk=full_topk)
        if candidate_face_embedding_ids is not None
        else index.search(vector, topk=full_topk)
    )
    ids = [hid for hid, _ in hits if hid >= 0]
    score_map = {hid: float(score) for hid, score in hits}
    rows = filter_photo_rows(
        policy,
        mysql.fetch_photos_by_embedding_ids(ids, photo_ids=policy_candidate_photo_ids),
    )
    results = []
    for row in rows:
        results.append(
            SearchHit(
                embedding_id=row["embedding_id"],
                score=score_map.get(row["embedding_id"], 0.0),
                face_id=row["face_id"],
                photo_id=row["photo_id"],
                file_path=row["file_path"],
                exif_datetime=str(row.get("exif_datetime")) if row.get("exif_datetime") else None,
                bbox=[row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]],
                gps_lat=float(row["gps_lat"]) if row.get("gps_lat") is not None else None,
                gps_lon=float(row["gps_lon"]) if row.get("gps_lon") is not None else None,
            )
        )
    return _new_search_response(
        stage=stage,
        results=filter_hits(policy, results),
        policy_id=policy.id,
    )

