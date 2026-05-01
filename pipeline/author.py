# pipeline/author.py
import datetime
import json
import re
from llm import ask


def build_blog_post(
    paper: dict,
    extraction: dict,
    figures: list[dict],
    mermaid: str | None,
    tokenizer,
    model,
) -> str:
    """Author a full Markdown blog post using Gemma 4."""

    # Build figure Markdown blocks from real extracted images
    figure_md = "\n\n".join(
        (
            f'![{f["caption"] or "Figure from paper"}]({f["path"]})\n'
            f'*{f["caption"]}*'
            if f["caption"]
            else f'![Figure from paper]({f["path"]})'
        )
        for f in figures
    )

    prompt = f"""You are writing for RoboLens, a technical blog for robotics and AI engineers.
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
## Why This Matters for Robotics
## Limitations & Open Questions

Hard rules:
- All numbers must exactly match those in key_results
- Component names must be verbatim from architecture_components
- Maximum 1800 words
- Do not add any references or footnotes

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
    front_matter = f"""---
title: "{paper['title']}"
date: {date}
authors:
  - RoboLens Bot
tags:
  - robotics
  - AI
categories:
  - Research Digest
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
    citation = f"""
---

## Citation

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

    return front_matter + "\n" + prose + citation


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
