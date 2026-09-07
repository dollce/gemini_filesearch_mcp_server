#!/usr/bin/env python3
"""Validate local configuration, create a profile, and run Secure MCP Tunnel."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemini_filesearch.config import (  # noqa: E402
    SettingsValidationError,
    load_settings_file,
    resolve_settings_path,
)

PROFILE_NAME = "gemini-filesearch"
PROFILE_DIR = "/tmp/tunnel-client"


def log(message: str) -> None:
    print(f"[startup] {message}", file=sys.stderr, flush=True)


def main() -> int:
    # Allow diagnostic commands such as `docker compose run --rm tunnel tunnel-client --version`.
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])

    log("[1/3] Checking local configuration.")
    tunnel_id = os.environ.get("CONTROL_PLANE_TUNNEL_ID", "")
    if not re.fullmatch(r"tunnel_[a-z0-9]{32}", tunnel_id):
        log("Set CONTROL_PLANE_TUNNEL_ID to your OpenAI Platform Tunnel ID (tunnel_ followed by 32 lowercase letters or digits).")
        return 1

    api_key = os.environ.get("CONTROL_PLANE_API_KEY", "")
    api_key_file = os.environ.get("CONTROL_PLANE_API_KEY_FILE", "")
    if api_key and api_key_file:
        log("Set only one of CONTROL_PLANE_API_KEY and CONTROL_PLANE_API_KEY_FILE.")
        return 1
    key_ref = "env:CONTROL_PLANE_API_KEY"
    if api_key_file:
        try:
            api_key = Path(api_key_file).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            log("Cannot read CONTROL_PLANE_API_KEY_FILE; check the secret mount and permissions.")
            return 1
        key_ref = f"file:{api_key_file}"
    if not api_key or not api_key.isascii() or any(not 0x21 <= ord(char) <= 0x7E for char in api_key):
        log("Set CONTROL_PLANE_API_KEY (or CONTROL_PLANE_API_KEY_FILE) to a nonempty runtime key without whitespace.")
        return 1

    try:
        load_settings_file(resolve_settings_path(PROJECT_ROOT))
    except (OSError, UnicodeError):
        log("Cannot read Gemini settings; check the settings mount and file ownership (DOCKER_UID/DOCKER_GID).")
        return 1
    except json.JSONDecodeError:
        log("Gemini settings must be valid JSON. Edit the mounted settings file.")
        return 1
    except SettingsValidationError as error:
        log(f"Invalid Gemini settings: {error}")
        return 1

    log("[2/3] Creating the container's tunnel profile.")
    os.umask(0o077)
    command = shlex.join([sys.executable, str(PROJECT_ROOT / "scripts" / "mcp_server.py")])
    initialized = subprocess.run(
        [
            "tunnel-client", "init",
            "--sample", "sample_mcp_stdio_local",
            "--profile", PROFILE_NAME,
            "--profile-dir", PROFILE_DIR,
            "--tunnel-id", tunnel_id,
            "--control-plane-api-key-ref", key_ref,
            "--health-listen-addr", "127.0.0.1:8080",
            "--mcp-command", command,
            "--force",
        ],
        check=False,
    )
    if initialized.returncode:
        log("Tunnel profile creation failed; see the tunnel-client error above.")
        return initialized.returncode

    log("[3/3] Starting the tunnel and stdio MCP server; use the health check to confirm readiness.")
    os.execvp(
        "tunnel-client",
        ["tunnel-client", "run", "--profile", PROFILE_NAME, "--profile-dir", PROFILE_DIR],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
