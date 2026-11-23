"""Environment-backed configuration for LLM, Search, and Platform APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    request_timeout_seconds: float = 12.0
    max_concurrent_requests: int = 6
    max_results_per_platform: int = 5
    cache_ttl_seconds: int = 300

    # LLM Provider Configuration ("openai", "gemini", "anthropic")
    llm_provider: str = "openai"
    llm_model: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # Authorized Search APIs (Discovery Layer)
    google_cse_api_key: str = ""
    google_cse_cx: str = ""
    serpapi_api_key: str = ""

    # Optional Official Platform APIs
    youtube_api_key: str = ""
    requests_per_minute: int = 20

    def __post_init__(self) -> None:
        if min(self.request_timeout_seconds, self.max_concurrent_requests,
               self.max_results_per_platform, self.requests_per_minute) <= 0:
            raise ValueError("Request limits, result limits and timeouts must be positive")
        if self.cache_ttl_seconds < 0:
            raise ValueError("Cache TTL must be nonnegative")


def get_settings() -> Settings:
    """Return a fresh Settings instance reflecting current environment variables."""
    return Settings(
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12.0")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "6")),
        max_results_per_platform=int(os.getenv("MAX_RESULTS_PER_PLATFORM", "5")),
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        google_cse_api_key=os.getenv("GOOGLE_CSE_API_KEY", "").strip(),
        google_cse_cx=os.getenv("GOOGLE_CSE_CX", "").strip(),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
        requests_per_minute=int(os.getenv("REQUESTS_PER_MINUTE", "20")),
    )
