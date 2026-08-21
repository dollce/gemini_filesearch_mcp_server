from __future__ import annotations

from typing import Any


READ_ONLY_EXTERNAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

READ_ONLY_LOCAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

_NULLABLE_STRING: dict[str, Any] = {
    "type": ["string", "null"],
}
_NULLABLE_NUMBER: dict[str, Any] = {
    "type": ["number", "null"],
}
_NULLABLE_INTEGER: dict[str, Any] = {
    "type": ["integer", "null"],
}
_ARBITRARY_OBJECT: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
}

_CITATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "uri": _NULLABLE_STRING,
        "title": _NULLABLE_STRING,
        "text": _NULLABLE_STRING,
        "file_search_store": _NULLABLE_STRING,
        "page_number": _NULLABLE_INTEGER,
        "custom_metadata": {
            "type": "array",
            "items": _ARBITRARY_OBJECT,
        },
    },
    "required": [
        "uri",
        "title",
        "text",
        "file_search_store",
        "page_number",
        "custom_metadata",
    ],
    "additionalProperties": False,
}

_SEARCH_SETTINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "model": {"type": "string"},
        "file_search_store_names": {
            "type": "array",
            "items": {"type": "string"},
        },
        "top_k": {"type": "integer", "minimum": 1},
        "temperature": {"type": "number"},
        "temperature_applied": {"type": "boolean"},
        "api_surface": {"type": "string"},
        "request_timeout_seconds": {"type": "number"},
    },
    "required": [
        "model",
        "file_search_store_names",
        "top_k",
        "temperature",
        "temperature_applied",
        "api_surface",
        "request_timeout_seconds",
    ],
    "additionalProperties": False,
}

SEARCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "answer_status": {
            "type": "string",
            "enum": ["citation_backed", "no_cited_support"],
            "description": (
                "Whether the returned answer has File Search citations. "
                "Uncited provider answer text is withheld."
            ),
        },
        "has_citations": {
            "type": "boolean",
            "description": (
                "True when Gemini returned at least one File Search citation. "
                "This does not prove every claim in the answer."
            ),
        },
        "grounded": {
            "type": "boolean",
            "description": (
                "Backward-compatible alias for has_citations; not a truth score."
            ),
        },
        "citations": {
            "type": "array",
            "items": _CITATION_SCHEMA,
        },
        "grounding_supports": {
            "type": "array",
            "items": _ARBITRARY_OBJECT,
        },
        "usage": _ARBITRARY_OBJECT,
        "model_version": _NULLABLE_STRING,
        "response_id": _NULLABLE_STRING,
        "settings": _SEARCH_SETTINGS_SCHEMA,
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "answer",
        "answer_status",
        "has_citations",
        "grounded",
        "citations",
        "grounding_supports",
        "usage",
        "model_version",
        "response_id",
        "settings",
        "warnings",
    ],
    "additionalProperties": False,
}

_INVENTORY_DOCUMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resource_name": _NULLABLE_STRING,
        "display_name": _NULLABLE_STRING,
        "state": _NULLABLE_STRING,
        "update_time": _NULLABLE_STRING,
    },
    "required": [
        "resource_name",
        "display_name",
        "state",
        "update_time",
    ],
    "additionalProperties": False,
}

INVENTORY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "store_name": {"type": "string"},
                    "documents": {
                        "type": "array",
                        "items": _INVENTORY_DOCUMENT_SCHEMA,
                    },
                    "document_count_returned": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "truncated": {"type": "boolean"},
                },
                "required": [
                    "store_name",
                    "documents",
                    "document_count_returned",
                    "truncated",
                ],
                "additionalProperties": False,
            },
        },
        "total_documents_returned": {
            "type": "integer",
            "minimum": 0,
        },
        "page_size_per_store": {"type": "integer", "minimum": 1},
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "stores",
        "total_documents_returned",
        "page_size_per_store",
        "warnings",
    ],
    "additionalProperties": False,
}

STATUS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "api_key_configured": {"type": "boolean"},
        "settings_file": {"type": "string"},
        "model": _NULLABLE_STRING,
        "file_search_store_names": {
            "type": "array",
            "items": {"type": "string"},
        },
        "top_k": _NULLABLE_INTEGER,
        "temperature": _NULLABLE_NUMBER,
        "request_timeout_seconds": _NULLABLE_NUMBER,
        "supported_models": {
            "type": "array",
            "items": {"type": "string"},
        },
        "temperature_note": {"type": "string"},
    },
    "required": [
        "api_key_configured",
        "settings_file",
        "model",
        "file_search_store_names",
        "top_k",
        "temperature",
        "request_timeout_seconds",
        "supported_models",
        "temperature_note",
    ],
    "additionalProperties": False,
}
