"""Conservative filtering using text returned by the discovery source."""
import re

from app.platforms.base import RawCandidate
from app.schemas import QueryUnderstanding

STOP = set("a an and at for from in near of on or the to".split())
ROLES = {"owner", "founder", "director", "creator", "coach", "manager", "developer"}
PEERS = {"owner": {"owner", "proprietor", "cofounder", "founder"}, "founder": {"founder", "cofounder"}}

def words(text: str) -> list[str]:
    tokens = re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)
    return [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in tokens]

def location_evidence(value: str, source: str) -> bool:
    terms = re.findall(r"[^\W_]+", value)
    return bool(terms and re.search(r"\b" + r"\W+".join(map(re.escape, terms)) + r"\b", source, re.I))

class RelevanceService:
    def filter_relevant(self, candidates: list[RawCandidate], understanding: QueryUnderstanding) -> list[RawCandidate]:
        roles = set(words(understanding.audience)) & ROLES
        topics = set(words(understanding.interest)) - STOP - ROLES
        if not topics and not roles:
            return []
        places = [p for p in (understanding.location.city, understanding.location.state, understanding.location.country) if p]
        result = []
        for candidate in candidates:
            source = candidate.name + " " + candidate.snippet
            tokens = set(words(source))
            if topics and not topics.issubset(tokens):
                continue
            if any(not tokens.intersection(PEERS.get(role, {role})) for role in roles):
                continue
            if places and not location_evidence(places[0], source):
                continue
            candidate.location = ", ".join(p for p in places if location_evidence(p, source)) or None
            result.append(candidate)
        return result
