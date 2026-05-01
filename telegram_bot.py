#!/usr/bin/env python3
"""
JarvisForResearchers Telegram Bot
─────────────────────
Paste an arXiv link in Telegram → get a full blog post generated and saved.

Setup:
  1. cp .env.example .env
  2. Edit .env and set TELEGRAM_BOT_TOKEN=<your token from @BotFather>
  3. uv run python telegram_bot.py

Supported input formats:
  https://arxiv.org/abs/2310.12931
  https://arxiv.org/pdf/2310.12931
  arxiv.org/abs/2310.12931v2
  2310.12931   (bare ID)

Commands:
  /start          — Welcome message
  /help           — Show usage
  /force <ID>     — Run pipeline, skipping the quality gate
  /status         — Show if a pipeline is currently running
"""
import asyncio
import logging
import os
import pathlib
import re
import subprocess
import sys
from typing import Optional

# Load .env before anything else
try:
    from dotenv import load_dotenv

    load_dotenv(pathlib.Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on env vars being set in the shell

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = pathlib.Path(__file__).parent
PIPELINE_DIR = REPO_ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

from config import cfg  # noqa: E402 — must come after sys.path insert

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("jarvisforresearchers.bot")

# ── arXiv ID regex ────────────────────────────────────────────────────────────
# Matches: 2310.12931  2310.12931v2  arxiv.org/abs/2310.12931  arxiv.org/pdf/...
ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)",
    re.IGNORECASE,
)

# ── Global state ──────────────────────────────────────────────────────────────
# Tracks whether a pipeline subprocess is currently running.
_running_lock = asyncio.Lock()
_running_paper: Optional[str] = None  # arXiv ID currently being processed


# ── Access control ────────────────────────────────────────────────────────────
def _is_allowed(user_id: int) -> bool:
    allowed = cfg.telegram.allowed_user_ids
    return (not allowed) or (user_id in allowed)


def _access_denied_text() -> str:
    return (
        "⛔ Sorry, this bot is restricted to authorised users.\n"
        "Ask the bot owner to add your user ID to `config.yaml → telegram.allowed_user_ids`."
    )


# ── Pipeline runner ───────────────────────────────────────────────────────────
async def _run_pipeline(arxiv_id: str, force: bool = False) -> dict:
    """
    Run pipeline/run.py as a subprocess.
    Returns {"success": bool, "output": str, "post_path": str | None}.
    """
    global _running_paper

    cmd = [sys.executable, str(PIPELINE_DIR / "run.py"), "--arxiv", arxiv_id]
    if force:
        cmd.append("--force")

    log.info("Spawning pipeline: %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_ROOT),
    )

    _running_paper = arxiv_id
    stdout, _ = await proc.communicate()
    _running_paper = None

    output = stdout.decode(errors="replace")
    success = proc.returncode == 0

    # Try to find the written post path in the output
    post_path = None
    for line in output.splitlines():
        if "Written:" in line:
            # e.g. "  Written: docs/posts/2026-05-01-some-title.md"
            post_path = line.split("Written:")[-1].strip()
            break

    log.info(
        "Pipeline finished (rc=%d) for %s — post_path=%s",
        proc.returncode,
        arxiv_id,
        post_path,
    )
    return {"success": success, "output": output, "post_path": post_path}


def _build_reply(arxiv_id: str, result: dict, force: bool) -> str:
    """Format the Telegram reply message from the pipeline result."""
    output = result["output"]

    if result["success"]:
        # Extract post title from output if possible
        title_line = ""
        for line in output.splitlines():
            if "feat: new post" in line.lower() or "written:" in line.lower():
                title_line = line.strip()
                break

        url_part = ""
        if cfg.telegram.notify_with_url and cfg.blog.site_url and result["post_path"]:
            # Derive slug from the filename: "2026-05-01-some-slug.md" → "some-slug"
            fname = pathlib.Path(result["post_path"]).stem  # "2026-05-01-some-slug"
            parts = fname.split("-", 3)  # ["2026", "05", "01", "some-slug"]
            slug = parts[3] if len(parts) >= 4 else fname
            url_part = f"\n\n🌐 <a href='{cfg.blog.site_url}/posts/{slug}/'>View on GitHub Pages</a>"
        elif result["post_path"]:
            url_part = f"\n\n📄 Saved to <code>{result['post_path']}</code>"

        return (
            f"✅ <b>Blog post generated for <code>{arxiv_id}</code>!</b>"
            f"{url_part}"
        )

    # Failed — check for quality rejection
    if "REJECTED" in output:
        rejection_line = ""
        for line in output.splitlines():
            if "REJECTED" in line or "citations" in line.lower() or "threshold" in line.lower():
                rejection_line = line.strip().lstrip("❌ ")
                break
        return (
            f"❌ <b>Quality gate rejected <code>{arxiv_id}</code></b>\n\n"
            f"<i>{rejection_line}</i>\n\n"
            f"💡 To override, reply with:\n"
            f"<code>/force {arxiv_id}</code>"
        )

    # Generic failure — show last few lines of output for debugging
    tail = "\n".join(output.strip().splitlines()[-8:])
    return (
        f"💥 <b>Pipeline failed for <code>{arxiv_id}</code></b>\n\n"
        f"<pre>{tail[:800]}</pre>"
    )


# ── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(_access_denied_text())
        return
    await update.message.reply_html(
        "👋 <b>Welcome to JarvisForResearchers Bot!</b>\n\n"
        "Send me any arXiv link and I'll generate a full blog post for you.\n\n"
        "<b>Examples:</b>\n"
        "• <code>https://arxiv.org/abs/2310.12931</code>\n"
        "• <code>2310.12931</code>\n\n"
        "Use /help for more options."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(_access_denied_text())
        return
    await update.message.reply_html(
        "<b>JarvisForResearchers Bot — Help</b>\n\n"
        "<b>Send an arXiv link or ID to generate a blog post.</b>\n\n"
        "<b>Commands:</b>\n"
        "• /start — Welcome message\n"
        "• /help — This message\n"
        "• /force <code>&lt;arxiv_id&gt;</code> — Skip quality gate\n"
        "• /status — Check if pipeline is running\n\n"
        "<b>Quality gate:</b>\n"
        "Papers are checked for venue/citation quality before processing.\n"
        "Brand-new preprints (published this year) always pass.\n"
        "Use <code>/force</code> to bypass for any paper."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(_access_denied_text())
        return
    if _running_paper:
        await update.message.reply_html(
            f"⏳ <b>Pipeline running</b>\n\n"
            f"Currently processing: <code>{_running_paper}</code>"
        )
    else:
        await update.message.reply_text("✅ No pipeline running — ready for a new paper!")


async def cmd_force(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(_access_denied_text())
        return

    args = context.args
    if not args:
        await update.message.reply_html(
            "Usage: <code>/force &lt;arxiv_id&gt;</code>\n"
            "Example: <code>/force 2310.12931</code>"
        )
        return

    arxiv_id_raw = args[0].strip()
    match = ARXIV_RE.search(arxiv_id_raw)
    if not match:
        await update.message.reply_text(
            f"❓ Couldn't parse an arXiv ID from: {arxiv_id_raw!r}"
        )
        return

    arxiv_id = match.group(1)
    await _process_arxiv(update, arxiv_id, force=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(_access_denied_text())
        return

    text = update.message.text or ""
    match = ARXIV_RE.search(text)
    if not match:
        return  # Not an arXiv link — ignore silently

    arxiv_id = match.group(1)
    await _process_arxiv(update, arxiv_id, force=False)


async def _process_arxiv(update: Update, arxiv_id: str, force: bool) -> None:
    """Shared logic: acknowledge → run pipeline → reply."""
    global _running_paper

    # Refuse if another paper is already running
    if _running_paper:
        await update.message.reply_html(
            f"⏳ <b>Already processing <code>{_running_paper}</code></b>\n\n"
            "Please wait until the current pipeline finishes, then send your link again."
        )
        return

    force_note = " (quality gate skipped)" if force else ""
    await update.message.reply_html(
        f"🔍 Found arXiv ID <code>{arxiv_id}</code>{force_note}\n\n"
        "⏳ <b>Starting pipeline…</b>\n"
        "This typically takes 3–10 minutes (model load + inference).\n"
        "I'll reply here when it's done!"
    )

    async with _running_lock:
        result = await _run_pipeline(arxiv_id, force=force)

    reply = _build_reply(arxiv_id, result, force)
    await update.message.reply_html(reply, disable_web_page_preview=False)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print(
            "❌ TELEGRAM_BOT_TOKEN is not set.\n"
            "   1. Copy .env.example → .env\n"
            "   2. Set TELEGRAM_BOT_TOKEN=<your token> in .env\n"
            "   3. Get a token from @BotFather on Telegram."
        )
        sys.exit(1)

    log.info("Starting JarvisForResearchers Telegram bot (polling mode)…")
    log.info("Allowed users: %s", cfg.telegram.allowed_user_ids or "everyone")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("force", cmd_force))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 JarvisForResearchers bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
