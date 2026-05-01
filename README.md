# JarvisForResearchers — Local LLM Blog Pipeline

> Turn any arXiv paper into a polished technical blog post — no API costs, no cloud GPUs, no data leaving your machine.

**JarvisForResearchers** is an open-source pipeline that runs a local language model (Google Gemma 4 E4B) to read research papers, extract the key ideas, and publish a well-structured blog post to GitHub Pages — automatically.

It works for **any technical field**: robotics, NLP, computer vision, systems, bioinformatics, etc. Everything is configured through a single `config.yaml` file.

---

## What it produces

For each paper, the pipeline:
1. Checks the paper quality (venue ranking + citation count) and rejects low-quality work
2. Downloads the PDF and extracts real figures
3. Asks Gemma 4 to extract a structured outline (key ideas, method, results)
4. Asks Gemma 4 to write a ~1800-word blog post in your voice
5. Publishes the Markdown to your GitHub Pages site via `git push`

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Managed via `uv` (installed below) |
| Git | Any recent version |
| NVIDIA GPU | 8 GB VRAM recommended; 5 GB works with 4-bit quantisation; CPU works but slow |
| GitHub account | Free tier is sufficient |
| HuggingFace account | Free; needed to download Gemma 4 |

---

## Quick Start (5 steps)

### Step 1 — Fork & clone

Click **Fork** on GitHub, then:

```bash
git clone git@github.com:<your-username>/jarvisforresearchers.git
cd jarvisforresearchers
```

### Step 2 — Edit `config.yaml`

Open `config.yaml` in any text editor. The only fields you **must** change:

```yaml
blog:
  name: "My ML Blog"               # ← your blog's name
  github_username: "your-username" # ← your GitHub username
  github_repo: "jarvisforresearchers"          # ← your repo name (matches what you forked)

author:
  audience: "machine learning engineers"  # ← who reads your blog
```

