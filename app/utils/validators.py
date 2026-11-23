"""Security-first URL, email, phone, and WhatsApp validators (with SSRF protection)."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s\(\)]{7,16}\d)")
WHATSAPP_URL_RE = re.compile(
    r"https?://(?:wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com)/[^\s<>\"']+",
    re.IGNORECASE,
)
DOMAIN_LABEL_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")

GENERIC_SEARCH_PATH_FRAGMENTS = (
    "/search",
    "/explore/tags/",
    "/hashtag/",
    "/results?",
    "google.com/search",
)


def is_safe_public_url(url: str) -> bool:
    """Validate that a URL is well-formed http/https and not a private/internal SSRF target."""
    if not url or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"http", "https"}:
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        parts = hostname.split(".")
        if len(parts) < 2 or len(parts[-1]) < 2:
            return False
        return all(DOMAIN_LABEL_RE.match(label) for label in parts)


def is_profile_not_generic_search(url: str) -> bool:
    """Ensure URL points to an individual/business profile rather than a generic search page."""
    lower = url.lower()
    return not any(frag in lower for frag in GENERIC_SEARCH_PATH_FRAGMENTS)


def is_valid_email(email: str) -> bool:
    """Validate publicly published email format and exclude obvious placeholder domains."""
    cleaned = email.strip().removeprefix("mailto:")
    if not EMAIL_RE.fullmatch(cleaned):
        return False
    domain = cleaned.split("@", 1)[1].lower()
    return domain not in {"example.com", "example.org", "test.com", "domain.com"}


def extract_public_emails(text: str) -> list[str]:
    """Extract valid, non-placeholder public email addresses from text."""
    found: list[str] = []
    for match in EMAIL_RE.findall(text or ""):
        if is_valid_email(match) and match.lower() not in {e.lower() for e in found}:
            found.append(match)
    return found


def extract_whatsapp_links(text: str) -> list[str]:
    """Extract valid public WhatsApp contact links from text."""
    found: list[str] = []
    for match in WHATSAPP_URL_RE.findall(text or ""):
        cleaned = match.rstrip(".,;:!?)")
        if is_safe_public_url(cleaned) and cleaned not in found:
            found.append(cleaned)
    return found


def extract_valid_phones(text: str) -> list[str]:
    """Extract plausible phone numbers (8-15 digits) from text."""
    found: list[str] = []
    for raw in PHONE_RE.findall(text or ""):
        digits = re.sub(r"\D", "", raw)
        if 8 <= len(digits) <= 15:
            normalized = f"+{digits}" if raw.strip().startswith("+") else digits
            if normalized not in found:
                found.append(normalized)
    return found
