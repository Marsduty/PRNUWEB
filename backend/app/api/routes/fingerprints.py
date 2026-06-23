from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.api.routes.devices import DeviceUpdate, apply_device_updates
from app.models.comparison_result import ComparisonResult
from app.models.device import Device
from app.models.fingerprint import Fingerprint
from app.models.image import ImageRecord
from app.models.job import Job
from app.services import storage
from app.services.image_preprocess import inspect_image_dimensions
from app.worker import tasks

router = APIRouter(prefix="/fingerprints", tags=["fingerprints"])


class FingerprintUpdate(BaseModel):
    brand: str | None = None
    model: str | None = None
    mac_address: str | None = None
    notes: str | None = None


def _device_to_dict(device: Device | None):
    if device is None:
        return None
    return {
        "id": device.id,
        "name": device.name,
        "brand": device.brand,
        "model": device.model,
        "mac_address": device.mac_address,
        "notes": device.notes,
        "created_at": device.created_at,
    }


def _fingerprint_to_dict(fingerprint: Fingerprint):
    return {
        "id": fingerprint.id,
        "device_id": fingerprint.device_id,
        "object_key": fingerprint.object_key,
        "image_count": fingerprint.image_count,
        "height": fingerprint.height,
        "width": fingerprint.width,
        "enhancement_config": fingerprint.enhancement_config,
        "created_at": fingerprint.created_at,
        "device": _device_to_dict(fingerprint.device),
    }


async def _store_reference_upload(upload: UploadFile, db: Session, *, job_id: int, device_id: int) -> ImageRecord:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传图像为空")

    try:
        width, height = inspect_image_dimensions(data, min_size=settings.prnu_image_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = upload.filename or "reference.jpg"
    object_key = storage.build_object_key("references", f"{device_id}/{job_id}", filename)
    storage.put_bytes(settings.prnu_image_bucket, object_key, data, upload.content_type or "application/octet-stream")

    image = ImageRecord(
        device_id=device_id,
        kind="reference",
        filename=filename,
        object_key=object_key,
        content_type=upload.content_type,
        width=width,
        height=height,
    )
    db.add(image)
    db.flush()
    return image


async def _create_build_job(
    *,
    device_id: int,
    files: list[UploadFile],
    db: Session,
    replace_fingerprint_id: int | None = None,
) -> Job:
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张参考图像")

    storage.ensure_buckets()
    job_type = "rebuild_fingerprint" if replace_fingerprint_id is not None else "build_fingerprint"
    progress = "设备指纹重构任务已入队" if replace_fingerprint_id is not None else "设备指纹构建任务已入队"
    job = Job(
        type=job_type,
        status="queued",
        progress=progress,
        payload={"device_id": device_id, "file_count": len(files)},
    )
    db.add(job)
    db.flush()
    image_records = [
        await _store_reference_upload(upload, db, job_id=job.id, device_id=device_id)
        for upload in files
    ]
    job.payload = {
        "device_id": device_id,
        "file_count": len(files),
        "image_ids": [image.id for image in image_records],
        "image_object_keys": [image.object_key for image in image_records],
    }
    if replace_fingerprint_id is not None:
        job.payload["replace_fingerprint_id"] = replace_fingerprint_id
    db.commit()
    db.refresh(job)
    tasks.build_fingerprint_job.delay(job.id)
    return job


@router.get("")
def list_fingerprints(db: Session = Depends(get_db)):
    rows = db.query(Fingerprint).order_by(Fingerprint.created_at.desc()).all()
    return [_fingerprint_to_dict(row) for row in rows]


@router.post("/build")
async def build_fingerprint(
    device_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    job = await _create_build_job(device_id=device_id, files=files, db=db)
    return {"job_id": job.id, "status": job.status}


@router.post("/{fingerprint_id}/references")
async def rebuild_fingerprint_references(
    fingerprint_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    fingerprint = db.get(Fingerprint, fingerprint_id)
    if fingerprint is None:
        raise HTTPException(status_code=404, detail="指纹不存在")
    if fingerprint.device_id is None:
        raise HTTPException(status_code=400, detail="指纹未关联设备")
    job = await _create_build_job(
        device_id=fingerprint.device_id,
        files=files,
        db=db,
        replace_fingerprint_id=fingerprint.id,
    )
    return {"job_id": job.id, "status": job.status}


@router.get("/{fingerprint_id}")
def get_fingerprint(fingerprint_id: int, db: Session = Depends(get_db)):
    fingerprint = db.get(Fingerprint, fingerprint_id)
    if fingerprint is None:
        raise HTTPException(status_code=404, detail="指纹不存在")
    return _fingerprint_to_dict(fingerprint)


@router.patch("/{fingerprint_id}")
def update_fingerprint(fingerprint_id: int, payload: FingerprintUpdate, db: Session = Depends(get_db)):
    fingerprint = db.get(Fingerprint, fingerprint_id)
    if fingerprint is None:
        raise HTTPException(status_code=404, detail="指纹不存在")
    if fingerprint.device is None:
        raise HTTPException(status_code=400, detail="指纹未关联设备")

    apply_device_updates(
        fingerprint.device,
        DeviceUpdate(
            brand=payload.brand,
            model=payload.model,
            mac_address=payload.mac_address,
            notes=payload.notes,
        ),
    )
    db.commit()
    db.refresh(fingerprint)
    return _fingerprint_to_dict(fingerprint)


@router.delete("/{fingerprint_id}")
def delete_fingerprint(fingerprint_id: int, db: Session = Depends(get_db)):
    fingerprint = db.get(Fingerprint, fingerprint_id)
    if fingerprint is None:
        raise HTTPException(status_code=404, detail="指纹不存在")

    (
        db.query(ComparisonResult)
        .filter(ComparisonResult.candidate_fingerprint_id == fingerprint_id)
        .update({"candidate_fingerprint_id": None})
    )
    db.delete(fingerprint)
    db.commit()
    return {"deleted": True, "id": fingerprint_id}
