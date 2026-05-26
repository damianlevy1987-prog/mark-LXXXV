from __future__ import annotations

import os

import keyring

from core.profile_store import get_active_profile_id


def _secret_type_for_var(var_name: str) -> str:
    n = var_name.upper()
    if "GEMINI" in n:
        return "gemini"
    if "OPENAI" in n:
        return "openai"
    if "OPENROUTER" in n:
        return "openrouter"
    if "GROQ" in n:
        return "groq"
    if "TELEGRAM" in n:
        return "telegram"
    if n.startswith("GITHUB_"):
        return "github"
    if "CAPTCHA" in n:
        return "captcha"
    return "misc"


def _service_name(secret_type: str) -> str:
    pid = get_active_profile_id()
    return f"mark-lxxxv:{pid}:{secret_type}"


def get_secret(var_name: str) -> str | None:
    service = _service_name(_secret_type_for_var(var_name))
    return keyring.get_password(service, var_name)


def set_secret(var_name: str, value: str) -> None:
    service = _service_name(_secret_type_for_var(var_name))
    keyring.set_password(service, var_name, value)


PROVIDER_KEY_VARS = {
    # provider_name -> list of env var names (checked in order)
    "gemini": ["GEMINI_API_KEY", "VITE_GOOGLE_API_KEY", "VERTEXAI_API_KEY"],
    "openai": ["OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"],
    "openrouter": ["OPENROUTER_API_KEY", "OPENROUTER_API_KEY_2"],
    "groq": ["GROQ_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
    "hf": ["HF_TOKEN"],
    "telegram": ["TELEGRAM_BOT_TOKEN"],
    "github": ["GITHUB_PAT", "GITHUB_CLIENT_SECRET"],
    "captcha": ["CAPTCHA_SECRET"],
    "kimi": ["KIMI_API_KEY"],
    "zhipuai": ["ZHIPUAI_API_KEY"],
    "firecrawl": ["FIRECRAWL_API_KEY"],
    "fal": ["FAL_AI_KEY"],
    "contabo": ["CONTABO_CLIENT_SECRET"],
    "hostinger": ["HOSTINGER_API_TOKEN"],
}


def get_provider_key(provider: str) -> str | None:
    """Look up an API key for a provider across all known env var names."""
    var_names = PROVIDER_KEY_VARS.get(provider, [])
    for name in var_names:
        val = get_secret(name)
        if val:
            return val
    return None


def import_from_env_once(var_names: list[str]) -> dict[str, str]:
    imported: dict[str, str] = {}
    for name in var_names:
        val = os.getenv(name)
        if not val:
            continue
        if get_secret(name):
            continue
        set_secret(name, val)
        imported[name] = "IMPORTED"
    return imported
