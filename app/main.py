"""FastAPI entry point for the AI-Powered Multi-Platform Prospect Discovery API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from app.services.query_service import intent_source
from app.services.errors import MissingConfiguration, ProviderFailure, RequestLimit

from app.schemas import ProspectDiscoveryRequest, ProspectDiscoveryResponse
from app.services.prospect_service import ProspectService

@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.prospect_service = ProspectService()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AI-Powered Multi-Platform Prospect Discovery API",
    description=(
        "FastAPI service that interprets natural-language prospect queries with an LLM, "
        "discovers public profiles across supported platforms, filters by relevance, "
        "deduplicates identities, and returns structured JSON."
    ),
    version="1.0.0",
)


def get_prospect_service(request: Request) -> ProspectService:
    """Dependency provider for ProspectService."""
    return request.app.state.prospect_service


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/prospect-discovery", response_model=ProspectDiscoveryResponse, tags=["Discovery"])
async def discover_prospects(
    payload: ProspectDiscoveryRequest,
    response: Response,
    service: ProspectService = Depends(get_prospect_service),
) -> ProspectDiscoveryResponse:
    """Discover, consolidate, and return public prospect candidates for a natural-language query."""
    token = intent_source.set("llm")
    try:
        result = await service.discover_prospects(payload.query)
        response.headers["X-Intent-Source"] = intent_source.get()
        return result
    except MissingConfiguration:
        raise HTTPException(503, "Configure an LLM provider and an authorized search provider.") from None
    except ProviderFailure:
        raise HTTPException(502, "A configured provider failed. Check credentials, quota and provider availability.") from None
    except RequestLimit:
        raise HTTPException(429, "Discovery request limit reached.", headers={"Retry-After": "60"}) from None
    finally:
        intent_source.reset(token)
