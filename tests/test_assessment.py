"""Offline evaluator. Names, contacts, profile paths and provider replies are fixtures."""
from dataclasses import replace
import json
import unittest

import httpx
from fastapi.testclient import TestClient

from app.main import app, get_prospect_service
from app.services.prospect_service import ProspectService
from app.utils.profiles import profile_platform, contact_links
from app.utils.normalizers import normalize_url
from tests.test_prospect_discovery import _configured_settings

CASES = [
    ("Football lovers in Washington DC in USA", "Football", "Football lovers", "Washington DC", "USA", "Individual"),
    ("Digital marketing agency owners in New York USA", "Digital marketing agency", "Agency owners", "New York", "USA", "Business"),
    ("Startup founders in London UK", "Startup", "Startup founders", "London", "UK", "Individual"),
    ("Cricket lovers in Ahmedabad India", "Cricket", "Cricket lovers", "Ahmedabad", "India", "Individual"),
    ("Restaurant owners in Dubai UAE", "Restaurant", "Restaurant owners", "Dubai", "UAE", "Business"),
]

class ProviderFixture:
    def __init__(self):
        self.calls = 0
        self.search_status = 200
        self.llm_body = None
        self.empty = False

    def __call__(self, request):
        self.calls += 1
        if request.url.host == "api.openai.com":
            messages = json.loads(request.content)["messages"]
            query = json.loads(messages[-1]["content"])["search_query"]
            _, topic, role, city, country, target = next(row for row in CASES if row[0] == query)
            parsed = {"interest": topic, "audience": role, "location": {"city": city, "country": country},
                      "target_type": target, "search_keywords": [topic, role, city]}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(self.llm_body if self.llm_body is not None else parsed)}}]})
        if self.search_status != 200:
            return httpx.Response(self.search_status)
        query = request.url.params["q"]
        rows = []
        for _, topic, role, city, country, _ in CASES:
            if city not in query or self.empty or not query.startswith("site:linkedin.com"):
                continue
            for slug, place in [("match", city), ("wrongcity", "Paris")]:
                rows.append({"title": "Fixture " + slug, "link": "https://www.linkedin.com/in/fixture-" + slug,
                             "snippet": f"{topic}. {role} based in {place}. Phone: +1 202 555 0101."})
        return httpx.Response(200, json={"items": rows})

class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ProviderFixture()
        self.configure()
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)
        self.addCleanup(self.client.close)

    def configure(self, **changes):
        service = ProspectService(replace(_configured_settings(), **changes), transport=httpx.MockTransport(self.fixture))
        app.dependency_overrides[get_prospect_service] = lambda: service

    def post(self, query=CASES[0][0]):
        return self.client.post("/prospect-discovery", json={"query": query})

    def test_five_queries_keep_only_evidenced_city_and_include_phone(self):
        for query, _, _, city, _, _ in CASES:
            with self.subTest(query=query):
                response = self.post(query)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["total_prospects"], 1)
                record, = data["prospects"]
                self.assertEqual(record["location"], city)
                self.assertEqual(record["name"], "Fixture match")
                self.assertIn({"platform": "Phone", "link": "tel:+12025550101"}, record["social_link"])

    def test_empty_success(self):
        self.fixture.empty = True
        self.assertEqual(self.post().json()["total_prospects"], 0)

    def test_failure_then_retry(self):
        self.fixture.search_status = 403
        self.assertEqual(self.post().status_code, 502)
        self.fixture.search_status = 200
        self.assertEqual(self.post().json()["total_prospects"], 1)

    def test_invalid_llm_output(self):
        self.fixture.llm_body = {"interest": "Football", "location": "Washington DC"}
        self.assertEqual(self.post().status_code, 502)

    def test_cache_across_requests(self):
        self.assertEqual(self.post().status_code, 200)
        calls = self.fixture.calls
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.fixture.calls, calls)

    def test_request_budget(self):
        self.configure(requests_per_minute=1)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 429)

    def test_distinct_ids_and_handles(self):
        from app.platforms.base import RawCandidate
        from app.services.deduplication_service import DeduplicationService
        urls = [f"https://www.facebook.com/profile.php?id={i}" for i in (101, 202)]
        self.assertNotEqual(normalize_url(urls[0]), normalize_url(urls[1]))
        records = [RawCandidate("Same Name", "Facebook", u, location="London") for u in urls]
        records.append(RawCandidate("Same Name", "Instagram", "https://instagram.com/another", location="London"))
        self.assertEqual(len(DeduplicationService().group_candidates(records)), 3)

    def test_profile_shapes(self):
        for url in ("https://youtube.com/watch?v=abc", "https://x.com/home", "https://instagram.com/p/abc", "https://news.example.org/football", "https://wa.me/not-a-number"):
            self.assertIsNone(profile_platform(url))
        self.assertEqual(profile_platform("https://threads.com/@fixture"), "Threads")
        self.assertEqual(contact_links("Membership 1234567890"), [])

class PlatformEvidenceTests(unittest.TestCase):
    def test_supported_profile_shapes(self):
        samples = {
            "LinkedIn": "https://linkedin.com/company/democlub",
            "Instagram": "https://instagram.com/demo.club",
            "Facebook": "https://facebook.com/profile.php?id=123",
            "X": "https://x.com/demo_club",
            "YouTube": "https://youtube.com/@demo_club",
            "Threads": "https://threads.net/@demo_club",
            "WhatsApp": "https://api.whatsapp.com/send?phone=12025550101",
        }
        for platform, link in samples.items():
            with self.subTest(platform=platform):
                self.assertEqual(profile_platform(link), platform)

    def test_labelled_phones_and_direct_whatsapp(self):
        self.assertEqual(
            contact_links("Tel: +1 202 555 0101. Contact https://wa.me/12025550101"),
            [("Phone", "tel:+12025550101"), ("WhatsApp", "https://wa.me/12025550101")],
        )
        self.assertEqual(contact_links("Chat https://chat.whatsapp.com/example"), [])

    def test_unknown_location_stays_empty(self):
        from app.platforms.base import RawCandidate
        from app.schemas import QueryUnderstanding
        from app.services.relevance_service import RelevanceService
        candidate = RawCandidate("Fixture Club", "X", "https://x.com/fixture", "Football fans meet weekly")
        intent = QueryUnderstanding(interest="Football", audience="Football fans")
        result = RelevanceService().filter_relevant([candidate], intent)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].location)