Everything else has sensible defaults. See the [Configuration Reference](#configuration-reference) section below for all options.

### Step 3 — Update `mkdocs.yml`

Open `mkdocs.yml` and change two lines to match your `config.yaml`:

```yaml
site_name: My ML Blog                                        # ← matches blog.name
site_url: https://your-username.github.io/jarvisforresearchers          # ← matches blog.github_username + blog.github_repo
```

### Step 4 — Install dependencies

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # or restart your terminal

# Install all Python dependencies
uv sync

# Log in to HuggingFace (one-time — needed to download Gemma 4)
uv run huggingface-cli login
# → paste your token from https://huggingface.co/settings/tokens
# → accept the Gemma 4 licence at https://huggingface.co/google/gemma-4-E4B-it
```

### Step 5 — Run your first post

```bash
# Run on a well-known paper (ACT — CoRL 2023)
uv run python pipeline/run.py --arxiv 2310.12931

# Preview the result locally
uv run mkdocs serve   # → http://127.0.0.1:8000
```

---

## GitHub Pages Setup

Your posts are committed locally but won't be live until GitHub Pages is configured.

### 1. Create the GitHub repository

If you forked: your repo already exists. If starting fresh:

```bash
# Create the repo on GitHub, then add it as remote
git remote add origin git@github.com:<your-username>/jarvisforresearchers.git
git push -u origin main
```

### 2. Deploy the site for the first time

```bash
uv run mkdocs gh-deploy --force --remote-branch gh-pages
```

This creates the `gh-pages` branch that GitHub Pages serves.

### 3. Enable GitHub Pages

Go to your repo → **Settings → Pages**:
- Source: **Deploy from a branch**
- Branch: **gh-pages** / **(root)**
- Click **Save**

After about 60 seconds, your blog is live at:
```
https://<your-username>.github.io/<your-repo>/
```

### 4. Future pushes deploy automatically

The included GitHub Actions workflow (`.github/workflows/publish.yml`) redeploys MkDocs every time you push a new post to `main`. You don't need to run `gh-deploy` again.

---

## Running the pipeline

```bash
# Process a specific arXiv paper
uv run python pipeline/run.py --arxiv 2310.12931

# Process a local PDF
uv run python pipeline/run.py --pdf ./papers/my_paper.pdf

# Force a paper through even if it fails the quality gate
uv run python pipeline/run.py --arxiv 2504.99999 --force

# Enable 4-bit quantisation (for GPUs with < 6 GB VRAM, or CPU)
uv run python pipeline/run.py --arxiv 2310.12931 --quantise

# Auto-discover and post today's best paper from your configured categories
uv run python pipeline/run.py --daily
```

---

## Daily Automation (optional)

To have the pipeline run every morning and post a new paper automatically:

```bash
# Install the cron job (reads schedule from config.yaml)
bash setup_cron.sh

# Remove it
bash setup_cron.sh --remove
```

The cron schedule is controlled by `discovery.cron_schedule` in `config.yaml`. Default is `0 8 * * *` (08:00 every morning). Use [crontab.guru](https://crontab.guru) to build your own schedule.

Logs are written to `logs/daily.log`.

---

## Telegram Bot (optional)

Send an arXiv link from your phone → get a full blog post generated and published automatically.

### Step 1 — Create a Telegram bot

1. Open Telegram and message **[@BotFather](https://t.me/botfather)**
2. Send `/newbot` and follow the prompts to name your bot
3. Copy the **bot token** it gives you (looks like `123456789:AAFxxxxxxxx`)

### Step 2 — Set your bot token

> [!IMPORTANT]
> Never commit your token to git. The `.env` file is already in `.gitignore` — always use it to store secrets.

```bash
cp .env.example .env
```

Open `.env` in a text editor and replace the placeholder:

```
TELEGRAM_BOT_TOKEN=123456789:AAFxxxxxxxx
```

### Step 3 — (Optional) Restrict to your user ID

By default the bot accepts messages from anyone. To lock it down to just yourself:

1. Message **[@userinfobot](https://t.me/userinfobot)** on Telegram to find your numeric user ID
2. Add it to `config.yaml`:

```yaml
telegram:
  allowed_user_ids:
    - 123456789   # ← your Telegram user ID
```

### Step 4 — Run the bot

```bash
uv run python telegram_bot.py
```

The bot runs in polling mode — no public server or webhook needed. Keep the terminal open while you want the bot to be active.

### Usage

| What to send | What happens |
|---|---|
| `https://arxiv.org/abs/2310.12931` | Run full pipeline (quality gate on) |
| `2310.12931` | Same — bare arXiv ID also works |
| `/force 2310.12931` | Skip quality gate |
| `/status` | Check if a pipeline is currently running |
| `/help` | Show all commands |

The bot replies immediately to acknowledge your request, then sends the blog post URL once the pipeline finishes (~3–10 min depending on hardware).

---

## Configuration Reference

All configuration lives in `config.yaml` at the repo root. Here is every option:

### `blog` — Site identity

| Key | Default | Description |
|---|---|---|
| `name` | `"JarvisForResearchers"` | Blog name shown in the header and browser tab |
| `description` | `"..."` | One-sentence tagline on the home page |
| `github_username` | `""` | Your GitHub username — used to build the live URL |
| `github_repo` | `"jarvisforresearchers"` | Repository name |

### `llm` — Language model

| Key | Default | Description |
|---|---|---|
| `model_id` | `"google/gemma-4-E4B-it"` | Any HuggingFace chat model |
| `min_free_vram_gib` | `6.0` | Auto-enable 4-bit quant below this VRAM threshold |
| `max_new_tokens` | `2048` | Tokens generated per LLM call |
| `temperature` | `0.2` | Sampling temperature (0 = deterministic) |

**Changing the model:** Any instruction-tuned model from HuggingFace that supports chat templates works. Tested alternatives:
- `google/gemma-3-4b-it` — smaller, faster, less capable
- `mistralai/Mistral-7B-Instruct-v0.3` — strong alternative, requires accepting licence

### `quality` — Paper quality gate

| Key | Default | Description |
|---|---|---|
| `top_venues` | (list of 18 venues) | Papers from these venues always pass |
| `citation_thresholds.age_0` | `0` | Min citations for papers from this year |
| `citation_thresholds.age_1` | `5` | Min citations for ~1 year old papers |
| `citation_thresholds.age_2` | `20` | Min citations for ~2 year old papers |
| `citation_thresholds.age_3_plus` | `50` | Min citations for older papers |

**Customising for your field:** Replace or extend `top_venues` with the top conferences in your domain. Examples:

```yaml
# NLP / LLM focus
top_venues:
  - ACL
  - EMNLP
  - NAACL
  - EACL
  - CoNLL
  - NeurIPS
  - ICML
  - ICLR

# Systems / architecture
top_venues:
  - OSDI
  - SOSP
  - ASPLOS
  - ISCA
  - MICRO
  - USENIX ATC

# Security
top_venues:
  - IEEE S&P
  - CCS
  - USENIX Security
  - NDSS
```

### `discovery` — Daily paper discovery

| Key | Default | Description |
|---|---|---|
| `categories` | `[cs.RO, cs.AI, cs.LG, cs.CV]` | arXiv categories to monitor |
| `fetch_per_category` | `30` | Papers fetched per category per run |
| `cron_schedule` | `"0 8 * * *"` | When `setup_cron.sh` schedules the daily run |

**Changing your field:** Find category codes at [arxiv.org/category_taxonomy](https://arxiv.org/category_taxonomy).

```yaml
# NLP / LLM focus
categories:
  - cs.CL   # Computation and Language
  - cs.AI
  - cs.LG

# Computer vision only
categories:
  - cs.CV
  - eess.IV  # Image and Video Processing
```

### `author` — Writing style

| Key | Default | Description |
|---|---|---|
| `blog_name` | `"JarvisForResearchers"` | Blog name used inside the LLM writing prompt |
| `audience` | `"robotics and AI engineers"` | Reader description — calibrates depth and tone |
| `max_words` | `1800` | Target word count per post |

---

## Hardware Guide

| Hardware | Config | Expected speed |
|---|---|---|
| NVIDIA GPU ≥ 8 GB VRAM | Default (bf16) | ~3–5 min per post |
| NVIDIA GPU 4–6 GB VRAM | `--quantise` or set `min_free_vram_gib: 0` to force | ~5–8 min |
| Apple Silicon M1/M2/M3 | Default (MPS backend, no flag needed) | ~8–12 min |
| CPU only | `--quantise` | ~20–40 min |

The pipeline auto-enables 4-bit quantisation when free VRAM is below `min_free_vram_gib`. You can force it permanently by passing `--quantise`, or disable auto-detection by setting `min_free_vram_gib: 0`.

---

## Troubleshooting

**`huggingface_hub.errors.GatedRepoError`**
You need to accept the Gemma 4 licence at [huggingface.co/google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it).

**`torch.OutOfMemoryError`**
Run with `--quantise`, or lower `min_free_vram_gib` in `config.yaml` so 4-bit activates earlier.

**`❌ REJECTED: arXiv preprint with only N citations`**
The paper didn't pass the quality gate. Either lower `citation_thresholds` in `config.yaml`, add its venue to `top_venues`, or use `--force` to bypass the gate for this run.

**`⚠️ No git remote configured`**
Run `git remote add origin git@github.com:<username>/<repo>.git` then `git push -u origin main`.

**Posts not showing on GitHub Pages**
Make sure `site_url` in `mkdocs.yml` exactly matches `https://<username>.github.io/<repo>`, and that GitHub Pages is set to serve from the `gh-pages` branch.

**`AttributeError` with transformers**
Make sure you have transformers ≥ 4.52: `uv add "transformers>=4.52.0"`.

---

## Pipeline overview

```
config.yaml
    │
    ▼
[ arXiv ID / local PDF ]
    │
    ▼
quality.py  ── venue allowlist + Semantic Scholar citation check ──► REJECT
    │ PASS
    ▼
ingest.py   ── download PDF, extract text + metadata
    │
    ▼
figures.py  ── extract real figures from PDF (quality-filtered)
    │
    ▼
extract.py  ── Gemma 4: paper text → structured JSON outline
    │
    ▼
diagram.py  ── Gemma 4: Mermaid fallback (only if no PDF figures)
    │
    ▼
author.py   ── Gemma 4: JSON outline → Markdown blog post
    │
    ▼
publish.py  ── git commit + push → GitHub Actions → GitHub Pages
    │
    ▼
https://<username>.github.io/<repo>/
```

---

## License

MIT — free to use, modify, and distribute.

Gemma 4 is released under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) by Google DeepMind.
Figures embedded in posts are reproduced from their respective papers for educational commentary under fair use. Always link back to the original arXiv page.

Gemma 4 is released under the Apache 2.0 License by Google DeepMind.
