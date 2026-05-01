# RoboLens

**RoboLens** is an open-source, automated blogging pipeline that uses
[Google Gemma 4 E4B](https://huggingface.co/google/gemma-4-E4B-it) running
**locally** — no API costs, no data leaving your machine.

It enforces a strict paper quality gate before doing any work, extracts real
figures directly from the PDF, and publishes beautifully formatted blog posts
to a free GitHub Pages site.

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Log in to HuggingFace (one-time, to download Gemma 4)
huggingface-cli login

# 3. Accept the Gemma 4 license at:
#    https://huggingface.co/google/gemma-4-E4B-it

# 4. Run the pipeline
python pipeline/run.py --arxiv 2310.12931        # ACT (CoRL 2023)
python pipeline/run.py --arxiv 2310.12931 --quantise  # 4-bit for low VRAM
python pipeline/run.py --pdf ./papers/my.pdf          # local PDF
python pipeline/run.py --arxiv 2504.99999 --force     # bypass quality gate

# 5. Preview locally
mkdocs serve   # → http://127.0.0.1:8000
```

## Pipeline

```
arXiv ID / PDF path
  → quality.py  (venue + citation gate)
  → ingest.py   (PDF text + metadata)
  → figures.py  (extract real PDF figures)
  → extract.py  (Gemma 4: key ideas → JSON)
  → diagram.py  (Mermaid fallback — only if no figures)
  → author.py   (Gemma 4: write Markdown post)
  → publish.py  (git commit + push)
  → GitHub Actions → mkdocs gh-deploy
  → https://davidlai0522.github.io/robolens
```

## License

MIT — see [COPILOT.md](COPILOT.md) for full specification.
Gemma 4 is released under the Apache 2.0 License by Google DeepMind.
