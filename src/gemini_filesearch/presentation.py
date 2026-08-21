from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .config import Settings
from .redaction import redact_value
from .service import SearchOutcome


def build_safe_search_output(
    outcome: SearchOutcome,
    settings: Settings,
) -> dict[str, Any]:
    result = outcome.result
    has_citations = bool(result.citations)
    provider_answer = result.answer.strip()
    answer_withheld = bool(provider_answer) and not has_citations
    answer = (
        result.answer
        if has_citations
        else (
            "The configured Gemini File Search stores did not return "
            "citation-backed evidence for this question."
        )
    )
    warnings = list(outcome.warnings)
    if answer_withheld:
        warnings.append(
            "Gemini returned answer text without File Search citations; the "
            "uncited provider answer was withheld."
        )
    raw_output: dict[str, Any] = {
        "answer": answer,
        "answer_status": (
            "citation_backed" if has_citations else "no_cited_support"
        ),
        "has_citations": has_citations,
        "grounded": result.grounded,
        "citations": [asdict(citation) for citation in result.citations],
        "grounding_supports": list(result.grounding_supports),
        "usage": result.usage,
        "model_version": result.model_version,
        "response_id": result.response_id,
        "settings": {
            "model": settings.model,
            "file_search_store_names": list(
                settings.file_search_store_names
            ),
            "top_k": settings.top_k,
            "temperature": settings.temperature,
            "temperature_applied": outcome.temperature_applied,
            "api_surface": outcome.api_surface,
            "request_timeout_seconds": settings.request_timeout_seconds,
        },
        "warnings": warnings,
    }
    return redact_value(
        raw_output,
        secret_values=(settings.api_key,),
    )
