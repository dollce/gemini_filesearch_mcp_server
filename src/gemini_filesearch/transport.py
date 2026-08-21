from __future__ import annotations

import json
import socket
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .redaction import redact_text


class GeminiClientError(RuntimeError):
    """Safe error that can be returned by the MCP boundary."""


class GeminiApiError(GeminiClientError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Gemini API error ({status_code}): {message}")


class GeminiApiTimeoutError(GeminiClientError):
    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(
            "Gemini File Search timed out after "
            f"{timeout_seconds:g} seconds. Retry once; if it repeats, lower "
            "top_k or choose a faster supported model."
        )


class GeminiApiConnectionError(GeminiClientError):
    pass


class UrllibJsonTransport:
    def __init__(self, *, opener: Callable[..., Any] = urlopen) -> None:
        self._opener = opener

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )
        return self._send_json(
            request,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )

    def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request = Request(
            url,
            headers=dict(headers),
            method="GET",
        )
        return self._send_json(
            request,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )

    def _send_json(
        self,
        request: Request,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            api_key = next(
                (
                    value
                    for key, value in headers.items()
                    if key.lower() == "x-goog-api-key"
                ),
                "",
            )
            try:
                error_payload = json.loads(error.read().decode("utf-8"))
                message = str(
                    (error_payload.get("error") or {}).get(
                        "message",
                        error.reason,
                    )
                )
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                message = str(error.reason)
            message = redact_text(message, secret_values=(api_key,))
            raise GeminiApiError(error.code, message[:1000]) from None
        except (TimeoutError, socket.timeout):
            raise GeminiApiTimeoutError(timeout_seconds) from None
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise GeminiApiTimeoutError(timeout_seconds) from None
            api_key = next(
                (
                    value
                    for key, value in headers.items()
                    if key.lower() == "x-goog-api-key"
                ),
                "",
            )
            message = redact_text(
                str(error.reason),
                secret_values=(api_key,),
            )
            raise GeminiApiConnectionError(
                f"Could not reach Gemini File Search: {message[:1000]}"
            ) from None
        except (TypeError, ValueError) as error:
            api_key = next(
                (
                    value
                    for key, value in headers.items()
                    if key.lower() == "x-goog-api-key"
                ),
                "",
            )
            message = redact_text(
                str(error),
                secret_values=(api_key,),
            )
            raise GeminiApiConnectionError(
                "Could not send the Gemini File Search request: "
                f"{message[:1000]}"
            ) from None
        if not isinstance(result, Mapping):
            raise ValueError("Gemini returned a non-object JSON response")
        return result
