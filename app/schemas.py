"""Pydantic schemas and strict input validation for Prospect Discovery API."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ProspectDiscoveryRequest(BaseModel):
    """Request body for POST /prospect-discovery."""

    query: str = Field(
        ...,
        description="Natural-language prospect discovery query.",
        examples=["Football lovers in Washington DC in USA"],
    )

    @field_validator("query")
    def validate_query(cls, value: str) -> str:
        cleaned = CONTROL_CHARS_RE.sub("", value).strip()
        if len(cleaned) < 3:
            raise ValueError("Query must be at least 3 characters long.")
        if len(cleaned) > 300:
            raise ValueError("Query must not exceed 300 characters.")
        return cleaned


class LocationInfo(BaseModel):
    """Structured location extracted from the natural-language query."""

    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class QueryUnderstanding(BaseModel):
    """Structured intent extracted from the user's natural-language query."""

    interest: str = Field(min_length=1, max_length=300)
    audience: str = Field(min_length=1, max_length=300)
    location: LocationInfo = Field(default_factory=LocationInfo)
    target_type: Literal["Individual", "Business"] = "Individual"
    search_keywords: list[str] = Field(default_factory=list)


class SocialLink(BaseModel):
    """Verified public profile or contact link for a prospect."""

    platform: str
    link: str


class ProspectRecord(BaseModel):
    """Consolidated prospect record returned in the API response."""

    name: str
    location: Optional[str] = None
    social_link: list[SocialLink] = Field(default_factory=list)


class ProspectDiscoveryResponse(BaseModel):
    """Top-level response matching the exact assignment JSON contract."""

    success: bool
    query: str
    total_prospects: int
    prospects: list[ProspectRecord]
