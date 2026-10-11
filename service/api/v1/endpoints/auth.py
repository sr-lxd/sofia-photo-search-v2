import threading

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from service.core.auth import (
    ADMIN_CONFIG_TOKEN_TTL_SECONDS,
    build_admin_config_token,
    clear_auth_cookie,
    get_request_policy,
    is_auth_configured,
    set_auth_cookie,
    verify_admin_config_token,
    verify_password,
)
from service.core.auth_policy import load_policy_store, save_policy_store, serialize_policy_store
from service.core.config import settings
from service.core.runtime_warm import finish_policy_warm, mark_policy_warm_started

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    password: str


class AdminReverifyRequest(BaseModel):
    password: str


def _require_admin_request(request: Request):
    policy = get_request_policy(request)
    if not policy:
        raise HTTPException(status_code=401, detail="未登录，请先输入密码")
    if not bool(policy.is_admin):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return policy


def _require_admin_config_token(request: Request, policy_id: str) -> None:
    token = str(request.headers.get("X-Admin-Config-Token") or "").strip()
    if not token:
        raise HTTPException(status_code=403, detail="请先再次验证管理员密码")
    if not verify_admin_config_token(token, policy_id):
        raise HTTPException(status_code=403, detail="管理员二次验证已失效，请重新验证")


@router.post("/login")
def login(payload: LoginRequest):
    if not is_auth_configured():
        return JSONResponse(status_code=500, content={"ok": False, "message": "服务端未配置可用的权限策略"})
    policy = verify_password(payload.password)
    if not policy:
        return JSONResponse(status_code=401, content={"ok": False, "message": "密码错误"})
    response = JSONResponse(
        {
            "ok": True,
            "message": "登录成功",
            "policy_id": policy.id,
            "policy_name": policy.name,
            "is_admin": bool(policy.is_admin),
        }
    )
    set_auth_cookie(response, policy)
    if not bool(policy.is_admin):
        try:
            from service.api.v1.endpoints.search import warm_policy_search_cache

            mark_policy_warm_started(policy.id)

            def _warm_policy():
                try:
                    warm_policy_search_cache(policy)
                    finish_policy_warm(policy.id, ok=True)
                except Exception:
                    finish_policy_warm(policy.id, ok=False, message="当前用户搜索缓存预热失败")

            threading.Thread(target=_warm_policy, daemon=True).start()
        except Exception:
            pass
    return response


@router.get("/status")
def auth_status(request: Request):
    policy = get_request_policy(request)
    return {
        "ok": True,
        "authenticated": bool(policy),
        "policy_id": policy.id if policy else None,
        "policy_name": policy.name if policy else None,
        "is_admin": bool(policy.is_admin) if policy else False,
    }


@router.post("/logout")
def logout():
    response = JSONResponse({"ok": True, "message": "已退出登录"})
    clear_auth_cookie(response)
    return response


@router.post("/admin/reverify")
def admin_reverify(payload: AdminReverifyRequest, request: Request):
    current_policy = _require_admin_request(request)
    candidate = verify_password(payload.password)
    if not candidate or not bool(candidate.is_admin) or str(candidate.id) != str(current_policy.id):
        return JSONResponse(status_code=401, content={"ok": False, "message": "管理员密码验证失败"})
    token = build_admin_config_token(current_policy.id)
    return {
        "ok": True,
        "message": "管理员二次验证通过",
        "token": token,
        "expires_in": int(ADMIN_CONFIG_TOKEN_TTL_SECONDS),
    }


@router.get("/admin/policies")
def admin_policies(request: Request):
    current_policy = _require_admin_request(request)
    _require_admin_config_token(request, current_policy.id)
    store = load_policy_store()
    return {
        "ok": True,
        "config_path": str(settings.auth.policies_json or ""),
        "store": serialize_policy_store(store),
    }


@router.put("/admin/policies")
def admin_save_policies(request: Request, payload: dict = Body(...)):
    current_policy = _require_admin_request(request)
    _require_admin_config_token(request, current_policy.id)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="策略配置必须是 JSON 对象")
    result = save_policy_store(payload, actor_policy_id=current_policy.id)
    return {
        "ok": True,
        "message": "权限策略已保存并即时生效",
        "config_path": result.get("config_path", ""),
        "backup_path": result.get("backup_path", ""),
        "store": result.get("store"),
    }
