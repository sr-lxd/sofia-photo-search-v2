"""The v2 gallery: metadata browsing, scoped facets and input-based search."""
import base64
import asyncio
from collections import Counter
from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
import time
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from service.core.acl import filter_photo_rows
from service.core.auth_policy import get_policy_by_id
from service.core.config import settings
from service.core.date_utils import date_bounds, shanghai_today
from service.db import mysql
from service.models.schemas import SearchHit
from service.api.v1.endpoints.photos import _append_policy_where
from service.api.v1.endpoints import search

router = APIRouter()


class GalleryQuery(BaseModel):
    mode: Literal["library", "photo", "description"] = "library"
    photo_goal: Literal["face", "scene"] = "face"
    time_basis: Literal["photo", "added"] = "photo"
    recent_days: int | None = Field(None, ge=1, le=3660)
    date_from: str | None = None
    date_to: str | None = None
    face_eq: int | None = Field(None, ge=1, le=10000)
    face_min: int | None = Field(None, ge=1, le=10000)
    face_max: int | None = Field(None, ge=1, le=10000)
    directory: str = Field("", max_length=1500)
    filename: str = Field("", max_length=200)
    center_lat: float | None = Field(None, ge=-90, le=90)
    center_lon: float | None = Field(None, ge=-180, le=180)
    radius_km: float = Field(5, ge=0.1, le=1000)
    place_name: str = Field("", max_length=100)
    description: str = Field("", max_length=500)
    reference_ids: list[int] = Field(default_factory=list, max_length=100)
    face_mode: Literal["and", "or"] = "or"
    min_match_faces: int | None = Field(None, ge=1, le=100)
    sort: Literal["date_desc", "date_asc", "face_asc", "face_desc", "relevance"] = "date_desc"


def parse_query(value):
    try:
        if isinstance(value, str):
            if len(value) > 16384:
                raise ValueError("查询条件过长")
            value = json.loads(value)
        q = GalleryQuery(**(value or {})).model_dump()
    except Exception:
        raise HTTPException(422, detail="查询配置无效，请检查日期、人数和地点")
    if q["recent_days"] and (q["date_from"] or q["date_to"]):
        raise HTTPException(422, detail="近期范围与自定义日期请选一种")
    if q["face_eq"] and (q["face_min"] or q["face_max"]):
        raise HTTPException(422, detail="精确人数与人数区间请选一种")
    if q["face_min"] and q["face_max"] and q["face_min"] > q["face_max"]:
        raise HTTPException(422, detail="人数下限不能大于上限")
    if (q["center_lat"] is None) != (q["center_lon"] is None):
        raise HTTPException(422, detail="地点需要同时提供纬度与经度")
    date_bounds(q["date_from"], q["date_to"])
    if any(pid <= 0 for pid in q["reference_ids"]):
        raise HTTPException(422, detail="参考照片ID无效")
    return q


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def policy_version(policy):
    return fingerprint({"id": policy.id, "roots": policy.roots, "admin": policy.is_admin, "enabled": policy.enabled})


def library_version():
    row = mysql.fetch_one("SELECT revision FROM ui_library_version WHERE id=1")
    if not row:
        raise HTTPException(503, detail="请先运行v2环境准备程序")
    return int(row["revision"])


def freeze(q, previous=None):
    resolved = dict(q)
    if previous is not None:
        resolved["date_from"], resolved["date_to"] = previous
    elif q["recent_days"]:
        today = shanghai_today()
        resolved["date_from"] = (today - timedelta(days=q["recent_days"] - 1)).isoformat()
        resolved["date_to"] = today.isoformat()
    return resolved


def time_expr(q):
    return "created_at" if q["time_basis"] == "added" else "COALESCE(exif_datetime,file_mtime)"


