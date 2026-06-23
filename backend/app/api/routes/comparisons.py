from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.comparison_result import ComparisonResult
from app.models.image import ImageRecord
from app.models.job import Job
from app.api.routes.serializers import comparison_decision, device_to_summary, fingerprint_to_summary, visible_comparison_rows
from app.services import storage
from app.services.image_preprocess import inspect_image_dimensions
from app.worker import tasks

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


def _clean_task_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


async def _read_upload_image(upload: UploadFile) -> tuple[bytes, int, int]:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传图像为空")

    try:
        width, height = inspect_image_dimensions(data, min_size=settings.prnu_image_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return data, width, height


def _store_upload_data(
    upload: UploadFile,
    data: bytes,
    width: int,
    height: int,
    db: Session,
    *,
    job_id: int,
    slot: str,
    kind: str,
    device_id: int | None = None,
) -> ImageRecord:
    filename = upload.filename or f"{slot}.jpg"
    object_key = storage.build_object_key("comparisons", f"{job_id}/{slot}", filename)
    storage.put_bytes(settings.prnu_image_bucket, object_key, data, upload.content_type or "application/octet-stream")

    image = ImageRecord(
        device_id=device_id,
        kind=kind,
        filename=filename,
        object_key=object_key,
        content_type=upload.content_type,
        width=width,
        height=height,
    )
    db.add(image)
    db.flush()
    return image


async def _store_upload(
    upload: UploadFile,
    db: Session,
    *,
    job_id: int,
    slot: str,
    kind: str,
    device_id: int | None = None,
) -> ImageRecord:
    data, width, height = await _read_upload_image(upload)
    return _store_upload_data(
        upload,
        data,
        width,
        height,
        db,
        job_id=job_id,
        slot=slot,
        kind=kind,
        device_id=device_id,
    )


@router.post("/database")
async def database_comparison(
    file: UploadFile = File(...),
    task_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    storage.ensure_buckets()
    job = Job(
        type="database_comparison",
        status="queued",
        progress="指纹数据库比对任务已入队",
        payload={"filename": file.filename, "task_name": _clean_task_name(task_name)},
    )
    db.add(job)
    db.flush()
    query_image = await _store_upload(file, db, job_id=job.id, slot="database-query", kind="query")
    job.payload = {
        "filename": file.filename,
        "task_name": _clean_task_name(task_name),
        "query_image_id": query_image.id,
        "query_object_key": query_image.object_key,
    }
    db.commit()
    db.refresh(job)
    tasks.database_comparison_job.delay(job.id)
    return {"job_id": job.id, "status": job.status}


@router.post("/external")
async def external_comparison(
    image_a: UploadFile = File(...),
    image_b: UploadFile = File(...),
    task_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    image_a_data, image_a_width, image_a_height = await _read_upload_image(image_a)
    image_b_data, image_b_width, image_b_height = await _read_upload_image(image_b)

    storage.ensure_buckets()
    job = Job(
        type="external_comparison",
        status="queued",
        progress="外来图像比对任务已入队",
        payload={"image_a": image_a.filename, "image_b": image_b.filename, "task_name": _clean_task_name(task_name)},
    )
    db.add(job)
    db.flush()
    image_a_record = _store_upload_data(
        image_a,
        image_a_data,
        image_a_width,
        image_a_height,
        db,
        job_id=job.id,
        slot="external-a",
        kind="external_a",
    )
    image_b_record = _store_upload_data(
        image_b,
        image_b_data,
        image_b_width,
        image_b_height,
        db,
        job_id=job.id,
        slot="external-b",
        kind="external_b",
    )
    job.payload = {
        "image_a": image_a.filename,
        "image_b": image_b.filename,
        "task_name": _clean_task_name(task_name),
        "image_a_id": image_a_record.id,
        "image_b_id": image_b_record.id,
        "image_a_object_key": image_a_record.object_key,
        "image_b_object_key": image_b_record.object_key,
    }
    db.commit()
    db.refresh(job)
    tasks.external_comparison_job.delay(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/{job_id}")
def get_comparison(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    rows = db.query(ComparisonResult).filter(ComparisonResult.job_id == job_id).order_by(ComparisonResult.rank.asc()).all()
    visible_rows = visible_comparison_rows(rows)
    top_row = visible_rows[0] if visible_rows else None
    return {
        "job_id": job.id,
        "status": job.status,
        "decision": comparison_decision(top_row) if top_row is not None else None,
        "results": [
            {
                "rank": row.rank,
                "pce": row.pce,
                "ncc": row.ncc,
                "is_hit": row.is_hit,
                "decision": comparison_decision(row),
                "peak_row": row.peak_row,
                "peak_col": row.peak_col,
                "device": device_to_summary(row.candidate_device),
                "fingerprint": fingerprint_to_summary(row.candidate_fingerprint),
            }
            for row in visible_rows
        ],
    }
