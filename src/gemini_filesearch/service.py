from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .config import Settings
from .request import (
    build_generate_content_request,
    build_interactions_request,
)
from .response import (
    SearchResult,
    parse_generate_content_response,
    parse_interactions_response,
)
from .transport import GeminiClientError


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODELS_IGNORING_TEMPERATURE = {
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
}


class JsonTransport(Protocol):
    def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class SearchOutcome:
    result: SearchResult
    api_surface: str
    temperature_applied: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class InventoryDocument:
    resource_name: str | None
    display_name: str | None
    state: str | None
    update_time: str | None


@dataclass(frozen=True)
class StoreInventory:
    store_name: str
    documents: tuple[InventoryDocument, ...]
    truncated: bool


@dataclass(frozen=True)
class InventoryOutcome:
    stores: tuple[StoreInventory, ...]
    total_documents_returned: int
    warnings: tuple[str, ...]


INVENTORY_PAGE_SIZE = 20
INVENTORY_REQUEST_TIMEOUT_SECONDS = 15.0


class GeminiFileSearchService:
    def __init__(
        self,
        *,
        transport: JsonTransport,
    ) -> None:
        self._transport = transport

    def inventory(self, settings: Settings) -> InventoryOutcome:
        store_names = settings.file_search_store_names
        worker_count = min(len(store_names), 4)
        if worker_count == 1:
            stores = (self._inventory_store(store_names[0], settings),)
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                stores = tuple(
                    executor.map(
                        lambda store_name: self._inventory_store(
                            store_name,
                            settings,
                        ),
                        store_names,
                    )
                )
        truncated_stores = [
            store.store_name for store in stores if store.truncated
        ]
        warnings = (
            (
                "Inventory returns at most 20 documents per store; one or more "
                "stores contain additional documents."
            ),
        ) if truncated_stores else ()
        return InventoryOutcome(
            stores=stores,
            total_documents_returned=sum(
                len(store.documents) for store in stores
            ),
            warnings=warnings,
        )

    def _inventory_store(
        self,
        store_name: str,
        settings: Settings,
    ) -> StoreInventory:
        timeout_seconds = min(
            settings.request_timeout_seconds,
            INVENTORY_REQUEST_TIMEOUT_SECONDS,
        )
        response = self._transport.get_json(
            url=(
                f"{GEMINI_API_BASE_URL}/{store_name}/documents"
                f"?pageSize={INVENTORY_PAGE_SIZE}"
            ),
            headers={"x-goog-api-key": settings.api_key},
            timeout_seconds=timeout_seconds,
        )
        documents: list[InventoryDocument] = []
        for item in response.get("documents") or []:
            if not isinstance(item, Mapping):
                continue
            documents.append(
                InventoryDocument(
                    resource_name=self._optional_string(item.get("name")),
                    display_name=self._optional_string(
                        item.get("displayName")
                        or item.get("display_name")
                    ),
                    state=self._optional_string(item.get("state")),
                    update_time=self._optional_string(
                        item.get("updateTime")
                        or item.get("update_time")
                    ),
                )
            )
        return StoreInventory(
            store_name=store_name,
            documents=tuple(documents),
            truncated=bool(
                response.get("nextPageToken")
                or response.get("next_page_token")
            ),
        )

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    def search(self, query: str, settings: Settings) -> SearchOutcome:
        if settings.model == "gemini-3.7-flash":
            return self._search_interactions(query, settings)

        temperature_applied = (
            settings.model not in MODELS_IGNORING_TEMPERATURE
        )
        url = (
            f"{GEMINI_API_BASE_URL}/models/"
            f"{settings.model}:generateContent"
        )
        response = self._transport.post_json(
            url=url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.api_key,
            },
            payload=build_generate_content_request(
                query,
                settings,
                include_temperature=temperature_applied,
            ),
            timeout_seconds=settings.request_timeout_seconds,
        )
        return SearchOutcome(
            result=parse_generate_content_response(response),
            api_surface="generateContent",
            temperature_applied=temperature_applied,
            warnings=(
                ()
                if temperature_applied
                else (
                    "temperature is ignored by this Gemini model and was not "
                    "sent.",
                )
            ),
        )

    def _search_interactions(
        self,
        query: str,
        settings: Settings,
    ) -> SearchOutcome:
        response = self._transport.post_json(
            url=f"{GEMINI_API_BASE_URL}/interactions",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.api_key,
            },
            payload=build_interactions_request(query, settings),
            timeout_seconds=settings.request_timeout_seconds,
        )
        status = response.get("status")
        if not isinstance(status, str) or status not in {
            "completed",
            "incomplete",
        }:
            known_status = (
                status
                if isinstance(status, str) and status in {
                    "failed",
                    "cancelled",
                    "budget_exceeded",
                    "queued",
                    "in_progress",
                }
                else "unknown"
            )
            raise GeminiClientError(
                "Gemini interaction did not complete "
                f"(status: {known_status}). Retry once."
            )
        warnings = [
            "temperature is not supported by the Gemini Interactions API "
            "and was not sent."
        ]
        if status == "incomplete":
            warnings.append(
                "Gemini returned an incomplete interaction; the response may "
                "be partial."
            )
        return SearchOutcome(
            result=parse_interactions_response(response),
            api_surface="interactions",
            temperature_applied=False,
            warnings=tuple(warnings),
        )
