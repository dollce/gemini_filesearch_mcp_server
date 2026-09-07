from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SUPPORTED_FILE_SEARCH_MODELS = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
)
DEFAULT_REQUEST_TIMEOUT_SECONDS = 45.0
MIN_REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REQUEST_TIMEOUT_SECONDS = 75.0
REQUIRED_SETTINGS_KEYS = (
    "model",
    "file_search_store_names",
    "top_k",
    "temperature",
)


class SettingsValidationError(ValueError):
    """Raised when the selected settings file is not usable."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    file_search_store_names: tuple[str, ...]
    top_k: int
    temperature: float
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS


def resolve_api_key(
    raw: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> Any:
    """Select the key without validating it, including for the status tool."""
    values = os.environ if environ is None else environ
    if "GEMINI_API_KEY" in values:
        # An explicitly empty environment value must not revive an old JSON key.
        return values["GEMINI_API_KEY"]
    return raw.get("GEMINI_API_KEY", "")


def load_settings_dict(
    raw: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> Settings:
    if not isinstance(raw, Mapping):
        raise SettingsValidationError(
            "settings file must contain a JSON object"
        )

    missing_keys = [
        key for key in REQUIRED_SETTINGS_KEYS if key not in raw
    ]
    if missing_keys:
        raise SettingsValidationError(
            "settings file is missing required keys: "
            + ", ".join(missing_keys)
        )

    api_key_value = resolve_api_key(raw, environ)
    if not isinstance(api_key_value, str):
        raise SettingsValidationError("GEMINI_API_KEY must be a string")
    api_key = api_key_value.strip()
    if not api_key:
        raise SettingsValidationError(
            "GEMINI_API_KEY is empty or missing. Set it in the environment "
            "(.env for Docker Compose), or in the settings file for legacy setups."
        )
    if len(api_key) < 8:
        raise SettingsValidationError(
            "GEMINI_API_KEY must contain at least 8 characters"
        )
    if not api_key.isascii() or any(
        not 0x21 <= ord(character) <= 0x7E for character in api_key
    ):
        raise SettingsValidationError(
            "GEMINI_API_KEY must contain printable ASCII characters "
            "without whitespace"
        )

    model_value = raw["model"]
    if not isinstance(model_value, str):
        raise SettingsValidationError("model must be a string")
    model = model_value.strip()
    if model not in SUPPORTED_FILE_SEARCH_MODELS:
        choices = ", ".join(SUPPORTED_FILE_SEARCH_MODELS)
        raise SettingsValidationError(f"model must be one of: {choices}")

    top_k = raw["top_k"]
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise SettingsValidationError("top_k must be a positive integer")

    temperature = raw["temperature"]
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not 0.0 <= temperature <= 2.0
    ):
        raise SettingsValidationError(
            "temperature must be between 0.0 and 2.0"
        )

    request_timeout_seconds = raw.get(
        "request_timeout_seconds",
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    if (
        isinstance(request_timeout_seconds, bool)
        or not isinstance(request_timeout_seconds, (int, float))
        or not MIN_REQUEST_TIMEOUT_SECONDS
        <= request_timeout_seconds
        <= MAX_REQUEST_TIMEOUT_SECONDS
    ):
        raise SettingsValidationError(
            "request_timeout_seconds must be between 5 and 75"
        )

    store_names = raw["file_search_store_names"]
    if not isinstance(store_names, list) or not store_names:
        raise SettingsValidationError(
            "file_search_store_names must contain at least one store"
        )

    normalized_store_names: list[str] = []
    for store_name in store_names:
        if not isinstance(store_name, str):
            raise SettingsValidationError(
                "every store must use the full fileSearchStores/ resource name"
            )
        normalized_store_name = store_name.strip()
        if not re.fullmatch(
            r"fileSearchStores/[A-Za-z0-9._~-]+",
            normalized_store_name,
        ):
            raise SettingsValidationError(
                "every store must use the full fileSearchStores/ resource name"
            )
        normalized_store_names.append(normalized_store_name)

    return Settings(
        api_key=api_key,
        model=model,
        file_search_store_names=tuple(normalized_store_names),
        top_k=top_k,
        temperature=float(temperature),
        request_timeout_seconds=float(request_timeout_seconds),
    )


def load_settings_file(
    settings_path: Path,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    return load_settings_dict(raw, environ)


def resolve_settings_path(
    project_root: Path,
    environ: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    explicit = values.get("GEMINI_FILESEARCH_SETTINGS")
    if explicit:
        return Path(explicit).expanduser()
    return project_root / "config" / "settings.json"
