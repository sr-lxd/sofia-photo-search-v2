from __future__ import annotations

import threading
import time


_LOCK = threading.RLock()
_startup_state = {
    "running": False,
    "ready": False,
    "message": "未开始",
    "updated_at": 0.0,
    "components": {
        "face_index": {"ready": False, "message": "未加载"},
        "vision_index": {"ready": False, "message": "未加载"},
        "face_engine": {"ready": False, "message": "未加载"},
        "vision_engine": {"ready": False, "message": "未加载"},
    },
}
_policy_states: dict[str, dict] = {}


def _now_ts() -> float:
    return time.time()


def mark_startup_warm_started() -> None:
    with _LOCK:
        _startup_state["running"] = True
        _startup_state["ready"] = False
        _startup_state["message"] = "系统预热中"
        _startup_state["updated_at"] = _now_ts()


def set_startup_component(name: str, ready: bool, message: str = "") -> None:
    with _LOCK:
        comp = _startup_state["components"].setdefault(str(name or "unknown"), {"ready": False, "message": ""})
        comp["ready"] = bool(ready)
        comp["message"] = str(message or ("已就绪" if ready else "未就绪"))
        _startup_state["updated_at"] = _now_ts()


def finish_startup_warm(ok: bool = True, message: str = "") -> None:
    with _LOCK:
        _startup_state["running"] = False
        _startup_state["ready"] = bool(ok)
        _startup_state["message"] = str(message or ("系统搜索已就绪" if ok else "系统预热未完成"))
        _startup_state["updated_at"] = _now_ts()


def get_startup_warm_status() -> dict:
    with _LOCK:
        return {
            "running": bool(_startup_state["running"]),
            "ready": bool(_startup_state["ready"]),
            "message": str(_startup_state["message"]),
            "updated_at": float(_startup_state["updated_at"] or 0.0),
            "components": {
                key: {
                    "ready": bool(value.get("ready")),
                    "message": str(value.get("message") or ""),
                }
                for key, value in dict(_startup_state.get("components") or {}).items()
            },
        }


def mark_policy_warm_started(policy_id: str) -> None:
    target = str(policy_id or "").strip()
    if not target:
        return
    with _LOCK:
        _policy_states[target] = {
            "running": True,
            "ready": False,
            "message": "正在准备当前用户搜索缓存",
            "updated_at": _now_ts(),
        }


def finish_policy_warm(policy_id: str, ok: bool = True, message: str = "") -> None:
    target = str(policy_id or "").strip()
    if not target:
        return
    with _LOCK:
        _policy_states[target] = {
            "running": False,
            "ready": bool(ok),
            "message": str(message or ("当前用户搜索已就绪" if ok else "当前用户搜索缓存未完成")),
            "updated_at": _now_ts(),
        }


def get_policy_warm_status(policy_id: str | None) -> dict | None:
    target = str(policy_id or "").strip()
    if not target:
        return None
    with _LOCK:
        state = _policy_states.get(target)
        if not state:
            return None
        return {
            "running": bool(state.get("running")),
            "ready": bool(state.get("ready")),
            "message": str(state.get("message") or ""),
            "updated_at": float(state.get("updated_at") or 0.0),
        }
