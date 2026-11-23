"""Platform discovery modules."""

from app.platforms.facebook import FacebookDiscoverer
from app.platforms.google import GoogleDiscoverer
from app.platforms.instagram import InstagramDiscoverer
from app.platforms.linkedin import LinkedInDiscoverer
from app.platforms.threads import ThreadsDiscoverer
from app.platforms.whatsapp import WhatsAppDiscoverer
from app.platforms.x_platform import XPlatformDiscoverer
from app.platforms.youtube import YouTubeDiscoverer

__all__ = [
    "GoogleDiscoverer",
    "LinkedInDiscoverer",
    "XPlatformDiscoverer",
    "YouTubeDiscoverer",
    "InstagramDiscoverer",
    "WhatsAppDiscoverer",
    "FacebookDiscoverer",
    "ThreadsDiscoverer",
]