def where(policy, q, omit=None):
    params = []
    sql = _append_policy_where(" WHERE status='active'", params, policy)
    start, end = date_bounds(q["date_from"], q["date_to"])
    expression = time_expr(q)
    if start:
        sql += f" AND {expression} >= %s"
        params.append(start)
    if end:
        sql += f" AND {expression} < %s"
        params.append(end)
    if omit != "face":
        for key, operation in [("face_eq", "="), ("face_min", ">="), ("face_max", "<=")]:
            if q[key] is not None:
                sql += f" AND face_count {operation} %s"
                params.append(q[key])
    if q["directory"]:
        directory = str(Path(q["directory"])).replace("\\", "/").rstrip("/")
        sql += " AND (REPLACE(file_path, '\\\\', '/')=%s OR REPLACE(file_path, '\\\\', '/') LIKE %s ESCAPE '=')"
        params.extend([directory, directory.replace("=", "==").replace("%", "=%").replace("_", "=_") + "/%"])
    if q["filename"]:
        name = q["filename"].replace("=", "==").replace("%", "=%").replace("_", "=_")
        sql += " AND file_name LIKE %s ESCAPE '='"
        params.append("%" + name + "%")
    if omit != "gps" and q["center_lat"] is not None:
        sql += " AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL AND (6371*2*ASIN(SQRT(LEAST(1,GREATEST(0,POW(SIN(RADIANS(gps_lat-%s)/2),2)+COS(RADIANS(%s))*COS(RADIANS(gps_lat))*POW(SIN(RADIANS(gps_lon-%s)/2),2)))))) <= %s"
        params.extend([q["center_lat"], q["center_lat"], q["center_lon"], q["radius_km"]])
    return sql, params


