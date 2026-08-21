from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Citation:
    uri: str | None
    title: str | None
    text: str | None
    file_search_store: str | None
    page_number: int | None
    custom_metadata: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class SearchResult:
    answer: str
    grounded: bool
    citations: tuple[Citation, ...]
    grounding_supports: tuple[dict[str, Any], ...]
    usage: dict[str, Any]
    model_version: str | None
    response_id: str | None


def parse_generate_content_response(
    payload: Mapping[str, Any],
) -> SearchResult:
    candidates = payload.get("candidates") or []
    candidate = candidates[0] if candidates else {}
    content = candidate.get("content") or {}
    answer = "".join(
        part.get("text", "")
        for part in content.get("parts") or []
        if isinstance(part, Mapping) and not part.get("thought", False)
    )

    grounding = candidate.get("groundingMetadata") or {}
    citations: list[Citation] = []
    for chunk in grounding.get("groundingChunks") or []:
        if not isinstance(chunk, Mapping):
            continue
        context = chunk.get("retrievedContext")
        if not isinstance(context, Mapping):
            continue
        citations.append(
            Citation(
                uri=context.get("uri"),
                title=context.get("title"),
                text=context.get("text"),
                file_search_store=context.get("fileSearchStore"),
                page_number=context.get("pageNumber"),
                custom_metadata=tuple(context.get("customMetadata") or []),
            )
        )

    supports = tuple(grounding.get("groundingSupports") or [])
    usage = dict(payload.get("usageMetadata") or {})
    return SearchResult(
        answer=answer,
        grounded=bool(citations),
        citations=tuple(citations),
        grounding_supports=supports,
        usage=usage,
        model_version=payload.get("modelVersion"),
        response_id=payload.get("responseId"),
    )


def parse_interactions_response(
    payload: Mapping[str, Any],
) -> SearchResult:
    text_blocks: list[str] = []
    citations: list[Citation] = []
    for step in payload.get("steps") or []:
        if not isinstance(step, Mapping) or step.get("type") != "model_output":
            continue
        for block in step.get("content") or []:
            if not isinstance(block, Mapping) or block.get("type") != "text":
                continue
            text_blocks.append(str(block.get("text", "")))
            for annotation in block.get("annotations") or []:
                if (
                    not isinstance(annotation, Mapping)
                    or annotation.get("type") != "file_citation"
                ):
                    continue
                citations.append(
                    Citation(
                        uri=annotation.get("source"),
                        title=annotation.get("file_name"),
                        text=None,
                        file_search_store=annotation.get(
                            "file_search_store"
                        ),
                        page_number=annotation.get("page_number"),
                        custom_metadata=tuple(
                            annotation.get("custom_metadata") or []
                        ),
                    )
                )

    return SearchResult(
        answer="".join(text_blocks),
        grounded=bool(citations),
        citations=tuple(citations),
        grounding_supports=(),
        usage=dict(payload.get("usage") or {}),
        model_version=payload.get("model"),
        response_id=payload.get("id"),
    )
