from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.device import Device
from app.models.job import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _device_name_for_job(job: Job, db: Session) -> str | None:
    device_id = (job.payload or {}).get("device_id")
    if device_id is None:
        return None
    device = db.get(Device, int(device_id))
    return device.name if device is not None else None


def _job_to_dict(job: Job, db: Session):
    payload = job.payload or {}
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "payload": job.payload,
        "task_name": payload.get("task_name"),
        "device_name": _device_name_for_job(job, db),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.get("")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
    return [_job_to_dict(job, db) for job in jobs]


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _job_to_dict(job, db)
