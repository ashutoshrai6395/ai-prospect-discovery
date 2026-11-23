"""Normalization helpers for prospect names, URLs, handles, and locations."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse, urlunparse

NOISE_SUFFIXES = (
    " | LinkedIn",
    " - LinkedIn",
    " (@",
    " • Instagram photos and videos",
    " - YouTube",
    " | Facebook",
    " on X",
    " / X",
    " on Threads",
)


def normalize_name(raw_name: str) -> str:
    """Clean profile titles into a normalized display name."""
    name = (raw_name or "").strip()
    for suffix in NOISE_SUFFIXES:
        idx = name.find(suffix)
        if idx > 0:
            name = name[:idx].strip()
    name = re.sub(r"\s+", " ", name)
    return name.strip(" -|•·")


def normalize_name_key(name: str) -> str:
    """Lowercase alphanumeric key for fuzzy matching."""
    return "".join(c for c in normalize_name(name).casefold() if c.isalnum())


def normalize_url(url: str) -> str:
    """Strip tracking query params and trailing slashes for canonical comparison."""
    cleaned = (url or "").strip()
    if cleaned.startswith("mailto:") or cleaned.startswith("tel:"):
        return cleaned.lower()
    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/") or ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    query = parse_qs(parsed.query)
    if host == "api.whatsapp.com" and path == "/send":
        return "https://wa.me/" + query.get("phone", [""])[0]
    identity = "id=" + query["id"][0] if host == "facebook.com" and path == "/profile.php" and "id" in query else ""
    return urlunparse(("https", host, path, "", identity, ""))


def extract_handle_from_url(url: str) -> str:
    """Extract social username/handle from common profile URLs."""
    parsed = urlparse((url or "").strip())
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return ""
    last = parts[-1].lstrip("@").lower()
    if last in {"in", "pub", "channel", "c", "user", "profile.php"} and len(parts) > 1:
        return parts[-2].lstrip("@").lower()
    if parts[0] in {"in", "pub", "c", "user"} and len(parts) > 1:
        return parts[1].lstrip("@").lower()
    return last


def format_location(city: str | None, state: str | None, country: str | None) -> str | None:
    """Format non-empty location parts cleanly."""
    parts = [p.strip() for p in (city, state, country) if p and p.strip()]
    return ", ".join(parts) if parts else None
