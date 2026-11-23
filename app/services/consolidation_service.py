"""Consolidates grouped platform candidates into final ProspectRecord objects."""

from __future__ import annotations

from app.platforms.base import RawCandidate
from app.schemas import ProspectRecord, SocialLink
from app.utils.normalizers import normalize_name, normalize_url
from app.utils.validators import is_safe_public_url


class ConsolidationService:
    """Builds deduplicated ProspectRecord items with validated social_link arrays."""

    def consolidate(self, groups: list[list[RawCandidate]]) -> list[ProspectRecord]:
        prospects: list[ProspectRecord] = []
        for group in groups:
            if not group:
                continue

            primary = group[0]
            name = normalize_name(primary.name)
            location = next((c.location for c in group if c.location), None)

            links: list[SocialLink] = []
            seen_links: set[str] = set()

            for candidate in group:
                if is_safe_public_url(candidate.profile_url):
                    norm = normalize_url(candidate.profile_url)
                    if norm not in seen_links:
                        seen_links.add(norm)
                        links.append(
                            SocialLink(platform=candidate.platform, link=candidate.profile_url)
                        )
                for plat, link in candidate.extra_links:
                    norm_extra = normalize_url(link)
                    if norm_extra not in seen_links:
                        seen_links.add(norm_extra)
                        links.append(SocialLink(platform=plat, link=link))

            if name and links:
                prospects.append(
                    ProspectRecord(
                        name=name,
                        location=location,
                        social_link=links,
                    )
                )
        return prospects
