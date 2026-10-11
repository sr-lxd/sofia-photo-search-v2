from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Request
from starlette.responses import Response

from service.core.auth_policy import AuthPolicy, find_policy_by_password, get_policy_by_id
from service.core.config import settings

AUTH_COOKIE_NAME = settings.auth.cookie_name
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
ADMIN_CONFIG_TOKEN_TTL_SECONDS = 60 * 30  # 30 minutes


def _legacy_password() -> str:
    return (settings.auth.password or "").strip()


def _signing_secret() -> str:
    return (settings.auth.session_secret or settings.auth.password or "").strip()


def _build_legacy_auth_token(password: str) -> str:
    raw = f"sofia-photo-search::{password}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def expected_auth_token() -> str:
    return _build_legacy_auth_token(_legacy_password())


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padded = text + ("=" * ((4 - len(text) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _sign_payload(payload_raw: bytes) -> str:
    secret = _signing_secret()
    if not secret:
        raise RuntimeError("auth session secret not configured")
    sig = hmac.new(secret.encode("utf-8"), payload_raw, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _build_session_token(policy_id: str) -> str:
    payload = {
        "policy_id": str(policy_id or "").strip(),
        "issued_at": int(time.time()),
    }
    payload_raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64url_encode(payload_raw)}.{_sign_payload(payload_raw)}"


def _parse_session_token(token: str) -> dict[str, Any] | None:
    raw = str(token or "").strip()
    if "." not in raw:
        return None
    payload_text, signature = raw.split(".", 1)
    try:
        payload_raw = _b64url_decode(payload_text)
    except Exception:
        return None
    expected_sig = _sign_payload(payload_raw)
    if not hmac.compare_digest(signature, expected_sig):
        return None
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def is_auth_configured() -> bool:
    try:
        return len(find_policy_candidates()) > 0
    except Exception:
        return False


def find_policy_candidates() -> list[AuthPolicy]:
    from service.core.auth_policy import get_enabled_policies

    return list(get_enabled_policies())


def _legacy_request_policy() -> AuthPolicy:
    return AuthPolicy(
        id="legacy_admin",
        name="管理员",
        enabled=True,
        is_admin=True,
        password=_legacy_password(),
        roots=[],
        note="legacy db2.ini password fallback",
    )


def verify_password(password: str) -> AuthPolicy | None:
    policy = find_policy_by_password(password)
    if policy:
        return policy
    legacy = _legacy_password()
    if legacy and str(password or "") == legacy:
        admin_policy = get_policy_by_id("admin")
        if admin_policy:
            return admin_policy
    return None


def get_request_policy(request: Request) -> AuthPolicy | None:
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    payload = _parse_session_token(token)
    if payload:
        policy_id = str(payload.get("policy_id") or "").strip()
        policy = get_policy_by_id(policy_id)
        if policy:
            return policy
        return None
    if not token:
        return None
    legacy = _legacy_password()
    if legacy and hmac.compare_digest(token, expected_auth_token()):
        return _legacy_request_policy()
    return None


def is_authenticated_request(request: Request) -> bool:
    return get_request_policy(request) is not None


def set_auth_cookie(response: Response, policy: AuthPolicy) -> None:
    value = _build_session_token(policy.id)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=value,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME)


def build_admin_config_token(policy_id: str) -> str:
    now = int(time.time())
    payload = {
        "policy_id": str(policy_id or "").strip(),
        "purpose": "admin_config",
        "issued_at": now,
        "expires_at": now + ADMIN_CONFIG_TOKEN_TTL_SECONDS,
    }
    payload_raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64url_encode(payload_raw)}.{_sign_payload(payload_raw)}"


def verify_admin_config_token(token: str, policy_id: str) -> bool:
    payload = _parse_session_token(token)
    if not payload:
        return False
    if str(payload.get("purpose") or "") != "admin_config":
        return False
    if str(payload.get("policy_id") or "").strip() != str(policy_id or "").strip():
        return False
    try:
        expires_at = int(payload.get("expires_at") or 0)
    except Exception:
        return False
    return expires_at > int(time.time())
