from __future__ import annotations

import os

import keyring


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
    return f"mark-lxxxv:{secret_type}"


def get_secret(var_name: str) -> str | None:
    service = _service_name(_secret_type_for_var(var_name))
    return keyring.get_password(service, var_name)


def set_secret(var_name: str, value: str) -> None:
    service = _service_name(_secret_type_for_var(var_name))
    keyring.set_password(service, var_name, value)


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
