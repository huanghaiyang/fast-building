"""生成任务接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import Footprint, GenerateResponse, JobView
from ..services.jobs import manager

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/generate", response_model=GenerateResponse)
def generate(footprint: Footprint) -> GenerateResponse:
    spec = footprint.model_dump()
    job = manager.submit(spec)
    return GenerateResponse(job_id=job.id)


@router.get("/jobs", response_model=list[JobView])
def list_jobs(limit: int = 20) -> list[dict]:
    return [job.to_dict() for job in manager.list(limit=max(1, min(limit, 100)))]


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job.to_dict()


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if manager.get(job_id) is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    ok = manager.cancel(job_id)
    return {"canceled": ok}
