# pipeline/quality.py
import datetime
import json
import pathlib
import time
import requests

# Direct S2 REST endpoint — much faster than the Python client wrapper
_S2_URL = "https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}"
_S2_FIELDS = "venue,year,citationCount"
_S2_TIMEOUT = 10  # seconds
_S2_RETRIES = 4   # attempts before giving up
_S2_BACKOFF = 2.0 # initial wait in seconds (doubles each retry)

# Cache results so repeated runs don't hit the network again
_CACHE_DIR = pathlib.Path("cache/quality")


TOP_VENUES = {
    # Machine Learning
    "NeurIPS", "ICML", "ICLR", "AAAI", "JMLR",
    # Computer Vision
    "CVPR", "ICCV", "ECCV",
    # Robotics
    "ICRA", "IROS", "CoRL", "RSS", "IJRR", "T-RO",
    # NLP
    "ACL", "EMNLP", "NAACL",
}


def check_quality(arxiv_id: str) -> dict:
    """
    Returns:
      { "pass": True,  "reason": "Top venue: NeurIPS 2024" }
      { "pass": False, "reason": "Only 3 citations (threshold: 20)" }
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{arxiv_id}.json"

    # Return cached result immediately if available
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    data = _fetch_s2(arxiv_id)
    if data is None:
        # S2 unreachable — let the paper through with a warning so the
        # pipeline is never blocked by a transient network issue
        print("  ⚠️  Semantic Scholar unavailable — skipping quality check")
        return {"pass": True, "reason": "Quality gate skipped (S2 unreachable)"}

    venue = _normalise_venue(data.get("venue") or "")
    year = data.get("year") or datetime.date.today().year
    cites = data.get("citationCount") or 0

    # --- Check 1: Is it published at a top venue? ---
    for v in TOP_VENUES:
        if v.lower() in venue.lower():
            result = {"pass": True, "reason": f"Top venue: {venue} {year}"}
            cache_file.write_text(json.dumps(result))
            return result

    # --- Check 2: arXiv preprint — use citation count ---
    threshold = _citation_threshold(year)
    if threshold == 0:
        result = {"pass": True, "reason": f"Brand new preprint ({year}) — accepted"}
        cache_file.write_text(json.dumps(result))
        return result
    if cites >= threshold:
        result = {
            "pass": True,
            "reason": f"arXiv preprint with {cites} citations (≥ {threshold})",
        }
        cache_file.write_text(json.dumps(result))
        return result

    result = {
        "pass": False,
        "reason": (
            f"arXiv preprint with only {cites} citations "
            f"(threshold for {year}: {threshold})"
        ),
    }
    cache_file.write_text(json.dumps(result))
    return result


def _fetch_s2(arxiv_id: str) -> dict | None:
    """Fetch paper metadata from S2 with exponential backoff on 429."""
    wait = _S2_BACKOFF
    for attempt in range(_S2_RETRIES):
        try:
            resp = requests.get(
                _S2_URL.format(arxiv_id=arxiv_id),
                params={"fields": _S2_FIELDS},
                timeout=_S2_TIMEOUT,
            )
            if resp.status_code == 429:
                print(f"  ⏳ S2 rate-limited — waiting {wait:.0f}s (attempt {attempt + 1}/{_S2_RETRIES})...")
                time.sleep(wait)
                wait *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < _S2_RETRIES - 1:
                time.sleep(wait)
                wait *= 2
            else:
                print(f"  ⚠️  S2 request failed: {e}")
    return None


def _citation_threshold(year: int) -> int:
    """
    Newer papers haven't had time to accumulate citations.
    Use age-adjusted thresholds to avoid rejecting good recent work.
    """
    age = datetime.date.today().year - year
    if age == 0:
        return 0   # Brand new — skip citation check
    if age == 1:
        return 5   # ~1 year old: at least 5 citations
    if age == 2:
        return 20  # ~2 years old: at least 20 citations
    return 50      # Older: at least 50 citations


def _normalise_venue(venue: str) -> str:
    """Strip year suffixes like 'NeurIPS 2023' → still matches 'NeurIPS'."""
    return venue.strip()
