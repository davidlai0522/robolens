# pipeline/config.py
"""
Load jarvisforresearchers/config.yaml and expose typed configuration sections.

All pipeline modules should import from here rather than hardcoding values.
Falls back to sensible defaults if config.yaml is absent.

Usage:
    from config import cfg
    print(cfg.blog.name)
    print(cfg.llm.model_id)
"""
import datetime
import pathlib

import yaml

_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.yaml"


def _load_raw() -> dict:
    if _CONFIG_PATH.exists():
        return yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    return {}


class _Blog:
    def __init__(self, d: dict) -> None:
        self.name: str = d.get("name", "JarvisForResearchers")
        self.description: str = d.get(
            "description", "AI research explained locally with Gemma 4"
        )
        self.github_username: str = d.get("github_username", "")
        self.github_repo: str = d.get("github_repo", "jarvisforresearchers")

    @property
    def site_url(self) -> str:
        if self.github_username:
            return f"https://{self.github_username}.github.io/{self.github_repo}"
        return ""

    @property
    def remote_url(self) -> str:
        if self.github_username:
            return f"git@github.com:{self.github_username}/{self.github_repo}.git"
        return ""


class _Llm:
    def __init__(self, d: dict) -> None:
        self.model_id: str = d.get("model_id", "google/gemma-4-E4B-it")
        self.min_free_vram_gib: float = float(d.get("min_free_vram_gib", 6.0))
        self.max_new_tokens: int = int(d.get("max_new_tokens", 2048))
        self.temperature: float = float(d.get("temperature", 0.2))


class _Quality:
    _DEFAULT_VENUES = {
        "NeurIPS", "ICML", "ICLR", "AAAI", "JMLR",
        "CVPR", "ICCV", "ECCV",
        "ICRA", "IROS", "CoRL", "RSS", "IJRR", "T-RO",
        "ACL", "EMNLP", "NAACL",
    }

    def __init__(self, d: dict) -> None:
        raw_venues = d.get("top_venues", list(self._DEFAULT_VENUES))
        self.top_venues: set[str] = set(raw_venues)
        thresholds = d.get("citation_thresholds", {})
        self._age_0: int = int(thresholds.get("age_0", 0))
        self._age_1: int = int(thresholds.get("age_1", 5))
        self._age_2: int = int(thresholds.get("age_2", 20))
        self._age_3_plus: int = int(thresholds.get("age_3_plus", 50))

    def citation_threshold(self, year: int) -> int:
        """Return the minimum citation count required for a paper published in `year`."""
        age = datetime.date.today().year - year
        if age <= 0:
            return self._age_0
        if age == 1:
            return self._age_1
        if age == 2:
            return self._age_2
        return self._age_3_plus


class _Discovery:
    def __init__(self, d: dict) -> None:
        self.categories: list[str] = d.get(
            "categories", ["cs.RO", "cs.AI", "cs.LG", "cs.CV"]
        )
        self.fetch_per_category: int = int(d.get("fetch_per_category", 30))
        self.cron_schedule: str = d.get("cron_schedule", "0 8 * * *")


class _Author:
    def __init__(self, d: dict) -> None:
        self.blog_name: str = d.get("blog_name", "JarvisForResearchers")
        self.audience: str = d.get("audience", "robotics and AI engineers")
        self.max_words: int = int(d.get("max_words", 1800))


class _Digest:
    def __init__(self, d: dict) -> None:
        self.lookback_days: int = int(d.get("lookback_days", 7))
        self.min_papers: int = int(d.get("min_papers", 2))
        self.title_prefix: str = d.get("title_prefix", "This Week in Robotics")


class _Vision:
    def __init__(self, d: dict) -> None:
        self.enabled: bool = bool(d.get("enabled", True))
        self.max_figures: int = int(d.get("max_figures", 3))


class _Telegram:
    def __init__(self, d: dict) -> None:
        raw_ids = d.get("allowed_user_ids", [])
        self.allowed_user_ids: list[int] = [int(uid) for uid in raw_ids if uid]
        self.notify_with_url: bool = bool(d.get("notify_with_url", True))


class _Config:
    def __init__(self) -> None:
        raw = _load_raw()
        self.blog = _Blog(raw.get("blog", {}))
        self.llm = _Llm(raw.get("llm", {}))
        self.quality = _Quality(raw.get("quality", {}))
        self.discovery = _Discovery(raw.get("discovery", {}))
        self.author = _Author(raw.get("author", {}))
        self.digest = _Digest(raw.get("digest", {}))
        self.vision = _Vision(raw.get("vision", {}))
        self.telegram = _Telegram(raw.get("telegram", {}))


# Module-level singleton — import this everywhere
cfg = _Config()
