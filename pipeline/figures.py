# pipeline/figures.py
import fitz
import pathlib
import re

# Save as JPEG to keep the git repo small.
# Quality 85 gives visually lossless output at ~6x smaller than PNG.
_JPEG_QUALITY = 85


def extract_figures(paper_id: str, pdf_path: str) -> list[dict]:
    """Extract all figures from the PDF and save them as compressed JPEGs."""
    import json as _json
    cache_file = pathlib.Path(f"cache/{paper_id}_figures.json")
    if cache_file.exists():
        print("  (cached) Skipping figure extraction")
        return _json.loads(cache_file.read_text())

    doc = fitz.open(pdf_path)
    out_dir = pathlib.Path(f"docs/assets/figures/{paper_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = []

    for page_num, page in enumerate(doc):
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)

            # Skip tiny decorative images (icons, logos, rule lines)
            if pix.width < 200 or pix.height < 150:
                continue

            # Normalise to RGB (JPEG does not support alpha or CMYK)
            if pix.n != 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            fname = f"fig_p{page_num + 1}_{img_idx}.jpg"
            fpath = out_dir / fname
            pix.save(str(fpath), jpg_quality=_JPEG_QUALITY)
            caption = _find_caption(page)

            figures.append(
                {
                    "path": f"/assets/figures/{paper_id}/{fname}",
                    "caption": caption,
                    "page": page_num + 1,
                    "figure_number": _parse_fig_num(caption),
                }
            )

    figures.sort(key=lambda f: f["figure_number"] or 99)
    print(f"  Extracted {len(figures)} figures from PDF")
    import json as _json
    cache_file = pathlib.Path(f"cache/{paper_id}_figures.json")
    cache_file.write_text(_json.dumps(figures))
    return figures


def select_blog_figures(figures: list[dict], max_figures: int = 4) -> list[dict]:
    """Pick the best figures to embed in the blog post."""
    captioned = [f for f in figures if f["caption"]]
    uncaptioned = [f for f in figures if not f["caption"]]
    pool = captioned if captioned else uncaptioned
    return pool[:max_figures]


def _find_caption(page) -> str:
    for block in page.get_text("blocks"):
        text = block[4].strip()
        if re.match(r"^(Figure|Fig\.?)\s*\d+", text, re.IGNORECASE):
            return text[:300]
    return ""


def _parse_fig_num(caption: str) -> int | None:
    m = re.search(r"(?:Figure|Fig\.?)\s*(\d+)", caption, re.IGNORECASE)
    return int(m.group(1)) if m else None
