# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM python:3.12-slim-bookworm AS tunnel-download

ARG TARGETARCH

# Pin both the release and its official archive digest for reproducible installs.
RUN python3 - <<'PY'
import hashlib
import os
from pathlib import Path
import urllib.request
import zipfile

version = "0.0.14"
checksums = {
    "amd64": "15bd17e805cad39d412199115bb9e10a978dd35258a114cdf25dd2ae6681c7d3",
    "arm64": "2de3fb879a18edb847e0313592c912f1983685488290a7fdba7ac403e6a4fb0a",
}
arch = os.environ["TARGETARCH"]
if arch not in checksums:
    raise SystemExit(f"Unsupported architecture: {arch}; use amd64 or arm64")
asset = f"tunnel-client-v{version}-linux-{arch}"
url = f"https://github.com/openai/tunnel-client/releases/download/v{version}/{asset}.zip"
archive = Path("/tmp/tunnel-client.zip")
with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as output:
    while chunk := response.read(1024 * 1024):
        output.write(chunk)
with archive.open("rb") as source:
    actual = hashlib.file_digest(source, "sha256").hexdigest()
if actual != checksums[arch]:
    raise SystemExit("tunnel-client archive SHA256 mismatch")
destination = Path("/out")
destination.mkdir()
with zipfile.ZipFile(archive) as bundle:
    for name in ("tunnel-client", "LICENSE", "NOTICE", f"{asset}-licenses.txt"):
        (destination / name).write_bytes(bundle.read(name))
(destination / "tunnel-client").chmod(0o755)
PY

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GEMINI_FILESEARCH_SETTINGS=/run/secrets/gemini_settings

WORKDIR /app
COPY --from=tunnel-download /out/tunnel-client /usr/local/bin/tunnel-client
COPY --from=tunnel-download /out/LICENSE /out/NOTICE /out/*-licenses.txt /usr/local/share/tunnel-client/
COPY src/ ./src/
COPY scripts/mcp_server.py scripts/docker_entrypoint.py ./scripts/

USER 10001:10001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["tunnel-client", "health", "--url", "http://127.0.0.1:8080", "--require-control-plane-poll"]

ENTRYPOINT ["python3", "/app/scripts/docker_entrypoint.py"]
