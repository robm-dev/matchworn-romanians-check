from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

from .config import Settings


class MwsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MWS Value Monitor/0.1; +local)",
            "X-Platform-Key": settings.mws_platform_key,
            "Accept": "application/json",
        }
        self.client = httpx.Client(timeout=settings.request_timeout_seconds, headers=self.headers)

    def close(self) -> None:
        self.client.close()

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.settings.cache_dir / f"{digest}.json"

    def get_json(self, path: str, params: dict[str, Any] | None = None, cache: bool = True) -> dict[str, Any]:
        url = f"{self.settings.mws_base_url}{path}"
        if params:
            request = self.client.build_request("GET", url, params=params)
            url = str(request.url)
        cache_path = self._cache_path(url)
        if cache and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                data = response.json()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with cache_path.open("w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                time.sleep(self.settings.request_delay_seconds)
                return data
            except Exception as exc:  # httpx has several transient exception types.
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"MWS request failed for {url}: {last_error}")

    def search_products(self, search_term: str) -> dict[str, Any]:
        return self.get_json("/v2/filter/products", {"search_term": search_term}, cache=True)

    def products_for_category(self, category_id: str, page_size: int = 100, cache: bool = False) -> dict[str, Any]:
        return self.get_json(
            "/v2/products/paginated",
            {"category_ids": category_id, "currency_code": self.settings.currency, "offset": 0, "page_size": page_size},
            cache=cache,
        )

    def product_detail(self, slug: str, cache: bool = True) -> dict[str, Any]:
        return self.get_json(f"/v2/products/{slug}", cache=cache)

    def event_by_slug(self, slug: str, cache: bool = True) -> dict[str, Any]:
        return self.get_json(f"/v2/events/{slug}", cache=cache)

    def products_for_event(self, event_id: str, page_size: int = 100, cache: bool = False) -> dict[str, Any]:
        return self.get_json(
            "/v2/products/paginated",
            {
                "event_id": event_id,
                "currency_code": self.settings.currency,
                "offset": 0,
                "page_size": page_size,
            },
            cache=cache,
        )
