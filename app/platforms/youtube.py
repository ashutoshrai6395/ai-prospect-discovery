"""YouTube public creator and channel discovery module (YouTube Data API v3 + search fallback)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.config import Settings
from app.platforms.base import BasePlatformDiscoverer, RawCandidate
from app.schemas import QueryUnderstanding
from app.utils.normalizers import format_location, normalize_name
from app.utils.profiles import contact_links, profile_platform

if TYPE_CHECKING:
    from app.services.search_service import SearchService


class YouTubeDiscoverer(BasePlatformDiscoverer):
    """Discovers public YouTube channels using YouTube Data API v3 or authorized search."""

    platform_name = "YouTube"
    site_domain = "youtube.com"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.youtube_api_key
        self._max_results = min(50, settings.max_results_per_platform)

    async def discover(
        self,
        understanding: QueryUnderstanding,
        search_service: SearchService,
        client: httpx.AsyncClient,
    ) -> list[RawCandidate]:
        loc = format_location(
            understanding.location.city,
            understanding.location.state,
            understanding.location.country,
        )
        if self._api_key:
            try:
                return await self._discover_via_api(understanding, loc, client)
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                pass
        return await super().discover(understanding, search_service, client)

    async def _discover_via_api(
        self,
        understanding: QueryUnderstanding,
        loc: str | None,
        client: httpx.AsyncClient,
    ) -> list[RawCandidate]:
        q = " ".join(p for p in [understanding.interest, understanding.audience, loc] if p)
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "channel",
                "q": q,
                "maxResults": self._max_results,
                "key": self._api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ValueError("Invalid YouTube response")
        candidates: list[RawCandidate] = []
        for item in data["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("snippet"), dict) or not isinstance(item.get("id"), dict):
                continue
            snippet = item.get("snippet", {})
            channel_id = item.get("id", {}).get("channelId")
            raw_title = snippet.get("channelTitle") or snippet.get("title")
            title = normalize_name(raw_title) if isinstance(raw_title, str) else ""
            if not channel_id or not title:
                continue
            url = f"https://www.youtube.com/channel/{channel_id}"
            desc = snippet.get("description", "")
            if not isinstance(desc, str) or profile_platform(url) != self.platform_name:
                continue
            extra = contact_links(desc)
            candidates.append(
                RawCandidate(
                    name=title,
                    platform=self.platform_name,
                    profile_url=url,
                    snippet=desc,
                    source_url=url,
                    extra_links=extra,
                )
            )
        return candidates
