# pipeline/figures.py
import json
import fitz
import pathlib
import re

# Save as JPEG to keep the git repo small.
_JPEG_QUALITY = 85
# DPI used when rendering page regions — 150 gives crisp output at reasonable size
_RENDER_DPI = 150

# --- Quality filter thresholds ---
_MIN_WIDTH = 200
_MIN_HEIGHT = 150
_MAX_ASPECT_RATIO = 8.0
_MIN_STDDEV = 15.0
_MIN_CONTENT_RATIO = 0.05

# How far above a figure caption to look for the figure body (in PDF points, 1pt ≈ 0.35mm)
_CAPTION_LOOKBACK_PT = 480


def _render_region(page: fitz.Page, rect: fitz.Rect) -> fitz.Pixmap:
    """
    Render a rectangular region of *page* to an RGB pixmap via MuPDF's full
    rendering pipeline.  This correctly handles all colorspaces, soft masks,
    transparency, and vector/raster composites — avoiding the mal-transformation
    artefacts that occur when extracting raw image bytes.
    """
    zoom = _RENDER_DPI / 72
    mat = fitz.Matrix(zoom, zoom)
    return page.get_pixmap(matrix=mat, clip=rect, colorspace=fitz.csRGB)


def _is_quality_figure(pix: fitz.Pixmap) -> tuple[bool, str]:
    """Return (True, "") if the pixmap looks like a real figure."""
    w, h = pix.width, pix.height
    if w < _MIN_WIDTH or h < _MIN_HEIGHT:
        return False, f"too small ({w}×{h})"
    if w / h > _MAX_ASPECT_RATIO:
        return False, f"banner aspect ratio ({w/h:.1f})"

    n = pix.n  # 3 for RGB
    samples = pix.samples
    total_pixels = w * h
    step = max(1, total_pixels // 4000)
    pixel_sum = pixel_sq_sum = white_pixels = sampled = 0

    for i in range(0, total_pixels, step):
        offset = i * n
        r, g, b = samples[offset], samples[offset + 1], samples[offset + 2]
        brightness = (r + g + b) / 3
        pixel_sum += brightness
        pixel_sq_sum += brightness * brightness
        if r > 240 and g > 240 and b > 240:
            white_pixels += 1
        sampled += 1

    mean = pixel_sum / sampled
    stddev = (pixel_sq_sum / sampled - mean * mean) ** 0.5
    white_ratio = white_pixels / sampled

    if stddev < _MIN_STDDEV:
        return False, f"near-uniform colour (stddev={stddev:.1f})"
    if white_ratio > (1.0 - _MIN_CONTENT_RATIO):
        return False, f"mostly white ({white_ratio*100:.0f}%)"
    return True, ""


def _captions_on_page(page: fitz.Page) -> list[tuple[fitz.Rect, str]]:
    """Return (rect, text) for every figure-caption block on the page."""
    results = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
        text = text.strip()
        if re.match(r"^(Figure|Fig\.?)\s*\d+", text, re.IGNORECASE):
            results.append((fitz.Rect(x0, y0, x1, y1), text[:300]))
    return results


def _rects_overlap(a: fitz.Rect, b: fitz.Rect) -> bool:
    return not a.intersect(b).is_empty


def extract_figures(paper_id: str, pdf_path: str) -> list[dict]:
    """
    Extract figures from the PDF using two complementary strategies:

    1. Caption-driven region rendering — finds every "Figure N" caption, then
       renders the page region above it.  This captures architectural diagrams
       and other vector figures that don't exist as embedded raster objects.

    2. Raster image rendering — for raster images not already covered by a
       caption, renders the image's bounding box through MuPDF's pipeline
       (correct colorspace, masks, transforms) rather than extracting raw bytes.
    """
    cache_file = pathlib.Path(f"cache/{paper_id}_figures.json")
    if cache_file.exists():
        print("  (cached) Skipping figure extraction")
        return json.loads(cache_file.read_text())

    doc = fitz.open(pdf_path)
    out_dir = pathlib.Path(f"docs/assets/figures/{paper_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    figures: list[dict] = []
    skipped = 0
    captured_rects: list[fitz.Rect] = []  # track regions already saved

    for page_num, page in enumerate(doc):
        pr = page.rect
        captions = _captions_on_page(page)

        # ── Strategy 1: caption-driven region rendering ──────────────────────
        for cap_rect, cap_text in captions:
            # Region above the caption (where the figure body lives)
            top = max(pr.y0, cap_rect.y0 - _CAPTION_LOOKBACK_PT)
            fig_rect = fitz.Rect(pr.x0 + 20, top, pr.x1 - 20, cap_rect.y0 - 2)

            if fig_rect.is_empty or fig_rect.height < 80:
                continue
            if any(_rects_overlap(fig_rect, seen) for seen in captured_rects):
                continue

            pix = _render_region(page, fig_rect)
            ok, reason = _is_quality_figure(pix)
            if not ok:
                skipped += 1
                continue

            fig_num = _parse_fig_num(cap_text)
            fname = f"fig_p{page_num + 1}_c{fig_num or 'x'}.jpg"
            pix.save(str(out_dir / fname), jpg_quality=_JPEG_QUALITY)
            captured_rects.append(fig_rect)
            figures.append({
                "path": f"../assets/figures/{paper_id}/{fname}",
                "caption": cap_text,
                "page": page_num + 1,
                "figure_number": fig_num,
            })

        # ── Strategy 2: raster images not yet captured ───────────────────────
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                img_rects = page.get_image_rects(xref)
            except Exception:
                continue

            for img_rect in img_rects:
                if img_rect.is_empty:
                    continue
                if img_rect.width < _MIN_WIDTH or img_rect.height < _MIN_HEIGHT:
                    continue
                if any(_rects_overlap(img_rect, seen) for seen in captured_rects):
                    continue

                pix = _render_region(page, img_rect)
                ok, reason = _is_quality_figure(pix)
                if not ok:
                    skipped += 1
                    continue

                # Attach a nearby caption if one exists just below this image
                caption = next(
                    (t for r, t in captions if 0 <= r.y0 - img_rect.y1 < 60),
                    "",
                )
                fname = f"fig_p{page_num + 1}_r{xref}.jpg"
                pix.save(str(out_dir / fname), jpg_quality=_JPEG_QUALITY)
                captured_rects.append(img_rect)
                figures.append({
                    "path": f"../assets/figures/{paper_id}/{fname}",
                    "caption": caption,
                    "page": page_num + 1,
                    "figure_number": _parse_fig_num(caption),
                })

    figures.sort(key=lambda f: (f["page"], f["figure_number"] or 99))
    print(
        f"  Extracted {len(figures)} figures from PDF "
        f"({skipped} low-quality regions skipped)"
    )
    cache_file.write_text(json.dumps(figures))
    return figures


def select_blog_figures(figures: list[dict], max_figures: int = 4) -> list[dict]:
    """Pick the best figures to embed in the blog post."""
    captioned = [f for f in figures if f["caption"]]
    uncaptioned = [f for f in figures if not f["caption"]]
    pool = captioned if captioned else uncaptioned
    return pool[:max_figures]


def _parse_fig_num(caption: str) -> int | None:
    m = re.search(r"(?:Figure|Fig\.?)\s*(\d+)", caption, re.IGNORECASE)
    return int(m.group(1)) if m else None
