# pipeline/daily.py
"""
v0.3 — Scheduled paper discovery.

Queries arXiv for recent papers in robotics/AI categories, filters out any
already processed, runs the quality gate on candidates, and returns the first
paper ID that passes — ready to be fed into the main pipeline.

Usage (standalone):
  python pipeline/daily.py               # print best paper ID
  python pipeline/daily.py --list 10     # show top-10 candidates without picking
"""
import argparse
import datetime
import json
import pathlib
import time
import sys

import arxiv
from config import cfg

# Where processed paper IDs are recorded
_PROCESSED_LOG = pathlib.Path("cache/processed.json")


def _categories() -> list[str]:
    return cfg.discovery.categories


def _fetch_per_category() -> int:
    return cfg.discovery.fetch_per_category


def _load_processed() -> set[str]:
    if _PROCESSED_LOG.exists():
        return set(json.loads(_PROCESSED_LOG.read_text()))
    return set()


def mark_processed(arxiv_id: str) -> None:
    """Record that a paper has been published so it's skipped in future runs."""
    processed = _load_processed()
    processed.add(arxiv_id)
    _PROCESSED_LOG.parent.mkdir(exist_ok=True)
    _PROCESSED_LOG.write_text(json.dumps(sorted(processed), indent=2))


def _fetch_recent(max_results: int | None = None) -> list[arxiv.Result]:
    """Fetch recent papers from all monitored categories, deduplicated."""
    if max_results is None:
        max_results = _fetch_per_category()
    client = arxiv.Client()
    seen_ids: set[str] = set()
    results: list[arxiv.Result] = []

    for cat in _categories():
        query = f"cat:{cat}"
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        for paper in client.results(search):
            pid = paper.get_short_id().split("v")[0]  # strip version suffix
            if pid not in seen_ids:
                seen_ids.add(pid)
                results.append(paper)

    # Sort by submission date descending
    results.sort(key=lambda p: p.published, reverse=True)
    return results


def pick_daily_paper(verbose: bool = False) -> str | None:
    """
    Return the arXiv ID of the best unprocessed paper that passes the quality
    gate, or None if no suitable paper is found today.
    """
    # Import here to avoid circular imports when daily.py is used standalone
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from quality import check_quality

    processed = _load_processed()
    candidates = _fetch_recent()

    if verbose:
        print(f"  Fetched {len(candidates)} candidate papers across {_categories()}")

    for paper in candidates:
        arxiv_id = paper.get_short_id().split("v")[0]

        if arxiv_id in processed:
            if verbose:
                print(f"  ⏭️  {arxiv_id} — already processed, skipping")
            continue

        if verbose:
            print(f"  🔍 Checking {arxiv_id}: {paper.title[:70]}...")

        result = check_quality(arxiv_id, allow_skip=False)
        if result["pass"]:
            print(f"  ✅ Selected: [{arxiv_id}] {paper.title[:70]}")
            print(f"     Reason: {result['reason']}")
            return arxiv_id
        else:
            if verbose:
                print(f"     ❌ {result['reason']}")
        # Brief pause between candidates to avoid hammering S2
        time.sleep(2)

    print("  ⚠️  No suitable paper found in today's arXiv feed.")
    return None


def list_candidates(n: int = 10) -> None:
    """Print the top-N recent papers without running the quality gate."""
    processed = _load_processed()
    candidates = _fetch_recent(max_results=n * 2)
    shown = 0
    for paper in candidates:
        if shown >= n:
            break
        arxiv_id = paper.get_short_id().split("v")[0]
        status = "✓ processed" if arxiv_id in processed else "new"
        pub_date = paper.published.strftime("%Y-%m-%d")
        cats = ", ".join(paper.categories[:3])
        print(f"  [{pub_date}] {arxiv_id}  ({status})  [{cats}]")
        print(f"    {paper.title[:90]}")
        shown += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JarvisForResearchers daily paper picker")
    parser.add_argument(
        "--list",
        metavar="N",
        type=int,
        default=0,
        help="List N recent candidates without picking",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show quality gate decisions"
    )
    args = parser.parse_args()

    if args.list:
        list_candidates(args.list)
    else:
        result = pick_daily_paper(verbose=args.verbose)
        if result:
            print(result)
        else:
            sys.exit(1)
