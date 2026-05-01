# pipeline/quality.py
import datetime
import json
import pathlib
import time
import requests
from config import cfg

# Direct S2 REST endpoint — much faster than the Python client wrapper
_S2_URL = "https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}"
_S2_FIELDS = "venue,year,citationCount"
_S2_TIMEOUT = 10  # seconds
_S2_RETRIES = 8   # attempts before giving up (enough for several 429 waves)
_S2_BACKOFF = 3.0 # initial wait in seconds (doubles each retry, capped at 60s)
_S2_BACKOFF_CAP = 60.0

# Cache results so repeated runs don't hit the network again
_CACHE_DIR = pathlib.Path("cache/quality")


# Loaded from config.yaml — edit top_venues there, not here
TOP_VENUES = cfg.quality.top_venues


def check_quality(arxiv_id: str, allow_skip: bool = True) -> dict:
    """
    Returns:
      { "pass": True,  "reason": "Top venue: NeurIPS 2024" }
      { "pass": False, "reason": "Only 3 citations (threshold: 20)" }

    allow_skip=True  (default) — if S2 is unreachable, pass the paper through
                                  with a warning. Safe for manual --arxiv runs
                                  where the user has already chosen the paper.
    allow_skip=False            — if S2 is unreachable, reject the paper.
                                  Use this in --daily mode to avoid publishing
                                  unvetted papers from the arXiv feed.
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{arxiv_id}.json"

    # Return cached result immediately if available
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    data, status = _fetch_s2(arxiv_id)

    if status == "not_found":
        # S2 has no record yet — paper is too new to be indexed.
        # Treat identically to a brand-new preprint: accept with grace period.
        print("  ℹ️   Not yet indexed in S2 — treating as brand-new preprint")
        result = {"pass": True, "reason": "Not yet indexed in S2 — assumed brand-new preprint"}
        cache_file.write_text(json.dumps(result))
        return result

    if data is None:
        if allow_skip:
            print("  ⚠️  Semantic Scholar unavailable — passing through (manual run)")
            return {"pass": True, "reason": "Quality gate skipped (S2 unreachable, manual override)"}
        else:
            print("  ❌  Semantic Scholar unavailable — rejecting to protect blog quality")
            return {"pass": False, "reason": "Quality gate failed (S2 unreachable, daily mode is fail-closed)"}

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


def _fetch_s2(arxiv_id: str) -> tuple[dict | None, str]:
    """
    Returns (data, status) where status is one of:
      "ok"          — success
      "not_found"   — 404, paper not yet indexed in S2 (too new)
      "rate_limited"— exhausted retries due to 429
      "error"       — network or unexpected HTTP error
    """
    wait = _S2_BACKOFF
    for attempt in range(_S2_RETRIES):
        try:
            resp = requests.get(
                _S2_URL.format(arxiv_id=arxiv_id),
                params={"fields": _S2_FIELDS},
                timeout=_S2_TIMEOUT,
            )
            if resp.status_code == 429:
                capped = min(wait, _S2_BACKOFF_CAP)
                print(f"  ⏳ S2 rate-limited — waiting {capped:.0f}s (attempt {attempt + 1}/{_S2_RETRIES})...")
                time.sleep(capped)
                wait = min(wait * 2, _S2_BACKOFF_CAP)
                continue
            if resp.status_code == 404:
                return None, "not_found"
            resp.raise_for_status()
            return resp.json(), "ok"
        except requests.exceptions.RequestException as e:
            if attempt < _S2_RETRIES - 1:
                time.sleep(min(wait, _S2_BACKOFF_CAP))
                wait = min(wait * 2, _S2_BACKOFF_CAP)
            else:
                print(f"  ⚠️  S2 request failed: {e}")
    return None, "rate_limited"


def _citation_threshold(year: int) -> int:
    """Delegate to the config-driven threshold table."""
    return cfg.quality.citation_threshold(year)


def _normalise_venue(venue: str) -> str:
    """Strip year suffixes like 'NeurIPS 2023' → still matches 'NeurIPS'."""
    return venue.strip()
