from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil

from service.core.config import settings


@dataclass(frozen=True)
class AuthPolicy:
    id: str
    name: str
    enabled: bool
    is_admin: bool
    password: str
    roots: list[str]
    note: str = ""


@dataclass(frozen=True)
class AuthPolicyStore:
    version: int
    updated_at: str
    default_deny: bool
    policies: list[AuthPolicy]


_CACHE: dict[str, object] = {
    "path": "",
    "mtime": None,
    "store": None,
}


def _config_path() -> Path:
    return Path(settings.auth.policies_json).resolve(strict=False)


def normalize_root(path_value: str) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    return str(Path(text)).replace("/", "\\").rstrip("\\")


def _validate_policy_item(raw: dict, seen_ids: set[str], seen_passwords: set[str]) -> AuthPolicy:
    if not isinstance(raw, dict):
        raise ValueError("policy item must be object")
    policy_id = str(raw.get("id") or "").strip()
    if not policy_id:
        raise ValueError("policy.id required")
    if policy_id in seen_ids:
        raise ValueError(f"duplicate policy.id: {policy_id}")
    seen_ids.add(policy_id)

    password = str(raw.get("password") or "")
    if not password:
        raise ValueError(f"policy.password required: {policy_id}")
    if password in seen_passwords:
        raise ValueError(f"duplicate policy.password not allowed: {policy_id}")
    seen_passwords.add(password)

    roots_raw = raw.get("roots") or []
    if not isinstance(roots_raw, list):
        raise ValueError(f"policy.roots must be list: {policy_id}")
    roots = [normalize_root(v) for v in roots_raw if normalize_root(v)]
    enabled = bool(raw.get("enabled", True))
    is_admin = bool(raw.get("is_admin", False))
    if enabled and not is_admin and not roots:
        raise ValueError(f"non-admin policy.roots required: {policy_id}")

    return AuthPolicy(
        id=policy_id,
        name=str(raw.get("name") or policy_id),
        enabled=enabled,
        is_admin=is_admin,
        password=password,
        roots=roots,
        note=str(raw.get("note") or ""),
    )


def _load_store_from_data(data: dict) -> AuthPolicyStore:
    if not isinstance(data, dict):
        raise ValueError("auth policies root must be object")
    seen_ids: set[str] = set()
    seen_passwords: set[str] = set()
    policies = [
        _validate_policy_item(raw, seen_ids, seen_passwords)
        for raw in (data.get("policies") or [])
    ]
    enabled_count = sum(1 for policy in policies if policy.enabled)
    enabled_admin_count = sum(1 for policy in policies if policy.enabled and policy.is_admin)
    if enabled_count <= 0:
        raise ValueError("no enabled auth policy configured")
    if enabled_admin_count <= 0:
        raise ValueError("at least one enabled admin policy is required")
    return AuthPolicyStore(
        version=int(data.get("version") or 1),
        updated_at=str(data.get("updated_at") or ""),
        default_deny=bool(data.get("default_deny", True)),
        policies=policies,
    )


def _load_store_from_disk(path: Path) -> AuthPolicyStore:
    if not path.exists():
        raise FileNotFoundError(f"auth policies file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return _load_store_from_data(data)


def clear_policy_store_cache() -> None:
    _CACHE["path"] = ""
    _CACHE["mtime"] = None
    _CACHE["store"] = None


def load_policy_store() -> AuthPolicyStore:
    path = _config_path()
    mtime = os.path.getmtime(path)
    cached_path = str(_CACHE.get("path") or "")
    cached_mtime = _CACHE.get("mtime")
    cached_store = _CACHE.get("store")
    if cached_store is not None and cached_path == str(path) and cached_mtime == mtime:
        return cached_store  # type: ignore[return-value]
    store = _load_store_from_disk(path)
    _CACHE["path"] = str(path)
    _CACHE["mtime"] = mtime
    _CACHE["store"] = store
    return store


def serialize_policy_store(store: AuthPolicyStore) -> dict:
    return {
        "version": int(store.version),
        "updated_at": str(store.updated_at or ""),
        "default_deny": bool(store.default_deny),
        "policies": [
            {
                "id": policy.id,
                "name": policy.name,
                "enabled": bool(policy.enabled),
                "is_admin": bool(policy.is_admin),
                "password": policy.password,
                "roots": list(policy.roots or []),
                "note": policy.note,
            }
            for policy in (store.policies or [])
        ],
    }


def save_policy_store(raw_data: dict, actor_policy_id: str = "") -> dict:
    path = _config_path()
    store = _load_store_from_data(raw_data)
    payload = serialize_policy_store(store)
    updated_at = str(raw_data.get("updated_at") or "").strip()
    if not updated_at:
        updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload["updated_at"] = updated_at

    project_dir = Path(settings.config_path).resolve(strict=False).parent
    backup_dir = project_dir / "archive" / "auth_policy_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = ""
    if path.exists():
        backup_file_name = f"{path.name}.bak_{stamp}"
        if actor_policy_id:
            backup_file_name = f"{path.name}.{actor_policy_id}.bak_{stamp}"
        backup_file = backup_dir / backup_file_name
        suffix_index = 1
        while backup_file.exists():
            backup_file = backup_dir / f"{backup_file_name}_{suffix_index}"
            suffix_index += 1
        shutil.copy2(path, backup_file)
        backup_path = str(backup_file)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)
    clear_policy_store_cache()
    loaded = load_policy_store()
    return {
        "config_path": str(path),
        "backup_path": backup_path,
        "store": serialize_policy_store(loaded),
    }


def get_enabled_policies() -> list[AuthPolicy]:
    store = load_policy_store()
    return [policy for policy in store.policies if policy.enabled]


def find_policy_by_password(password: str) -> AuthPolicy | None:
    candidate = str(password or "")
    if not candidate:
        return None
    for policy in get_enabled_policies():
        if policy.password == candidate:
            return policy
    return None


def get_policy_by_id(policy_id: str) -> AuthPolicy | None:
    target = str(policy_id or "").strip()
    if not target:
        return None
    for policy in get_enabled_policies():
        if policy.id == target:
            return policy
    return None
