"""Multi-provider LLM service (OpenAI, Google Gemini, Anthropic) using httpx."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings

JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMService:
    """Async LLM client supporting OpenAI, Gemini, and Anthropic REST APIs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def is_configured(self) -> bool:
        provider = self._settings.llm_provider
        if provider == "openai":
            return bool(self._settings.openai_api_key)
        if provider == "gemini":
            return bool(self._settings.gemini_api_key)
        if provider == "anthropic":
            return bool(self._settings.anthropic_api_key)
        return False

    async def complete_json(
        self,
        system_prompt: str,
        user_payload: str,
        client: httpx.AsyncClient,
    ) -> dict[str, Any] | None:
        """Send a structured JSON completion request; return parsed dict or None."""
        if not self.is_configured:
            return None

        provider = self._settings.llm_provider
        try:
            if provider == "openai":
                raw = await self._call_openai(system_prompt, user_payload, client)
            elif provider == "gemini":
                raw = await self._call_gemini(system_prompt, user_payload, client)
            elif provider == "anthropic":
                raw = await self._call_anthropic(system_prompt, user_payload, client)
            else:
                return None
            return _parse_json_object(raw)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            return None

    async def _call_openai(
        self, system_prompt: str, user_payload: str, client: httpx.AsyncClient
    ) -> str:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._settings.llm_model or "gpt-4o-mini",
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])

    async def _call_gemini(
        self, system_prompt: str, user_payload: str, client: httpx.AsyncClient
    ) -> str:
        model = self._settings.llm_model or "gemini-3.1-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        resp = await client.post(
            url,
            headers={
                "x-goog-api-key": self._settings.gemini_api_key,
                "Content-Type": "application/json",
            },
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_payload}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["candidates"][0]["content"]["parts"][0]["text"])

    async def _call_anthropic(
        self, system_prompt: str, user_payload: str, client: httpx.AsyncClient
    ) -> str:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self._settings.llm_model or "claude-haiku-5-5",
                "max_tokens": 512,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_payload}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data["content"][0]["text"])


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        match = JSON_BLOCK_RE.search(text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
