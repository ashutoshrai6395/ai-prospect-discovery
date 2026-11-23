"""Run the five required requests against a running API and save the actual responses."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import httpx

QUERIES = (
    "Football lovers in Washington DC in USA",
    "Digital marketing agency owners in New York USA",
    "Startup founders in London UK",
    "Cricket lovers in Ahmedabad India",
    "Restaurant owners in Dubai UAE",
)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    with httpx.Client(timeout=150) as client:
        for query in QUERIES:
            start = monotonic()
            entry = {"request": {"query": query}}
            try:
                response = client.post(args.base_url.rstrip("/") + "/prospect-discovery", json=entry["request"])
                entry["status"] = response.status_code
                entry["response"] = response.json()
            except (httpx.HTTPError, ValueError) as error:
                entry["error"] = type(error).__name__
            entry["seconds"] = round(monotonic() - start, 3)
            results.append(entry)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "runs": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return int(any(row.get("status") != 200 or row.get("response", {}).get("success") is not True for row in results))

if __name__ == "__main__":
    raise SystemExit(main())
