"""Unit and integration tests for AI-Powered Multi-Platform Prospect Discovery API."""

from __future__ import annotations

import json
import unittest

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_prospect_service
from app.services.prospect_service import ProspectService
from app.utils.validators import is_profile_not_generic_search, is_safe_public_url, is_valid_email


def _configured_settings() -> Settings:
    return Settings(
        request_timeout_seconds=5.0,
        max_concurrent_requests=6,
        max_results_per_platform=5,
        cache_ttl_seconds=300,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        openai_api_key="test-openai-key",
        google_cse_api_key="test-cse-key",
        google_cse_cx="test-cse-cx",
    )


class TestProspectDiscoveryAPI(unittest.TestCase):
    """Tests for security validators, LLM query understanding, discovery, consolidation, and API."""

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health_endpoint(self) -> None:
        client = TestClient(app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_input_validation_rejects_invalid_queries(self) -> None:
        client = TestClient(app)
        with client:
            for bad in ["", "  ", "ab", "x" * 301]:
                resp = client.post("/prospect-discovery", json={"query": bad})
                self.assertEqual(resp.status_code, 422)

    def test_security_validators_block_ssrf_and_generic_search(self) -> None:
        self.assertFalse(is_safe_public_url("http://127.0.0.1:8080/admin"))
        self.assertFalse(is_safe_public_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_public_url("http://localhost:4000/"))
        self.assertFalse(is_safe_public_url("file:///etc/passwd"))
        self.assertTrue(is_safe_public_url("https://www.linkedin.com/in/johnsmith-dc"))

        self.assertFalse(is_profile_not_generic_search("https://www.google.com/search?q=football"))
        self.assertFalse(is_profile_not_generic_search("https://x.com/search?q=football"))
        self.assertTrue(is_profile_not_generic_search("https://x.com/johnsmithdc"))

        self.assertFalse(is_valid_email("fake@example.com"))
        self.assertTrue(is_valid_email("john.smith@dcfootballclub.org"))

    def test_end_to_end_discovery_consolidation_and_filtering(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "api.openai.com/v1/chat/completions" in url:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "interest": "Football",
                                            "audience": "Football lovers",
                                            "location": {
                                                "city": "Washington DC",
                                                "state": "District of Columbia",
                                                "country": "USA",
                                            },
                                            "target_type": "Individual",
                                            "search_keywords": ["football", "Washington DC"],
                                        }
                                    )
                                }
                            }
                        ]
                    },
                )

            if "googleapis.com/customsearch/v1" in url:
                q = request.url.params.get("q", "")
                if "site:linkedin.com" in q:
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "title": "John Smith | LinkedIn",
                                    "link": "https://www.linkedin.com/in/johnsmithdc",
                                    "snippet": "Football organizer in Washington DC, USA. https://wa.me/12025550199 Contact: john.smith@dcfootballclub.org",
                                },
                                {
                                    "title": "Unrelated Chef | LinkedIn",
                                    "link": "https://www.linkedin.com/in/unrelatedchef",
                                    "snippet": "Pastry chef in Paris, France.",
                                },
                            ]
                        },
                    )
                if "site:x.com" in q:
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "title": "John Smith on X",
                                    "link": "https://x.com/johnsmithdc",
                                    "snippet": "Weekend football lovers meetup in Washington DC USA! https://wa.me/12025550199",
                                }
                            ]
                        },
                    )
                if "site:youtube.com" in q:
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "title": "Michael Johnson - YouTube",
                                    "link": "https://www.youtube.com/@mjohnsonfootball",
                                    "snippet": "Football highlights & Washington DC USA fan community.",
                                }
                            ]
                        },
                    )
                if "site:wa.me" in q:
                    return httpx.Response(
                        200,
                        json={
                            "items": [
                                {
                                    "title": "John Smith",
                                    "link": "https://wa.me/12025550199",
                                    "snippet": "Washington DC football lovers group chat",
                                }
                            ]
                        },
                    )
                return httpx.Response(200, json={"items": []})

            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        app.dependency_overrides[get_prospect_service] = lambda: ProspectService(
            settings=_configured_settings(),
            transport=transport,
        )
        client = TestClient(app)
        resp = client.post(
            "/prospect-discovery",
            json={"query": "Football lovers in Washington DC in USA"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["query"], "Football lovers in Washington DC in USA")
        self.assertEqual(body["total_prospects"], 2)

        by_name = {p["name"]: p for p in body["prospects"]}
        self.assertIn("John Smith", by_name)
        self.assertIn("Michael Johnson", by_name)
        self.assertNotIn("Unrelated Chef", by_name)

        john_platforms = {s["platform"]: s["link"] for s in by_name["John Smith"]["social_link"]}
        self.assertEqual(john_platforms["LinkedIn"], "https://www.linkedin.com/in/johnsmithdc")
        self.assertEqual(john_platforms["X"], "https://x.com/johnsmithdc")
        self.assertEqual(john_platforms["Email"], "mailto:john.smith@dcfootballclub.org")
        self.assertEqual(john_platforms["WhatsApp"], "https://wa.me/12025550199")

    def test_practical_test_cases_report_missing_keys(self) -> None:
        empty_settings = Settings(
            openai_api_key="",
            gemini_api_key="",
            anthropic_api_key="",
            google_cse_api_key="",
            google_cse_cx="",
            serpapi_api_key="",
        )
        app.dependency_overrides[get_prospect_service] = lambda: ProspectService(
            settings=empty_settings
        )
        client = TestClient(app)
        queries = [
            "Football lovers in Washington DC in USA",
            "Digital marketing agency owners in New York USA",
            "Startup founders in London UK",
            "Cricket lovers in Ahmedabad India",
            "Restaurant owners in Dubai UAE",
        ]
        for q in queries:
            resp = client.post("/prospect-discovery", json={"query": q})
            self.assertEqual(resp.status_code, 503)
            self.assertIn("detail", resp.json())


if __name__ == "__main__":
    unittest.main()
