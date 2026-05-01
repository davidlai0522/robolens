#!/usr/bin/env python3
"""
JarvisForResearchers v1.0 — Local Web UI

Launch on the server:
  uv run uvicorn web.app:app --host 0.0.0.0 --port 7860

Then open in your local browser one of:
  A) Direct (server on LAN / VPN):
       http://<server-ip>:7860

  B) SSH tunnel (server only reachable via SSH):
       ssh -L 7860:localhost:7860 user@server
     Then open: http://localhost:7860
"""
import asyncio
import pathlib
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_VE_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_RUN_SCRIPT = _REPO_ROOT / "pipeline" / "run.py"

app = FastAPI(title="JarvisForResearchers UI")

_STATIC = pathlib.Path(__file__).parent / "static"
_STATIC.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# In-memory job store — survives for the lifetime of the server process
jobs: dict[str, dict] = {}


class SubmitRequest(BaseModel):
    arxiv_id: str = ""
    force: bool = False
    quantise: bool = False
    no_vision: bool = False
    digest: bool = False


def _python() -> str:
    return str(_VE_PYTHON) if _VE_PYTHON.exists() else sys.executable


def _run_job(job_id: str, cmd: list[str]) -> None:
    """Run the pipeline subprocess, capturing output line by line."""
    job = jobs[job_id]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        for line in proc.stdout:
            job["output"].append(line.rstrip())
        proc.wait()
        job["status"] = "done" if proc.returncode == 0 else "failed"
        # Parse the written post path from pipeline output
        for line in reversed(job["output"]):
            m = re.search(r"Written:\s+(\S+\.md)", line)
            if m:
                job["post_path"] = str(_REPO_ROOT / m.group(1))
                break
    except Exception as e:
        job["output"].append(f"ERROR: {e}")
        job["status"] = "failed"
    finally:
        job["finished"] = True


@app.post("/submit")
async def submit(req: SubmitRequest):
    if not req.digest and not req.arxiv_id.strip():
        raise HTTPException(400, "arxiv_id required")

    job_id = str(uuid.uuid4())[:8]
    label = "Weekly Digest" if req.digest else req.arxiv_id.strip()

    cmd = [_python(), str(_RUN_SCRIPT)]
    if req.digest:
        cmd.append("--digest")
    else:
        cmd += ["--arxiv", req.arxiv_id.strip()]
    if req.force:
        cmd.append("--force")
    if req.quantise:
        cmd.append("--quantise")
    if req.no_vision:
        cmd.append("--no-vision")

    jobs[job_id] = {
        "id": job_id,
        "label": label,
        "status": "running",
        "output": [],
        "finished": False,
        "post_path": None,
        "started_at": datetime.now().isoformat(),
    }
    threading.Thread(target=_run_job, args=(job_id, cmd), daemon=True).start()
    return {"job_id": job_id}


@app.get("/jobs")
async def list_jobs():
    return [
        {k: v for k, v in j.items() if k != "output"}
        for j in sorted(jobs.values(), key=lambda x: x["started_at"], reverse=True)
    ]


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    async def gen():
        job = jobs[job_id]
        sent = 0
        while True:
            while sent < len(job["output"]):
                # Escape newlines so each SSE message is a single line
                line = job["output"][sent].replace("\n", " ")
                yield f"data: {line}\n\n"
                sent += 1
            if job["finished"]:
                yield f"data: __DONE__{job['status']}\n\n"
                break
            await asyncio.sleep(0.15)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/preview/{job_id}")
async def preview(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    path = jobs[job_id].get("post_path")
    if not path or not pathlib.Path(path).exists():
        raise HTTPException(404, "Post not yet available")
    content = pathlib.Path(path).read_text(encoding="utf-8")
    # Strip YAML front-matter — the browser renders it as plain text otherwise
    if content.startswith("---"):
        parts = content.split("---", 2)
        content = parts[2].strip() if len(parts) >= 3 else content
    return JSONResponse({"content": content})


@app.delete("/remove/{arxiv_id}")
async def remove(arxiv_id: str):
    result = subprocess.run(
        [_python(), str(_RUN_SCRIPT), "--remove", arxiv_id],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return {
        "output": (result.stdout + result.stderr).strip(),
        "ok": result.returncode == 0,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    return (_STATIC / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    uvicorn.run("web.app:app", host="0.0.0.0", port=7860, reload=False)
