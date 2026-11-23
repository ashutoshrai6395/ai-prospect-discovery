"""Recognise supported public profile URL formats and published contact links."""
import re
from urllib.parse import parse_qs, urlsplit

from app.utils.validators import extract_public_emails, extract_valid_phones, extract_whatsapp_links, is_safe_public_url

HOSTS = {
    "linkedin.com": "LinkedIn", "x.com": "X", "twitter.com": "X",
    "youtube.com": "YouTube", "facebook.com": "Facebook", "instagram.com": "Instagram",
    "threads.net": "Threads", "threads.com": "Threads", "wa.me": "WhatsApp",
    "api.whatsapp.com": "WhatsApp",
}
RESERVED = set("about accounts ads business channels community developers directory events explore friends gaming groups hashtag help home i intent legal login logout marketplace messages notifications pages people policy privacy reels search settings share sharer stories support terms watch web".split())
PATTERNS = {
    "Instagram": r"[A-Za-z0-9._]{1,30}", "X": r"[A-Za-z0-9_]{1,15}",
    "Threads": r"@[A-Za-z0-9._]{1,30}", "Facebook": r"[A-Za-z0-9.\-]+",
    "LinkedIn": r"(?:in|company)/[\w%\-]+",
    "YouTube": r"(?:@[\w.%\-]+|channel/UC[\w\-]{22}|(?:c|user)/[\w.%\-]+)",
}

def profile_platform(url: str) -> str | None:
    if not is_safe_public_url(url):
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.username is not None or parts.netloc.lower() != (parts.hostname or "").lower():
        return None
    platform = HOSTS.get(host)
    path = parts.path.strip("/")
    if platform == "WhatsApp":
        number = path if host == "wa.me" else parse_qs(parts.query).get("phone", [""])[0]
        if host == "api.whatsapp.com" and path != "send":
            return None
        return platform if re.fullmatch(r"[1-9][0-9]{7,14}", number) else None
    if platform == "Facebook" and path == "profile.php":
        ids = parse_qs(parts.query).get("id", [])
        return platform if len(ids) == 1 and ids[0].isascii() and ids[0].isdigit() else None
    if path.lower() in RESERVED or path.lower() in {"p", "tv", "reel", "direct", "press", "developers", "accounts.php", "profile.php"} or path.lower().endswith(".php"):
        return None
    if platform in PATTERNS and re.fullmatch(PATTERNS[platform], path):
        return platform
    return None

def contact_links(snippet: str) -> list[tuple[str, str]]:
    links = [("Email", "mailto:" + email) for email in extract_public_emails(snippet)]
    for match in re.finditer(r"\b(?:phone|tel(?:ephone)?|mobile|call)\s*[:.]?\s*(\+?\d[\d ()\-]{6,20}\d)", snippet, re.I):
        links.extend(("Phone", "tel:" + number) for number in extract_valid_phones(match[1]))
    links.extend(("WhatsApp", url) for url in extract_whatsapp_links(snippet) if profile_platform(url) == "WhatsApp")
    return links
