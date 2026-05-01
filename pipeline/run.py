#!/usr/bin/env python3
"""
Usage:
  python pipeline/run.py --arxiv 2504.01234
  python pipeline/run.py --pdf   ./papers/smolvla.pdf
  python pipeline/run.py --arxiv 2504.01234 --force     # skip quality gate
  python pipeline/run.py --arxiv 2504.01234 --quantise  # 4-bit for low VRAM
"""
import argparse
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
from publish import publish
from llm import load_model


def main():
    parser = argparse.ArgumentParser(
        description="RoboLens — LLM-powered robotics & AI research blogger"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--arxiv", metavar="ID", help="arXiv paper ID (e.g. 2310.12931)")
    group.add_argument("--pdf", metavar="PATH", help="Path to a local PDF file")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip quality gate",
    )
    parser.add_argument(
        "--quantise",
        action="store_true",
        help="Load model in 4-bit (for low VRAM / CPU)",
    )
    args = parser.parse_args()

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

    print("\n📄 Step 1/5 — Ingesting paper...")
    paper = ingest_arxiv(args.arxiv) if args.arxiv else ingest_pdf(args.pdf)

    print("🖼️  Step 2/5 — Extracting figures from PDF...")
    all_figs = extract_figures(paper["id"], paper["pdf_path"])
    figures = select_blog_figures(all_figs)

    print("🧠 Step 3/5 — Extracting key ideas...")
    extraction = extract_key_ideas(paper, tokenizer, model)

    print("📐 Step 4/5 — Diagram check...")
    mermaid = maybe_generate_mermaid(extraction, figures, tokenizer, model)

    print("✍️  Step 5/5 — Authoring blog post...")
    post = build_blog_post(paper, extraction, figures, mermaid, tokenizer, model)

    print("🚀 Publishing...")
    publish(paper, post)


if __name__ == "__main__":
    main()
