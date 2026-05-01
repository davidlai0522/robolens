# pipeline/publish.py
import datetime
import pathlib
import re
import subprocess
from config import cfg


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def _has_remote() -> bool:
    result = _git("remote", check=False)
    return bool(result.stdout.strip())


def publish(paper: dict, post_content: str):
    """Write the blog post to docs/posts/ and push to GitHub."""
    slug = re.sub(r"[^a-z0-9]+", "-", paper["title"].lower()).strip("-")[:60]
    date = datetime.date.today().isoformat()
    filename = f"{date}-{slug}.md"
    dest = pathlib.Path("docs/posts") / filename

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  (cached) Post already exists: {dest} — skipping commit")
        return
    dest.write_text(post_content, encoding="utf-8")
    print(f"  Written: {dest}")

    _git("add", "docs/")
    _git("commit", "-m", f"feat: new post — {paper['title'][:60]}")
    print(f"  ✅ Post committed locally.")

    if not _has_remote():
        remote_hint = cfg.blog.remote_url or "git@github.com:<username>/<repo>.git"
        print(
            "\n⚠️  No git remote configured — skipping push.\n"
            "  To publish to GitHub Pages, run once:\n"
            "\n"
            f"    git remote add origin {remote_hint}\n"
            "    git push -u origin main\n"
            "\n"
            "  Then future runs will push automatically.\n"
            f"  Post is ready locally at: {dest}"
        )
        return

    _git("push")
    site = cfg.blog.site_url
    if site:
        print(f"✅ Live at: {site}/posts/{slug}/")
    else:
        print("✅ Pushed. Check your GitHub Pages URL for the live post.")
