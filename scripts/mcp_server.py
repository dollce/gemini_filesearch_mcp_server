#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemini_filesearch.config import resolve_settings_path  # noqa: E402
from gemini_filesearch.mcp import McpApplication, run_stdio  # noqa: E402
from gemini_filesearch.service import GeminiFileSearchService  # noqa: E402
from gemini_filesearch.transport import UrllibJsonTransport  # noqa: E402


def main() -> int:
    settings_path = resolve_settings_path(PROJECT_ROOT)
    app = McpApplication(
        settings_path=settings_path,
        service=GeminiFileSearchService(transport=UrllibJsonTransport()),
    )
    return run_stdio(app)


if __name__ == "__main__":
    raise SystemExit(main())
