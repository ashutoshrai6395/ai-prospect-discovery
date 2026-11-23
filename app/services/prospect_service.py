"""Main orchestration service for AI-Powered Multi-Platform Prospect Discovery."""

from __future__ import annotations

import asyncio
from typing import Sequence
from collections import deque
from time import monotonic
from app.services.errors import MissingConfiguration, ProviderFailure, RequestLimit

import httpx

from app.config import Settings, get_settings
from app.platforms import (
    FacebookDiscoverer,
    GoogleDiscoverer,
    InstagramDiscoverer,
    LinkedInDiscoverer,
    ThreadsDiscoverer,
    WhatsAppDiscoverer,
    XPlatformDiscoverer,
    YouTubeDiscoverer,
)
from app.platforms.base import BasePlatformDiscoverer, RawCandidate
from app.schemas import ProspectDiscoveryResponse
from app.services.consolidation_service import ConsolidationService
from app.services.deduplication_service import DeduplicationService
from app.services.llm_service import LLMService
from app.services.query_service import QueryService
from app.services.relevance_service import RelevanceService
from app.services.search_service import SearchService


class ProspectService:
    """Coordinates query understanding, multi-platform discovery, filtering, and consolidation."""

    def __init__(
        self,
        settings: Settings | None = None,
        discoverers: Sequence[BasePlatformDiscoverer] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transport = transport
        self._recent: deque[float] = deque()
        self._llm = LLMService(self._settings)
        self._query_service = QueryService(
            self._llm, cache_ttl_seconds=self._settings.cache_ttl_seconds
        )
        self._search_service = SearchService(self._settings)
        self._relevance_service = RelevanceService()
        self._dedup_service = DeduplicationService()
        self._consolidation_service = ConsolidationService()
        self._discoverers: list[BasePlatformDiscoverer] = (
            list(discoverers)
            if discoverers is not None
            else [
                GoogleDiscoverer(),
                LinkedInDiscoverer(),
                XPlatformDiscoverer(),
                YouTubeDiscoverer(self._settings),
                InstagramDiscoverer(),
                WhatsAppDiscoverer(),
                FacebookDiscoverer(),
                ThreadsDiscoverer(),
            ]
        )

    async def discover_prospects(self, query: str) -> ProspectDiscoveryResponse:
        now = monotonic()
        while self._recent and self._recent[0] <= now - 60:
            self._recent.popleft()
        if len(self._recent) >= self._settings.requests_per_minute:
            raise RequestLimit()
        self._recent.append(now)
        if not ((self._settings.google_cse_api_key and self._settings.google_cse_cx) or self._settings.serpapi_api_key):
            raise MissingConfiguration()
        client_kwargs: dict[str, object] = {
            "timeout": httpx.Timeout(self._settings.request_timeout_seconds),
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            understanding = await self._query_service.understand(query, client)
            tasks = [
                discoverer.discover(understanding, self._search_service, client)
                for discoverer in self._discoverers
            ]
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, BaseException):
                    raise batch

        all_candidates = [cand for batch in batches for cand in batch]
        relevant = self._relevance_service.filter_relevant(all_candidates, understanding)
        grouped = self._dedup_service.group_candidates(relevant)
        prospects = self._consolidation_service.consolidate(grouped)

        return ProspectDiscoveryResponse(
            success=True,
            query=query,
            total_prospects=len(prospects),
            prospects=prospects,
        )

