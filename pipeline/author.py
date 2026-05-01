# pipeline/author.py
import datetime
import json
import re
from config import cfg
from llm import ask

# ── Tag / category helpers ───────────────────────────────────────────────────

_ARXIV_TO_TAGS: dict[str, list[str]] = {
    "cs.RO": ["robotics"],
    "cs.AI": ["artificial-intelligence"],
    "cs.LG": ["machine-learning"],
    "cs.CV": ["computer-vision"],
    "cs.CL": ["nlp"],
    "cs.SY": ["control-systems"],
    "cs.NE": ["neural-networks"],
    "eess.SY": ["control-systems"],
    "cs.MA": ["multi-agent"],
}

_ARXIV_TO_CATEGORY: dict[str, str] = {
    "cs.RO": "Robotics",
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
    "cs.CV": "Computer Vision",
    "cs.CL": "NLP",
    "cs.SY": "Control Systems",
    "cs.NE": "Neural Networks",
    "cs.MA": "Multi-Agent Systems",
}

# Longer phrases first so they take priority over shorter sub-phrases
_TOPIC_KEYWORDS: list[tuple[str, str]] = [
    ("reinforcement learning", "reinforcement-learning"),
    ("reward design", "reward-design"),
    ("reward function", "reward-design"),
    ("imitation learning", "imitation-learning"),
    ("sim-to-real", "sim-to-real"),
    ("sim to real", "sim-to-real"),
    ("large language model", "llm"),
    ("language model", "llm"),
    ("vision-language", "vision-language"),
    ("vision language", "vision-language"),
    ("foundation model", "foundation-models"),
    ("diffusion model", "diffusion-models"),
    ("diffusion policy", "diffusion-models"),
    ("human-robot interaction", "human-robot-interaction"),
    ("human robot interaction", "human-robot-interaction"),
    ("dexterous manipulation", "dexterous-manipulation"),
    ("motion planning", "motion-planning"),
    ("task planning", "task-planning"),
    ("pose estimation", "pose-estimation"),
    ("depth estimation", "depth-estimation"),
    ("object detection", "object-detection"),
    ("3d reconstruction", "3d-perception"),
    ("point cloud", "point-cloud"),
    ("manipulation", "manipulation"),
    ("locomotion", "locomotion"),
    ("grasping", "grasping"),
    ("navigation", "navigation"),
    ("planning", "planning"),
    ("perception", "perception"),
    ("affordance", "affordance"),
    ("segmentation", "segmentation"),
    ("transformer", "transformers"),
    ("multimodal", "multimodal"),
    ("multi-modal", "multimodal"),
    ("humanoid", "humanoid"),
    ("generalization", "generalization"),
    ("sim2real", "sim-to-real"),
    ("slam", "slam"),
]


def _generate_tags(paper: dict, extraction: dict) -> list[str]:
    """Generate specific tags from arXiv categories and paper content."""
    tags: list[str] = []

    for cat in paper.get("categories", []):
        for t in _ARXIV_TO_TAGS.get(cat, []):
            if t not in tags:
                tags.append(t)

    search_text = " ".join([
        extraction.get("one_sentence_summary", ""),
        extraction.get("problem_statement", ""),
        " ".join(extraction.get("key_contributions", [])),
        extraction.get("method_overview", ""),
    ]).lower()

    for keyword, tag in _TOPIC_KEYWORDS:
        if keyword in search_text and tag not in tags:
            tags.append(tag)

    return tags[:8] if tags else ["robotics", "ai-research"]


def _infer_category(paper: dict) -> str:
    """Infer blog category from the paper's primary arXiv category."""
    for cat in paper.get("categories", []):
        if cat in _ARXIV_TO_CATEGORY:
            return _ARXIV_TO_CATEGORY[cat]
    return "Research Digest"


def build_blog_post(
    paper: dict,
    extraction: dict,
    figures: list[dict],
    mermaid: str | None,
    tokenizer,
    model,
) -> str:
    """Author a full Markdown blog post using Gemma 4."""

    # Build figure Markdown blocks — use vision description as alt text when available
    def _fig_block(f: dict) -> str:
        alt = f.get("description") or f.get("caption") or "Figure from paper"
        visible = f.get("caption") or f.get("description") or ""
        img_md = f'![{alt}]({f["path"]})'
        return f"{img_md}\n*{visible}*" if visible else img_md

    figure_md = "\n\n".join(_fig_block(f) for f in figures)

    # Build a figure context block to help the LLM reference figures accurately
    fig_context = ""
    described = [f for f in figures if f.get("description")]
    if described:
        lines = ["Figure context (what each figure actually shows):"]
        for i, f in enumerate(described, 1):
            cap = f.get("caption") or f"Figure {i}"
            lines.append(f"  Figure {i} ({cap[:60]}): {f['description']}")
        fig_context = "\n".join(lines)

    prompt = f"""You are writing for {cfg.author.blog_name}, a technical blog for {cfg.author.audience}.
Tone: precise, clear, never dumbed-down. Write like a good PhD advisor explaining
to a sharp master's student. Avoid hype. Every claim must follow from the outline.

Write the blog post body in Markdown. Do NOT write front-matter. Do NOT write a
Citation section. Follow this exact section order:

## TL;DR
## The Problem
## Key Contributions
## How It Works
[Add ### subsections per architecture_component]
## Results
[Include a Markdown table from key_results — numbers verbatim from the outline]
## Why This Matters
## Limitations & Open Questions

Hard rules:
- All numbers must exactly match those in key_results
- Component names must be verbatim from architecture_components
- Maximum {cfg.author.max_words} words
- Do not add any references or footnotes
{fig_context and chr(10) + fig_context}

Outline:
{json.dumps(extraction, indent=2)}"""

    prose = ask(prompt, tokenizer, model, temperature=0.3, max_new_tokens=3000)

    # Inject figures/mermaid directly after "## How It Works"
    visual = figure_md or mermaid or ""
    if visual:
        prose = prose.replace("## How It Works", f"## How It Works\n\n{visual}\n", 1)

    # Front-matter
    slug = _slugify(paper["title"])
    date = datetime.date.today().isoformat()
    tags = _generate_tags(paper, extraction)
    category = _infer_category(paper)
    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    front_matter = f"""---
title: "{paper['title']}"
date: {date}
authors:
  - JarvisForResearchers Bot
tags:
{tags_yaml}
categories:
  - {category}
description: >
  {extraction['one_sentence_summary']}
---
"""

    # Citation block
    authors = paper["authors"][:6]
    author_str = " and ".join(authors)
    if len(paper["authors"]) > 6:
        author_str += " et al."

    arxiv_url = paper.get("arxiv_url", "")
    paper_id_safe = paper["id"].replace(".", "")
    paper_link = f"**Paper:** [{paper['id']}]({arxiv_url})" if arxiv_url else ""
    citation = f"""

---

## Citation

{paper_link}

```bibtex
@article{{{paper_id_safe},
  title   = {{{paper['title']}}},
  author  = {{{author_str}}},
  journal = {{arXiv preprint arXiv:{paper['id']}}},
  year    = {{{paper['year']}}},
  url     = {{{arxiv_url}}}
}}
```
"""

    return front_matter + f"\n> *Generated by JarvisForResearchers Bot on {date}*\n\n" + prose + citation


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
