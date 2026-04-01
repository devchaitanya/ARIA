import logging
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from src.orchestrator.graph import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="ARIA — Adaptive Review Intelligence Architecture", version="1.0.0")

jobs: dict = {}


class ReviewRequest(BaseModel):
    repo_url: str
    branch: str = "main"


@app.post("/api/review")
def submit_review(req: ReviewRequest):
    job_id = f"aria-{uuid.uuid4().hex[:8]}"
    try:
        state = run_pipeline(req.repo_url, req.branch)
        jobs[job_id] = state
        return {
            "job_id": job_id,
            "status": state.status,
            "health_score": state.report.get("health_score"),
            "total_findings": state.report.get("total_findings"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/review/{job_id}")
def get_review(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs[job_id]
    return {
        "job_id": job_id,
        "status": state.status,
        "report": state.report,
    }


@app.get("/api/review/{job_id}/report", response_class=HTMLResponse)
def get_report_html(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs[job_id]
    html = state.report.get("html", "<h1>Report not generated</h1>")
    return HTMLResponse(content=html)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ARIA"}
