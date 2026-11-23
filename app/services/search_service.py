"""Authorized search with bounded caching, concurrency and provider fallback."""
import asyncio
from dataclasses import dataclass
from time import monotonic

import httpx

from app.config import Settings
from app.services.errors import MissingConfiguration, ProviderFailure

@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str = ""

class SearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.limit = asyncio.Semaphore(settings.max_concurrent_requests)
        self.cache: dict[str, tuple[float, list[SearchHit]]] = {}

    async def search(self, query: str, client: httpx.AsyncClient) -> list[SearchHit]:
        settings = self.settings
        key = query.casefold()
        cached = self.cache.get(key)
        if cached and monotonic() < cached[0]:
            return cached[1]
        providers = []
        size = min(settings.max_results_per_platform, 10)
        if settings.google_cse_api_key and settings.google_cse_cx:
            providers.append(("https://www.googleapis.com/customsearch/v1",
                              {"cx": settings.google_cse_cx, "key": settings.google_cse_api_key, "num": size},
                              "items", "link"))
        if settings.serpapi_api_key:
            providers.append(("https://serpapi.com/search.json",
                              {"engine": "google", "api_key": settings.serpapi_api_key, "num": size},
                              "organic_results", "link"))
        if not providers:
            raise MissingConfiguration()
        async with self.limit:
            for url, params, field, link in providers:
                try:
                    response = await client.get(url, params={**params, "q": query})
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict) or "error" in body:
                        continue
                    if field not in body and not ("searchInformation" in body or "search_information" in body):
                        continue
                    rows = body.get(field, [])
                    if not isinstance(rows, list):
                        continue
                    hits = [SearchHit(row["title"], row[link], row.get("snippet") or "")
                            for row in rows[:size] if isinstance(row, dict) and
                            all(isinstance(row.get(k), str) for k in ("title", link)) and
                            isinstance(row.get("snippet") or "", str)]
                except (httpx.HTTPError, ValueError):
                    continue
                if len(self.cache) >= 512:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[key] = (monotonic() + settings.cache_ttl_seconds, hits)
                return hits
        raise ProviderFailure()
