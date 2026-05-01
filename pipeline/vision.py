# pipeline/vision.py
"""
v0.4 — Vision figure descriptions via Gemma 4's multimodal capability.

For each extracted figure, calls Gemma 4 with the image to produce a precise
2-3 sentence technical description: figure type, key visual elements, and what
it demonstrates. Descriptions are cached and then injected into author.py's
prompt so the LLM can write prose that accurately references figure content.
"""
import json
import pathlib

from llm import ask_with_image
from config import cfg

_REPO_ROOT = pathlib.Path(__file__).parent.parent

_VISION_PROMPT = (
    "You are analysing a figure extracted from a robotics or AI research paper.\n"
    "In 2-3 precise sentences describe:\n"
    "1. What type of figure this is (architecture diagram, result plot, "
    "qualitative comparison, system photo, etc.).\n"
    "2. The key visual elements — component names, axes labels, colour coding, "
    "or structural relationships you can read from the image.\n"
    "3. What the figure demonstrates or shows about the method or results.\n"
    "Be specific. Do not use vague adjectives. Do not invent information not "
    "visible in the image."
)


def _resolve_path(fig: dict, paper_id: str) -> pathlib.Path | None:
    """
    Figures are stored with a docs-relative path like
    '../../assets/figures/<id>/<fname>'.  Resolve to the actual disk path.
    """
    fname = pathlib.Path(fig["path"]).name
    candidate = _REPO_ROOT / "docs" / "assets" / "figures" / paper_id / fname
    return candidate if candidate.exists() else None


def describe_figures(
    paper_id: str,
    figures: list[dict],
    processor,
    model,
) -> list[dict]:
    """
    Attach a 'description' key to each figure dict by querying Gemma 4's vision
    encoder.  Results are cached in cache/<paper_id>_vision.json so re-runs skip
    inference.  Returns the updated figures list.
    """
    cache_file = pathlib.Path(f"cache/{paper_id}_vision.json")

    # Load existing cache
    cached: dict[str, str] = {}
    if cache_file.exists():
        cached = json.loads(cache_file.read_text())

    max_figs = cfg.vision.max_figures
    described = 0

    for fig in figures[:max_figs]:
        fname = pathlib.Path(fig["path"]).name

        # Use cached description if available
        if fname in cached:
            fig["description"] = cached[fname]
            continue

        img_path = _resolve_path(fig, paper_id)
        if img_path is None:
            continue

        print(f"    👁️  Describing {fname}...")
        description = ask_with_image(
            _VISION_PROMPT,
            str(img_path),
            processor,
            model,
            max_new_tokens=256,
        )
        if description:
            fig["description"] = description
            cached[fname] = description
            described += 1

    # Persist cache
    cache_file.parent.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(cached, indent=2))

    if described:
        print(f"  👁️  Described {described} figure(s) with Gemma 4 vision")

    return figures