def cursor_encode(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(settings.auth.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + sig


def cursor_decode(value):
    try:
        if len(value) > 4096:
            raise ValueError()
        encoded, sig = value.split(".")
        expected = hmac.new(settings.auth.session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if data["v"] != 1 or data["expires"] < time.time() or int(data["id"]) <= 0:
            raise ValueError()
        return data
    except Exception:
        raise HTTPException(400, detail={"code": "invalid_cursor", "message": "翻页记录无效或已过期，请重新查询"})


def public_row(row):
    item = dict(row)
    item["photo_id"] = int(item.pop("id"))
    for key in ["exif_datetime", "created_at", "effective_time"]:
        if item.get(key):
            item[key] = item[key].isoformat(sep=" ")
    for key in ["gps_lat", "gps_lon"]:
        if item.get(key) is not None:
            item[key] = float(item[key])
    return item


@router.get("/photos/browse")
def browse(request: Request, config: str = "{}", cursor: str | None = None, limit: int = Query(55, ge=1, le=100)):
    policy = request.state.policy
    q = parse_query(config)
    fp, pv, rev = fingerprint(q), policy_version(policy), library_version()
    data = cursor_decode(cursor) if cursor else None
    if data:
        for key, expected, code in [("fp", fp, "query_changed"), ("policy", pv, "policy_changed"), ("rev", rev, "library_changed")]:
            if data.get(key) != expected:
                raise HTTPException(409, detail={"code": code, "message": "照片库、访问权限或条件已变更，请重新查询"})
    resolved = freeze(q, data["range"] if data else None)
    tail, params = where(policy, resolved)
    expression = time_expr(resolved)
    descending = q["sort"] not in ("date_asc", "face_asc")
    operation, direction = ("<", "DESC") if descending else (">", "ASC")
    face_sort = q["sort"].startswith("face_")
    order_expr = "COALESCE(face_count,0)" if face_sort else expression
    if data:
        tail += f" AND ({order_expr} {operation} %s OR ({order_expr}=%s AND id {operation} %s))"
        params.extend([data["value"], data["value"], data["id"]])
    sql = "SELECT id,file_path,file_name,face_count,gps_lat,gps_lon,created_at,COALESCE(exif_datetime,file_mtime) AS exif_datetime," + expression + " AS effective_time FROM photos" + tail
    rows = list(mysql.fetch_all(sql + f" ORDER BY {order_expr} {direction},id {direction} LIMIT %s", params + [limit + 1]) or [])
    rows = filter_photo_rows(policy, rows)
    if library_version() != rev:
        raise HTTPException(409, detail={"code": "library_changed", "message": "照片库正在更新，请稍后刷新"})
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        value = int(last.get("face_count") or 0) if face_sort else str(last["effective_time"])
        next_cursor = cursor_encode({"v": 1, "expires": int(time.time()) + 3600, "id": int(last["id"]), "value": value, "fp": fp, "policy": pv, "rev": rev, "range": [resolved["date_from"], resolved["date_to"]]})
    return {"items": [public_row(row) for row in items], "has_more": has_more, "next_cursor": next_cursor, "query_fingerprint": fp, "resolved_range": [resolved["date_from"], resolved["date_to"]], "library_version": rev}


def metadata_rows(policy, q):
    tail, params = where(policy, q)
    return filter_photo_rows(policy, list(mysql.fetch_all("SELECT id,file_path,file_name,face_count,gps_lat,gps_lon,COALESCE(exif_datetime,file_mtime) AS exif_datetime,created_at FROM photos" + tail, params) or []))


@router.post("/search/query")
async def query(request: Request, config: str = Form(...), files: list[UploadFile] | None = File(None)):
    return await run_in_threadpool(lambda: asyncio.run(execute_query(request, config, files)))


async def execute_query(request, config, files):
    q = parse_query(config)
    policy = request.state.policy
    resolved = freeze(q)
    if q["mode"] == "library":
        raise HTTPException(422, detail="浏览请使用照片库入口")
    if q["mode"] == "photo":
        if not files and not q["reference_ids"]:
            raise HTTPException(422, detail="请添加本次参考照片")
        original = await search.search_multi(request=request, files=files or [], standard_photo_ids=q["reference_ids"], elements=[q["photo_goal"]], stage=3, date_from=resolved["date_from"] if q["time_basis"] == "photo" else None, date_to=resolved["date_to"] if q["time_basis"] == "photo" else None, text_query=None, text_scope="parent", text_mode="and", focus_modes=None, face_mode=q["face_mode"], min_match_faces=q["min_match_faces"], face_prune=True, element_mode="and", sort_mode=None, face_count_exact=None)
        session = search._get_search_session(original.search_id, policy.id)
        if not session:
            raise HTTPException(409, detail="检索记录已失效，请重试")
        raw = [SearchHit(**row) for row in session["results"]]
    else:
        if not q["description"].strip():
            raise HTTPException(422, detail="请描述要找的画面")
        from service.vision.engine import get_vision_engine
        from service.index.manager import get_vision_index_manager
        engine, index = get_vision_engine(), get_vision_index_manager()
        vector = engine.embed_text(q["description"].strip())
        scoped = metadata_rows(policy, resolved)
        if not scoped:
            raw = []
        else:
            ids = [int(row["id"]) for row in scoped]
            embedding_ids = []
            for offset in range(0, len(ids), 1000):
                chunk = ids[offset:offset + 1000]
                emb = mysql.fetch_all("SELECT embedding_id FROM photo_embeddings WHERE photo_id IN (" + ",".join(["%s"] * len(chunk)) + ")", chunk)
                embedding_ids.extend(int(row["embedding_id"]) for row in (emb or []))
            hits = index.search_subset(vector, embedding_ids, topk=min(2000, len(embedding_ids))) if embedding_ids else []
            scores = dict(hits)
            ids_hit = list(scores)
            raw = []
            for offset in range(0, len(ids_hit), 1000):
                rows = mysql.fetch_photos_by_photo_embedding_ids(ids_hit[offset:offset + 1000])
                for row in filter_photo_rows(policy, rows):
                    raw.append(SearchHit(embedding_id=row["embedding_id"], score=scores[row["embedding_id"]], photo_id=row["photo_id"], file_path=row["file_path"], exif_datetime=str(row["exif_datetime"]) if row.get("exif_datetime") else None, gps_lat=row.get("gps_lat"), gps_lon=row.get("gps_lon")))
            raw.sort(key=lambda hit: hit.score, reverse=True)
    allowed = {int(row["id"]): row for row in metadata_rows(policy, resolved)}
    unique = {}
    for hit in raw:
        if hit.photo_id in allowed and hit.photo_id not in unique:
            hit.face_count = int(allowed[hit.photo_id].get("face_count") or 0)
            unique[hit.photo_id] = hit
    results = list(unique.values())
    if q["sort"] != "relevance":
        key = (lambda hit: hit.face_count or 0) if q["sort"].startswith("face_") else (lambda hit: str(allowed[hit.photo_id].get("created_at") if q["time_basis"] == "added" else hit.exif_datetime or ""))
        results.sort(key=lambda hit: (key(hit), hit.photo_id), reverse=q["sort"] not in ("date_asc", "face_asc"))
    response = search._new_search_response(3, results, policy.id, debug={"mode": q["mode"], "description_model": settings.vision.model_name if q["mode"] == "description" else None, "candidate_limit": 2000 if q["mode"] == "description" else None})
    session = search._get_search_session(response.search_id, policy.id)
    if not session:
        raise HTTPException(409, detail="检索会话繁忙，请重试")
    session["gallery_query"] = resolved
    session["gallery_policy"] = policy_version(policy)
    session["gallery_revision"] = library_version()
    return {**response.model_dump(), "resolved_range": [resolved["date_from"], resolved["date_to"]], "query_fingerprint": fingerprint(q)}


class SuggestionRequest(BaseModel):
    config: dict = Field(default_factory=dict)
    search_id: str | None = None
    request_id: str = Field("", max_length=100)
    resolved_range: list[str | None] | None = None


@router.post("/search/suggestions")
def suggestions(payload: SuggestionRequest, request: Request):
    policy = request.state.policy
    q = parse_query(payload.config)
    resolved = freeze(q)
    candidate_ids = None
    if payload.search_id:
        state = search._get_search_session(payload.search_id, policy.id)
        if not state:
            raise HTTPException(404, detail={"code": "search_expired", "message": "检索会话已过期，请重新搜索"})
        if state.get("gallery_policy") != policy_version(policy) or state.get("gallery_revision") != library_version():
            raise HTTPException(409, detail={"code": "library_changed", "message": "照片库或权限已变更，请重新搜索"})
        resolved = state.get("gallery_query", resolved)
        candidate_ids = {int(row["photo_id"]) for row in state["results"]}
    elif payload.resolved_range:
        if len(payload.resolved_range) != 2:
            raise HTTPException(422, detail="日期范围无效")
        resolved = freeze(q, payload.resolved_range)
    rows = metadata_rows(policy, resolved)
    if candidate_ids is not None:
        rows = [row for row in rows if int(row["id"]) in candidate_ids]
    faces = Counter(int(row.get("face_count") or 0) for row in rows)
    years = Counter(str(row.get("exif_datetime") or "")[:4] for row in rows)
    dirs = Counter(str(Path(row["file_path"]).parent) for row in rows)
    items = []
    if not q["face_eq"] and not q["face_min"] and not q["face_max"]:
        for number, count in faces.most_common(3):
            if number > 0:
                items.append({"type": "face", "label": f"检测人脸{number}个", "count": count, "patch": {"face_eq": number, "face_min": None, "face_max": None}, "source": "detected_faces"})
    for year, count in years.most_common(2):
        if year.isdigit() and len(year) == 4 and q["time_basis"] == "photo":
            items.append({"type": "year", "label": year + "年", "count": count, "patch": {"recent_days": None, "date_from": year + "-01-01", "date_to": year + "-12-31"}, "source": "photo_date"})
    if not q["directory"]:
        for directory, count in dirs.most_common(2):
            items.append({"type": "directory", "label": "目录线索：" + Path(directory).name, "count": count, "patch": {"directory": directory}, "source": "directory"})
    no_gps = sum(row.get("gps_lat") is None or row.get("gps_lon") is None for row in rows)
    return {"request_id": payload.request_id, "query_fingerprint": fingerprint(q), "scope": "current_candidates" if candidate_ids is not None else "filtered_library", "total_candidates": len(rows), "no_gps_count": no_gps, "suggestions": items[:7]}


@router.get("/photos/directories")
def directories(request: Request):
    q = freeze(parse_query({}))
    tail, params = where(request.state.policy, q)
    rows = mysql.fetch_all("SELECT DISTINCT file_path FROM photos" + tail, params) or []
    rows = filter_photo_rows(request.state.policy, rows)
    counts = Counter(str(Path(row["file_path"]).parent) for row in rows)
    return {"items": [{"path": path, "name": Path(path).name, "count": count} for path, count in counts.most_common(500)], "truncated": len(counts) > 500}


@router.get("/gallery/capabilities")
def capabilities(request: Request):
    ready = bool(settings.vision.text_model and (Path(settings.vision.text_model) / "model_origin.json").is_file())
    note = "中文画面描述按相关程度返回候选，请结合照片判断。" if ready else "中文模型尚未准备；可先使用参考照片检索或英文描述。"
    return {"description": True, "chinese_description_ready": ready, "description_note": note, "model": settings.vision.model_name, "pretrained": settings.vision.pretrained, "source_read_only": settings.paths.source_read_only, "time_zone": "Asia/Shanghai", "library_version": library_version()}
