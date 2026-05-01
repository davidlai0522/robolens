# pipeline/ingest.py
import arxiv
import fitz
import json
import pathlib


def ingest_arxiv(arxiv_id: str) -> dict:
    """Download a paper from arXiv and extract its text and metadata."""
    pathlib.Path("cache").mkdir(exist_ok=True)
    cache_json = pathlib.Path(f"cache/{arxiv_id}.json")
    if cache_json.exists():
        print("  (cached) Skipping ingest")
        return json.loads(cache_json.read_text())

    paper = next(arxiv.Client().results(arxiv.Search(id_list=[arxiv_id])))

    pdf_path = pathlib.Path(f"cache/{arxiv_id}.pdf")
    paper.download_pdf(filename=str(pdf_path))

    doc = fitz.open(str(pdf_path))
    full_text = "\n".join(page.get_text() for page in doc)

    data = {
        "id": arxiv_id,
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "abstract": paper.summary,
        "venue": str(paper.journal_ref or "arXiv preprint"),
        "year": paper.published.year,
        "pdf_path": str(pdf_path),
        "full_text": full_text,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "categories": list(paper.categories),
    }

    pathlib.Path(f"cache/{arxiv_id}.json").write_text(json.dumps(data, indent=2))
    return data


def ingest_pdf(pdf_path: str) -> dict:
    """Ingest a local PDF file without fetching arXiv metadata."""
    pdf_path = pathlib.Path(pdf_path)
    pathlib.Path("cache").mkdir(exist_ok=True)

    doc = fitz.open(str(pdf_path))
    full_text = "\n".join(page.get_text() for page in doc)

    # Derive a stable ID from the filename
    paper_id = pdf_path.stem

    # Try to pull a title from the first text block on the first page
    title = paper_id
    try:
        first_page_blocks = doc[0].get_text("blocks")
        if first_page_blocks:
            title = first_page_blocks[0][4].strip().replace("\n", " ")
    except Exception:
        pass

    data = {
        "id": paper_id,
        "title": title,
        "authors": [],
        "abstract": "",
        "venue": "Local PDF",
        "year": 0,
        "pdf_path": str(pdf_path),
        "full_text": full_text,
        "arxiv_url": "",
        "categories": [],
    }

    pathlib.Path(f"cache/{paper_id}.json").write_text(json.dumps(data, indent=2))
    return data
