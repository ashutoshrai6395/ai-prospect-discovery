"""Shared models and base interface for multi-platform prospect discovery."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from app.schemas import QueryUnderstanding
from app.utils.profiles import contact_links, profile_platform
from app.utils.normalizers import normalize_name

if TYPE_CHECKING:
    from app.services.search_service import SearchService


@dataclass
class RawCandidate:
    """Raw prospect candidate returned by a single platform module."""

    name: str
    platform: str
    profile_url: str
    snippet: str = ""
    location: str | None = None
    source_url: str | None = None
    extra_links: list[tuple[str, str]] = field(default_factory=list)


class BasePlatformDiscoverer(ABC):
    """Abstract base class for independent platform discovery modules."""

    platform_name: str
    site_domain: str = ""

    async def discover(
        self,
        understanding: QueryUnderstanding,
        search_service: SearchService,
        client: httpx.AsyncClient,
    ) -> list[RawCandidate]:
        hits = await search_service.search(self.build_scoped_query(understanding), client)
        candidates = []
        for hit in hits:
            platform = profile_platform(hit.url)
            if not platform or (self.platform_name != "Google" and platform != self.platform_name):
                continue
            name = normalize_name(hit.title)
            if not name:
                continue
            candidates.append(RawCandidate(
                name=name, platform=platform, profile_url=hit.url, source_url=hit.url,
                snippet=hit.snippet, extra_links=contact_links(hit.snippet),
            ))
        return candidates

    def build_scoped_query(self, understanding: QueryUnderstanding) -> str:
        """Build a clean, dynamic platform-scoped search query without hardcoding."""
        terms: list[str] = []
        if self.site_domain:
            terms.append(f"site:{self.site_domain}")
        if understanding.interest:
            terms.append(understanding.interest)
        if understanding.audience and understanding.audience.lower() != understanding.interest.lower():
            terms.append(understanding.audience)
        loc_parts = [
            p
            for p in (
                understanding.location.city,
                understanding.location.state,
                understanding.location.country,
            )
            if p
        ]
        if loc_parts:
            terms.append(" ".join(loc_parts))
        return " ".join(terms)
