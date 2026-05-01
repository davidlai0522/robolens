# pipeline/figures.py
import json
import fitz
import pathlib
import re

# Save as JPEG to keep the git repo small.
# Quality 85 gives visually lossless output at ~6x smaller than PNG.
_JPEG_QUALITY = 85

# --- v0.2 Figure quality filter thresholds ---
# Minimum pixel dimensions — skip rule lines, tiny icons
_MIN_WIDTH = 200
_MIN_HEIGHT = 150
# Aspect ratio guard — skip banners, rule lines (very wide and short)
_MAX_ASPECT_RATIO = 8.0
# Near-uniform colour guard — skip solid background blocks / logos
# Measures stddev of pixel values; below this = nearly one flat colour
_MIN_STDDEV = 8.0
# Minimum fraction of non-white pixels — skip white-background placeholders
_MIN_CONTENT_RATIO = 0.05


def _is_quality_figure(pix: fitz.Pixmap) -> tuple[bool, str]:
    """
    Return (True, "") if the image is a real figure, or (False, reason) if it
    should be skipped.  Runs fast pixel-level heuristics with no ML required.
    """
    w, h = pix.width, pix.height

    # 1. Size gate (already checked before call, but kept for completeness)
    if w < _MIN_WIDTH or h < _MIN_HEIGHT:
        return False, f"too small ({w}×{h})"

    # 2. Aspect ratio — very wide thin strips are rule lines / headers
    if w / h > _MAX_ASPECT_RATIO:
        return False, f"banner aspect ratio ({w/h:.1f})"

    # 3. Pixel-level checks — need raw samples
    import struct
    n = pix.n  # channels (already normalised to 3=RGB)
    samples = pix.samples  # bytes

    total_pixels = w * h
    # Compute mean and stddev over all channels via a fast sum
    pixel_sum = 0
    pixel_sq_sum = 0
    white_pixels = 0

    step = max(1, total_pixels // 4000)  # sample at most ~4000 pixels for speed
    sampled = 0
    for i in range(0, total_pixels, step):
        offset = i * n
        r = samples[offset]
        g = samples[offset + 1]
        b = samples[offset + 2]
        brightness = (r + g + b) / 3
        pixel_sum += brightness
        pixel_sq_sum += brightness * brightness
        if r > 240 and g > 240 and b > 240:
            white_pixels += 1
        sampled += 1

    mean = pixel_sum / sampled
    variance = pixel_sq_sum / sampled - mean * mean
    stddev = variance ** 0.5
    white_ratio = white_pixels / sampled

    # 4. Near-uniform colour → logo, solid block, blank placeholder
    if stddev < _MIN_STDDEV:
        return False, f"near-uniform colour (stddev={stddev:.1f})"

    # 5. Mostly white with very little content → blank / whitespace image
    if white_ratio > (1.0 - _MIN_CONTENT_RATIO):
        return False, f"mostly white ({white_ratio*100:.0f}% white pixels)"

    return True, ""


def extract_figures(paper_id: str, pdf_path: str) -> list[dict]:
    """Extract real figures from the PDF, filtering out decorative non-content images."""
    cache_file = pathlib.Path(f"cache/{paper_id}_figures.json")
    if cache_file.exists():
        print("  (cached) Skipping figure extraction")
        return json.loads(cache_file.read_text())

    doc = fitz.open(pdf_path)
    out_dir = pathlib.Path(f"docs/assets/figures/{paper_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = []
    skipped = 0

    for page_num, page in enumerate(doc):
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)

            # Normalise to RGB before quality checks (JPEG needs 3 channels)
            if pix.n != 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)

            # v0.2: apply quality filter
            ok, reason = _is_quality_figure(pix)
            if not ok:
                skipped += 1
                continue

            fname = f"fig_p{page_num + 1}_{img_idx}.jpg"
            fpath = out_dir / fname
            pix.save(str(fpath), jpg_quality=_JPEG_QUALITY)
            caption = _find_caption(page)

            figures.append(
                {
                    "path": f"../../assets/figures/{paper_id}/{fname}",
                    "caption": caption,
                    "page": page_num + 1,
                    "figure_number": _parse_fig_num(caption),
                }
            )

    figures.sort(key=lambda f: f["figure_number"] or 99)
    print(f"  Extracted {len(figures)} figures from PDF ({skipped} decorative images skipped)")
    cache_file.write_text(json.dumps(figures))
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
