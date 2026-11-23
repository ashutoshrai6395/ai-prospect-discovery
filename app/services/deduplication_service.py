"""Keep distinct platform accounts separate unless evidence supports a merge."""
from app.platforms.base import RawCandidate
from app.utils.normalizers import extract_handle_from_url, normalize_name_key, normalize_url

def compatible(a: RawCandidate, b: RawCandidate) -> bool:
    if normalize_url(a.profile_url) == normalize_url(b.profile_url):
        return True
    if a.platform == b.platform or not normalize_name_key(a.name) or normalize_name_key(a.name) != normalize_name_key(b.name):
        return False
    handle = extract_handle_from_url(a.profile_url)
    if handle and handle == extract_handle_from_url(b.profile_url) and handle != "profile.php":
        return True
    def contacts(item):
        return {normalize_url(url) for _, url in item.extra_links} | {normalize_url(item.profile_url)}
    return bool(contacts(a) & contacts(b))

class DeduplicationService:
    def group_candidates(self, candidates: list[RawCandidate]) -> list[list[RawCandidate]]:
        groups: list[list[RawCandidate]] = []
        for candidate in candidates:
            for group in groups:
                if all(compatible(candidate, member) for member in group):
                    group.append(candidate)
                    break
            else:
                groups.append([candidate])
        return groups
