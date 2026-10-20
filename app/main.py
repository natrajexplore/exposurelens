"""FastAPI server: upload configs -> background scan -> poll results."""
from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .advisories import AdvisoryHunter  # noqa: E402
from .llm import Ledger, NemotronRouter, TIER_MODELS, TIER_ROLES  # noqa: E402
from .pipeline import Pipeline  # noqa: E402
from .report import to_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "samples" / "configs"
MAX_FILES, MAX_BYTES = 6, 200_000
ACCESS_KEY = os.getenv("APP_ACCESS_KEY")  # optional: protects credits on a public demo

app = FastAPI(title="ExposureLens")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
JOBS: dict[str, dict] = {}


def _check(key: str | None):
    if ACCESS_KEY and key != ACCESS_KEY:
        raise HTTPException(401, "Invalid or missing access key")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {
        "nebius_key": bool(os.getenv("NEBIUS_API_KEY")),
        "tavily_key": bool(os.getenv("TAVILY_API_KEY")),
        "access_key_required": bool(ACCESS_KEY),
        "models": TIER_MODELS, "roles": TIER_ROLES,
    }


@app.get("/api/samples")
def samples():
    return {p.name: p.read_text() for p in sorted(SAMPLES.glob("*.txt"))}


def _run(job_id: str, configs: dict[str, str], focus: str | None):
    job = JOBS[job_id]

    def emit(stage, msg):
        job["events"].append({"t": round(time.time() - job["started"], 1), "stage": stage, "msg": msg})

    try:
        router = NemotronRouter(ledger=Ledger())
        result = Pipeline(router, AdvisoryHunter(), emit).run(configs, focus)
        job.update(status="done", result=result)
        emit("done", f"Scan complete in {result['elapsed_s']}s")
    except Exception as e:
        job.update(status="error", error=str(e))
        emit("error", str(e))


@app.post("/api/scan")
async def scan(files: list[UploadFile] = File(default=[]), use_samples: bool = Form(False),
               focus: str = Form(""), x_access_key: str | None = Header(default=None)):
    _check(x_access_key)
    if not os.getenv("NEBIUS_API_KEY"):
        raise HTTPException(503, "Server has no NEBIUS_API_KEY configured")
    configs: dict[str, str] = {}
    if use_samples:
        configs = samples()
    for f in files[:MAX_FILES]:
        raw = await f.read()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, f"{f.filename} is larger than {MAX_BYTES} bytes")
        configs[f.filename] = raw.decode("utf-8", errors="replace")
    if not configs:
        raise HTTPException(400, "Upload at least one config or choose the sample fleet")
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"status": "running", "events": [], "started": time.time()}
    threading.Thread(target=_run, args=(job_id, configs, focus.strip() or None), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/scan/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return {k: v for k, v in job.items() if k != "started"}


@app.get("/api/scan/{job_id}/report.md", response_class=PlainTextResponse)
def report(job_id: str):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "Report not ready")
    return to_markdown(job["result"])
