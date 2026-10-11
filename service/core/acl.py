from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

from service.core.auth_policy import AuthPolicy
from service.db import mysql


def normalize_path(path_value: str) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    return str(Path(text)).replace("/", "\\").rstrip("\\")


def path_is_under_root(path_value: str, root_value: str) -> bool:
    path_norm = normalize_path(path_value)
    root_norm = normalize_path(root_value)
    if not path_norm or not root_norm:
        return False
    try:
        common = os.path.commonpath(
            [
                os.path.normcase(str(Path(path_norm).resolve(strict=False))),
                os.path.normcase(str(Path(root_norm).resolve(strict=False))),
            ]
        )
    except Exception:
        return False
    return common == os.path.normcase(str(Path(root_norm).resolve(strict=False)))


def policy_can_access_path(policy: AuthPolicy | None, path_value: str) -> bool:
    if not policy:
        return False
    if policy.is_admin:
        return True
    return any(path_is_under_root(path_value, root) for root in (policy.roots or []))


def filter_photo_rows(policy: AuthPolicy | None, rows: list[dict], path_key: str = "file_path") -> list[dict]:
    if not rows:
        return []
    if policy and policy.is_admin:
        return [row for row in rows if isinstance(row, dict)]
    return [
        row
        for row in rows
        if isinstance(row, dict) and policy_can_access_path(policy, row.get(path_key) or "")
    ]


def filter_hits(policy: AuthPolicy | None, hits: list) -> list:
    if not hits:
        return []
    if policy and policy.is_admin:
        return list(hits)
    result = []
    for hit in hits:
        path_value = getattr(hit, "file_path", None)
        if policy_can_access_path(policy, path_value or ""):
            result.append(hit)
    return result


def ensure_photo_allowed(policy: AuthPolicy | None, photo_id: int) -> dict:
    row = mysql.fetch_one(
        """
        SELECT id, file_path, status, file_name, parent_dir_name,
               COALESCE(exif_datetime, file_mtime) AS exif_datetime,
               gps_lat, gps_lon
        FROM photos
        WHERE id=%s
        LIMIT 1
        """,
        (int(photo_id),),
    )
    if not row:
        raise HTTPException(status_code=404, detail="photo not found")
    if str(row.get("status") or "").lower() != "active":
        raise HTTPException(status_code=404, detail="photo not found")
    if not policy_can_access_path(policy, row.get("file_path") or ""):
        raise HTTPException(status_code=403, detail="photo access denied")
    return row
