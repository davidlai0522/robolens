#!/usr/bin/env python3
"""
Usage:
  python pipeline/run.py --arxiv 2504.01234
  python pipeline/run.py --pdf   ./papers/smolvla.pdf
  python pipeline/run.py --arxiv 2504.01234 --force     # skip quality gate
  python pipeline/run.py --arxiv 2504.01234 --quantise  # 4-bit for low VRAM
  python pipeline/run.py --daily                        # auto-pick today's best paper
  python pipeline/run.py --daily --quantise             # daily + low VRAM
  python pipeline/run.py --remove 2504.01234            # delete a paper & its figures
"""
import argparse
import json
import shutil
import subprocess
import sys
import pathlib

# Allow running from the repo root or from inside pipeline/
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from quality import check_quality
from ingest import ingest_arxiv, ingest_pdf
from figures import extract_figures, select_blog_figures
from extract import extract_key_ideas
from diagram import maybe_generate_mermaid
from author import build_blog_post
from publish import publish, publish_digest
from llm import load_model
from daily import pick_daily_paper, mark_processed
from digest import build_weekly_digest
from vision import describe_figures
from config import cfg


def _remove_paper(arxiv_id: str) -> None:
    """Delete a paper's post file, figures, processed.json entry, and cache files."""
    repo_root = pathlib.Path(__file__).parent.parent
    removed: list[str] = []

    # 1. Find and delete the post file (search by arXiv ID in file content)
    for post_dir in [repo_root / "docs" / "posts", repo_root / "docs" / "digest" / "posts"]:
        if not post_dir.exists():
            continue
        for post_file in post_dir.glob("*.md"):
            if arxiv_id in post_file.read_text(encoding="utf-8"):
                post_file.unlink()
                removed.append(f"  🗑️  Post:    {post_file.relative_to(repo_root)}")

    # 2. Delete figures directory
    fig_dir = repo_root / "docs" / "assets" / "figures" / arxiv_id
    if fig_dir.exists():
        shutil.rmtree(fig_dir)
        removed.append(f"  🗑️  Figures: docs/assets/figures/{arxiv_id}/")

    # 3. Remove from processed.json
    processed_log = repo_root / "cache" / "processed.json"
    if processed_log.exists():
        ids: list[str] = json.loads(processed_log.read_text())
        if arxiv_id in ids:
            ids.remove(arxiv_id)
            processed_log.write_text(json.dumps(sorted(ids), indent=2))
            removed.append(f"  🗑️  processed.json entry removed")

    # 4. Delete cache files (non-destructive to pipeline; can be re-generated)
    for suffix in ["", "_extraction", "_figures", "_vision"]:
        for ext in [".json", ".pdf"]:
            cache_file = repo_root / "cache" / f"{arxiv_id}{suffix}{ext}"
            if cache_file.exists():
                cache_file.unlink()
                removed.append(f"  🗑️  Cache:   cache/{arxiv_id}{suffix}{ext}")

    if not removed:
        print(f"  ⚠️  Nothing found for ID '{arxiv_id}'. Check the ID and try again.")
        return

    print(f"\n🗑️  Removed all artifacts for {arxiv_id}:")
    for line in removed:
        print(line)

    # 5. Git commit the deletions
    subprocess.run(["git", "add", "-A", "docs/"], cwd=repo_root, check=False)
    result = subprocess.run(
        ["git", "commit", "-m", f"remove: paper {arxiv_id}"],
        cwd=repo_root, capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"\n  ✅ Committed. Run 'git push' to update GitHub Pages.")
    else:
        print(f"\n  ⚠️  Nothing staged for git commit (docs changes may already be clean).")


def main():
    parser = argparse.ArgumentParser(
        description="JarvisForResearchers — LLM-powered robotics & AI research blogger"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--arxiv", metavar="ID", help="arXiv paper ID (e.g. 2310.12931)")
    group.add_argument("--pdf", metavar="PATH", help="Path to a local PDF file")
    group.add_argument("--daily", action="store_true",
                       help="Auto-pick today's best unprocessed paper from arXiv")
    group.add_argument("--digest", action="store_true",
                       help="Build 'This Week in Robotics' multi-paper summary post")
    group.add_argument("--remove", metavar="ID",
                       help="Remove a paper by arXiv ID: deletes post, figures, and cache")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip quality gate",
    )
    parser.add_argument(
        "--no-vision",
        action="store_true",
        help="Skip vision figure descriptions (faster)",
    )
    parser.add_argument(
        "--quantise",
        action="store_true",
        help="Load model in 4-bit (for low VRAM / CPU)",
    )
    args = parser.parse_args()

    # --- Remove mode: delete a paper and all its artifacts ---
    if args.remove:
        _remove_paper(args.remove)
        return

    # --- Digest mode: weekly multi-paper summary ---
    if args.digest:
        print("\n📰 Digest mode — building 'This Week in Robotics'...")
        print("\n🤖 Loading Gemma 4 E4B...")
        tokenizer, model = load_model(quantise=args.quantise)
        content = build_weekly_digest(tokenizer, model)
        if content:
            print("\n🚀 Publishing digest...")
            publish_digest(content)
        return

    # --- Daily mode: auto-discover paper ---
    if args.daily:
        print("\n📅 Daily mode — searching arXiv for today's best paper...")
        arxiv_id = pick_daily_paper(verbose=True)
        if not arxiv_id:
            print("  Nothing to post today.")
            return
        args.arxiv = arxiv_id
        args.force = False  # quality gate already passed inside pick_daily_paper

    # --- Quality gate ---
    if args.arxiv and not args.force:
        print("\n🔍 Quality gate...")
        result = check_quality(args.arxiv)
        if not result["pass"]:
            print(f"  ❌ REJECTED: {result['reason']}")
            print("  Use --force to override.")
            return
        print(f"  ✅ PASSED: {result['reason']}")

    # --- Load model once, reuse for all LLM steps ---
    print("\n🤖 Loading Gemma 4 E4B...")
    tokenizer, model = load_model(quantise=args.quantise)

    print("\n📄 Step 1/6 — Ingesting paper...")
    paper = ingest_arxiv(args.arxiv) if args.arxiv else ingest_pdf(args.pdf)

    print("🖼️  Step 2/6 — Extracting figures from PDF...")
    all_figs = extract_figures(paper["id"], paper["pdf_path"])
    figures = select_blog_figures(all_figs)

    use_vision = cfg.vision.enabled and not getattr(args, "no_vision", False)
    if use_vision and figures:
        print("👁️  Step 3/6 — Describing figures with Gemma 4 vision...")
        figures = describe_figures(paper["id"], figures, tokenizer, model)
    else:
        print("👁️  Step 3/6 — Vision skipped")

    print("🧠 Step 4/6 — Extracting key ideas...")
    extraction = extract_key_ideas(paper, tokenizer, model)

    print("📐 Step 5/6 — Diagram check...")
    mermaid = maybe_generate_mermaid(extraction, figures, tokenizer, model)

    print("✍️  Step 6/6 — Authoring blog post...")
    post = build_blog_post(paper, extraction, figures, mermaid, tokenizer, model)

    print("🚀 Publishing...")
    publish(paper, post)

    # Record paper as processed so --daily skips it on future runs
    if paper.get("id"):
        mark_processed(paper["id"])
        print(f"  📝 Marked {paper['id']} as processed")


if __name__ == "__main__":
    main()
