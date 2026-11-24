# AI-Powered Multi-Platform Prospect Discovery API

A FastAPI service that converts a natural-language request into audience, topic and location fields, searches public indexes, and returns matching profile and public contact links. The LLM sees the query only. The application makes outbound calls to configured providers and never visits profile URLs supplied by a search result.

[Open the live API documentation](https://ai-prospect-discovery-il7p.onrender.com/docs) · [Review the five live queries and accuracy checks](evidence/live-assessment.md)

## Run locally on Windows

Use Python 3.10+ (tested on 3.12). From the extracted project folder, run these PowerShell commands.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --port 4000
```

For macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python` and `cp .env.example .env`. Configure the following in the local .env or hosting secret settings and restart the server. Keep any real .env out of Git.

| Requirement | Configuration |
|---|---|
| One LLM provider | Set LLM_PROVIDER to openai, gemini or anthropic and set the corresponding OPENAI_API_KEY, GEMINI_API_KEY or ANTHROPIC_API_KEY. Leave LLM_MODEL blank for the provider default. |
| One authorized search provider | Set SERPAPI_API_KEY or, for a provisioned Google Custom Search engine, both GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX. Configure the engine to cover the target domains. When both providers are configured, a failed Google search falls back to SerpAPI. |
| Optional native YouTube search | Set YOUTUBE_API_KEY for the YouTube Data API. Indexed channel search is the default and the fallback on native API failure. |

Interactive API docs are at `http://localhost:4000/docs`. `GET /health` reports that the process is up. Provider credentials are checked when discovery runs.

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:4000/prospect-discovery -ContentType application/json -Body '{"query":"Football lovers in Washington DC in USA"}'
```

## Discovery and accuracy

The unrestricted Google or SerpAPI search discovers recognizable social profile URLs. Additional searches use platform domains for LinkedIn, X, Instagram, Facebook, Threads, WhatsApp and YouTube. Google is a discovery source. Generic websites, articles, posts and videos are outside this prototype's accepted profile formats. Indexed coverage depends on the search engine and public snippets. A matching social URL establishes a candidate, not verified account ownership.

The filter looks for topic terms, supported audience roles and the most specific requested place in the source title or snippet. Only location components present in that text are returned. A city mention can indicate an event or service area, so the result does not establish residence. Missing evidence, spelling variants and sparse snippets can exclude real matches. Individual/business intent is included in the parser output; ownership and professional status cannot be independently verified from a snippet.

Public email addresses, explicitly labelled phone numbers and direct WhatsApp contacts are extracted from the returned profile snippet or channel description. These are syntactically checked public references. Email deliverability, phone ownership and reachability are untested. Group invites and inferred contact details are excluded.

Duplicate URLs retain distinct Facebook IDs and WhatsApp numbers. Across platforms the service requires matching normalized names plus a shared handle or contact link. Every member of a merged group must agree. This favors separate records for ambiguous identities. Shared names, handles or organizational inboxes can still be ambiguous.

Missing configuration returns HTTP 503. For a transient LLM timeout or 502/503/504, simple topic-and-place queries can use a local rule parser. The X-Intent-Source header reports llm or rules-provider-unavailable. This fallback still searches live sources and does not cache the fallback interpretation. Unsupported queries, invalid model responses and failed search providers return 502. An incomplete discovery run fails as a whole. A completed run with zero matches returns 200 with an empty array. Invalid input returns 422, and the process-wide request budget returns 429. Each worker has a separate budget and bounded caches. Use one worker for the demo and set provider-side quotas. Search requests share a concurrency limit. Cached query interpretation and successful indexed searches are reused until expiry; simultaneous cache misses and native YouTube calls may still consume quota.

## LLM choice

Standard text pricing below is in USD per million input/output tokens for short prompts. The last column estimates one parser call with 250 input and 120 billable output tokens. Actual output length, reasoning tokens, search fees, retries and hosting affect total cost.

| Model | Input / output | Parser cost | Suitability |
|---|---:|---:|---|
| OpenAI gpt-4o-mini | $0.15 / $0.60 | $0.000110 | Recommended default. Native JSON mode and low cost suit short extraction prompts. |
| Google gemini-3.1-flash-lite | $0.25 / $1.50 | $0.000243 | Manual alternative with JSON response mode and a low-latency design. |
| Anthropic claude-haiku-5-5 | $0.10 / $0.50 | $0.000085 | Economical alternative for short classification requests. This adapter validates prompted JSON locally. |

Sources: [OpenAI model specifications](https://developers.openai.com/api/docs/models/gpt-4o-mini), [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Claude models and pricing](https://platform.claude.com/docs/en/models/overview).

Allow roughly 1–5 seconds for a short parser response as a planning estimate. No live model accuracy or latency ranking has been measured. All three clients use the same typed parser output. For a provider comparison, score each extracted audience, city, country and target type against human labels on the five test queries, then compare observed latency and billed tokens. The final profile filtering runs locally. Search calls will often dominate the request count.

## Tests, examples and public demo

Run `python -m unittest discover -s tests -v`. Only offline fixtures are used by the test suite. See [the executed test log](evidence/offline-tests.txt) and [sample requests and responses](evidence/offline-examples.json). The sample profiles are deliberately fictional test inputs.

Deploy from the project root to a Python web host. Install with `python -m pip install -r requirements.txt`. For a Linux host, start with `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-4000} --workers 1`. A Procfile is included. Set secrets on the host before running discovery and keep provider keys out of URLs shared with reviewers.

To collect genuine responses from the deployed application, replace the demo hostname below and run the command once. It sends all five required queries and can consume provider quota.

```text
python scripts/check_live.py --base-url https://YOUR-DEMO-HOST --output evidence/live-results.json
```

The runner saves HTTP status, elapsed time and JSON for each query. Review returned links and location evidence, and check the report for public contact details before publishing. The repository includes offline fixtures and an observed live-run summary in evidence/live-assessment.md. The assessment submission also requires the public repository URL and the reachable demo URL.
