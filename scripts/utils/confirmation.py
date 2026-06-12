from __future__ import annotations

from typing import Any


VALID_MANUAL_CONFIRMATION_SOURCES = {
    "explicit_user_reply",
    "user_reply",
}

VALID_AUTO_CONFIRMATION_SOURCES = {
    "agent_auto_allowed_by_user",
}


def infer_confirmation_mode(user_text: str) -> dict[str, Any]:
    text = (user_text or "").lower()
    auto_terms = (
        "全自动",
        "自动确认",
        "不用问我",
        "不需要问我",
        "中途不用确认",
        "中途不需要确认",
        "直接跑到底",
        "你自己决定",
        "无需确认",
        "no need to ask",
        "auto confirm",
        "fully automatic",
    )
    if any(term in text for term in auto_terms):
        return {
            "value": "agent_auto_allowed",
            "confidence": 0.95,
            "evidence": ["用户明确允许全自动或自动确认"],
            "reason": "用户授权 Codex 在确认门处自动继续。",
        }
    return {
        "value": "manual_required",
        "confidence": 0.9,
        "evidence": ["用户未明确授权全自动确认"],
        "reason": "默认需要用户显式确认后才能越过确认门。",
    }


def valid_confirmation_source(data: dict[str, Any]) -> bool:
    if data.get("confirmed_by_user") is not True:
        return False
    mode = data.get("confirmation_mode")
    if isinstance(mode, dict):
        mode = mode.get("value")
    source = data.get("confirmation_source")
    if mode == "agent_auto_allowed":
        if source in VALID_MANUAL_CONFIRMATION_SOURCES:
            return True
        if source in VALID_AUTO_CONFIRMATION_SOURCES:
            return bool(str(data.get("auto_confirmation_grant_text", "")).strip())
        return False
    return source in VALID_MANUAL_CONFIRMATION_SOURCES


def confirmation_reason(data: dict[str, Any]) -> str:
    if data.get("confirmed_by_user") is not True:
        return "not_confirmed"
    if valid_confirmation_source(data):
        return "confirmed"
    source = data.get("confirmation_source") or "missing_confirmation_source"
    mode = data.get("confirmation_mode")
    if isinstance(mode, dict):
        mode = mode.get("value")
    if source in VALID_AUTO_CONFIRMATION_SOURCES and not str(data.get("auto_confirmation_grant_text", "")).strip():
        return f"missing_auto_confirmation_grant_text:{source};mode:{mode or 'missing'}"
    return f"invalid_confirmation_source:{source};mode:{mode or 'missing'}"
