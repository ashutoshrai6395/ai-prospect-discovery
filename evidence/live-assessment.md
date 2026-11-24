# Live assessment run

The five requests below were sent to the [deployed API](https://ai-prospect-discovery-il7p.onrender.com/docs) at application commit `4e8606f7ffbbe27133151106161809c9b5ed1229`. Times are client-observed round trips. This is a summary of the observed responses.

| Query | HTTP | Candidates | Intent parser | Seconds |
|---|---:|---:|---|---:|
| Football lovers in Washington DC in USA | 200 | 3 | Local fallback | 20.12 |
| Digital marketing agency owners in New York USA | 200 | 1 | Gemini | 9.13 |
| Startup founders in London UK | 200 | 0 | Gemini | 34.61 |
| Cricket lovers in Ahmedabad India | 200 | 0 | Gemini | 21.76 |
| Restaurant owners in Dubai UAE | 200 | 1 | Local fallback | 20.89 |

All five used live search. For two requests, a transient model failure activated a local query parser. The response header `X-Intent-Source` identifies the parser.

## Relevance checks

- Washington DC returned a professional football club and two individual profiles. The club confirms its connection to the city and sport. Its profile does not establish an individual fan, and the interests of the two individuals were not independently verified. [Club description](https://www.dcpowerfootballclub.com/about/)
- The New York result was Sue Bookhout. Her business confirms that she owns a digital marketing agency. Her profile lists Cazenovia, New York. This supports a state-level match. The returned city label “New York, New York” is unsupported. [Business biography](https://bestdaydigital.com/about/) · [Public profile](https://www.linkedin.com/in/suebookhout)
- Dubai returned GoFood UAE. Its public description connects it to restaurant owners in Dubai. The candidate is a delivery platform and the response identifies no individual owner. [Company profile](https://www.linkedin.com/company/gofooduae)
- The London and Ahmedabad runs returned empty arrays. These counts describe the service's retrieval and filtering on this run. They do not establish the absence of relevant prospects.

To repeat the run from the repository root, run `python scripts/check_live.py --base-url https://ai-prospect-discovery-il7p.onrender.com --output evidence/live-results.json`. Each run consumes provider quota.
