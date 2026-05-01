# pipeline/digest.py
"""
v0.5 — Weekly digest: "This Week in Robotics".

Reads recently-processed papers from cache/, builds compact per-paper summaries
from their extraction JSONs, then calls Gemma 4 once to write:
  - A one-paragraph Overview synthesising the week's themes
  - Per-paper 2-3 sentence blurbs with exact method names and numbers
  - Trends & Observations bullet points

Usage (via run.py):
  python pipeline/run.py --digest
  python pipeline/run.py --digest --quantise
"""
import datetime
import json
import pathlib

from llm import ask
from config import cfg

_PROCESSED_LOG = pathlib.Path("cache/processed.json")


def _load_recent_papers() -> list[dict]:
    """
    Return list of dicts with 'meta' and 'extraction' keys for papers whose
    extraction JSON was written within the last cfg.digest.lookback_days days.
    """
    if not _PROCESSED_LOG.exists():
        return []

    all_ids: list[str] = json.loads(_PROCESSED_LOG.read_text())
    cutoff = datetime.datetime.now() - datetime.timedelta(days=cfg.digest.lookback_days)

    papers = []
    for pid in all_ids:
        meta_path = pathlib.Path(f"cache/{pid}.json")
        extraction_path = pathlib.Path(f"cache/{pid}_extraction.json")

        if not meta_path.exists() or not extraction_path.exists():
            continue

        # Use extraction mtime as the proxy for "when this paper was processed"
        mtime = datetime.datetime.fromtimestamp(extraction_path.stat().st_mtime)
        if mtime < cutoff:
            continue

        meta = json.loads(meta_path.read_text())
        extraction = json.loads(extraction_path.read_text())
        papers.append({"meta": meta, "extraction": extraction, "processed_at": mtime})

    # Oldest first so the digest reads chronologically
    papers.sort(key=lambda p: p["processed_at"])
    return papers


def _paper_summary(index: int, p: dict) -> dict:
    """Build the compact per-paper dict that goes into the LLM prompt."""
    meta = p["meta"]
    ext = p["extraction"]
    return {
        "index": index,
        "title": meta["title"],
        "arxiv_id": meta["id"],
        "url": meta.get("arxiv_url", f"https://arxiv.org/abs/{meta['id']}"),
        "authors": meta.get("authors", [])[:3],
        "year": meta.get("year", ""),
        "one_sentence_summary": ext.get("one_sentence_summary", ""),
        "key_contributions": ext.get("key_contributions", [])[:3],
        "key_results": ext.get("key_results", [])[:2],
        "practitioner_takeaways": ext.get("practitioner_takeaways", [])[:2],
    }


def build_weekly_digest(tokenizer, model) -> str | None:
    """
    Build the 'This Week in Robotics' post from recently processed papers.
    Returns the full post as a Markdown string, or None if too few papers.
    """
    papers = _load_recent_papers()

    if len(papers) < cfg.digest.min_papers:
        print(
            f"  Only {len(papers)} paper(s) in the last {cfg.digest.lookback_days} days "
            f"(minimum: {cfg.digest.min_papers}). Skipping digest."
        )
        return None

    print(f"  Building digest from {len(papers)} paper(s)...")

    summaries = [_paper_summary(i, p) for i, p in enumerate(papers, 1)]

    today = datetime.date.today()
    week_num = int(today.strftime("%W"))
    title_prefix = cfg.digest.title_prefix

    prompt = f"""\
You are writing for {cfg.author.blog_name}, a technical blog for {cfg.author.audience}.
Tone: precise, engaging, collegial — like a senior engineer briefing sharp peers.
Never use hype words (revolutionary, groundbreaking, game-changing).
Every claim must come from the paper summaries below.

Write a weekly digest covering {len(papers)} paper(s).
Do NOT write front-matter or a title heading — start directly with ## Overview.

Follow this exact structure:

## Overview
One paragraph (5–8 sentences) synthesising this week's main themes, surprises,
and cross-cutting ideas. Reference paper titles by name where relevant.

## Papers This Week
For EACH paper, output EXACTLY this block (no extras):

### [<title>](<url>)
*<one_sentence_summary — copy verbatim from input>*

<2–3 sentences on the key contribution and standout result.
Be specific: use exact method names and numbers from key_results.
No vague adjectives.>

**Why it matters:** <one sentence practitioner takeaway>

## Trends & Observations
3–5 bullet points identifying patterns across this week's papers
(e.g. shared architectures, benchmark trends, open problems addressed).

---

PAPERS:
{json.dumps(summaries, indent=2)}"""

    print("  🤖 Calling Gemma 4 for digest synthesis...")
    prose = ask(
        prompt,
        tokenizer,
        model,
        temperature=cfg.llm.temperature,
        max_new_tokens=cfg.llm.max_new_tokens,
    )

    # Build MkDocs front-matter
    title = f"{title_prefix} — {today.year}, Week {week_num}"
    short_titles = ", ".join(p["meta"]["title"][:45] for p in papers[:3])
    if len(papers) > 3:
        short_titles += f" and {len(papers) - 3} more"

    front_matter = (
        f'---\n'
        f'title: "{title}"\n'
        f'date: {today.isoformat()}\n'
        f'authors:\n'
        f'  - JarvisForResearchers Bot\n'

        f'categories:\n'
        f'  - Weekly Digest\n'
        f'description: >\n'
        f'  {len(papers)} papers this week: {short_titles}.\n'
        f'---\n'
    )

    return front_matter + f"\n> *Generated by JarvisForResearchers Bot on {today.isoformat()}*\n\n" + prose
