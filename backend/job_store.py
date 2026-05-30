"""Armazenamento thread-safe de jobs de simulação em memória."""
import uuid, threading
from typing import Dict, Optional
from backend.schemas import JobStatus


_lock = threading.Lock()
_jobs: Dict[str, JobStatus] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = JobStatus(job_id=job_id, status="pending")
    return job_id


def get_job(job_id: str) -> Optional[JobStatus]:
    with _lock:
        return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)


def list_jobs() -> list[JobStatus]:
    with _lock:
        return list(_jobs.values())
