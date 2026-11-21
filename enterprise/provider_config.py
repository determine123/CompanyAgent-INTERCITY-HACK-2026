"""Pinned, environment-only LLM provider selection for bounded tool calls.

Never accept a model-supplied endpoint, request URL, or secret. The chosen
provider is deployment configuration, not an Agent/Skill permission.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    endpoint: str
    model: str
    api_key: str


_B1X_ENDPOINT = "https://token.b1x.work/v1/chat/completions"
_TOKENDANCE_ENDPOINT = "https://tokendance.space/gateway/v1/chat/completions"
_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}$")


def resolve_provider(*, provider: str | None = None, api_key: str | None = None) -> ProviderConfig:
    name = (provider if provider is not None else os.getenv("COMPANYAGENT_MODEL_PROVIDER", "b1x")).strip().lower()
    if name == "b1x":
        model = "deepseek-v4.1-flash-1017"
        endpoint = _B1X_ENDPOINT
        secret = api_key if api_key is not None else os.getenv("B1X_API_KEY", "")
    elif name == "tokendance":
        # Explicit model ID: not every published model supports Chat Completions tool calls.
        model = os.getenv("TOKENDANCE_MODEL", "").strip()
        endpoint = _TOKENDANCE_ENDPOINT
        secret = api_key if api_key is not None else os.getenv("TOKENDANCE_API_KEY", "")
    else:
        raise ValueError("仅允许 b1x 或 tokendance 模型服务商")
    if model and not _MODEL_ID_PATTERN.fullmatch(model):
        raise ValueError("模型 ID 不符合受限格式")
    if any(ch in secret for ch in "\r\n"):
        raise ValueError("模型密钥格式无效")
    return ProviderConfig(name=name, endpoint=endpoint, model=model, api_key=secret.strip())


def provider_configured() -> bool:
    try:
        config = resolve_provider()
        return bool(config.model and config.api_key)
    except ValueError:
        return False


def provider_name() -> str:
    """Safe display string without exposing configuration secrets."""
    try:
        return resolve_provider().name
    except ValueError:
        return "invalid"
