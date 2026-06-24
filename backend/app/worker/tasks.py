from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import numpy as np

TZ = ZoneInfo("Asia/Shanghai")

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.comparison_result import ComparisonResult
from app.models.device import Device
from app.models.fingerprint import Fingerprint
from app.models.image import ImageRecord
from app.models.job import Job
from app.services import prnu_service, storage
from app.worker.celery_app import celery_app


def _mark_job(job_id: int, status: str, progress: str | None = None, error: str | None = None) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = status
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error = error
        if status == "running":
            job.started_at = datetime.now(TZ)
        if status in {"succeeded", "failed"}:
            job.finished_at = datetime.now(TZ)
        db.commit()


def _array_to_bytes(array: np.ndarray) -> bytes:
    buf = BytesIO()
    np.save(buf, array)
    return buf.getvalue()


def _array_from_bytes(data: bytes) -> np.ndarray:
    return np.load(BytesIO(data))


def _peak_row(result: dict) -> int | None:
    peak_pos = result.get("peak_pos")
    return int(peak_pos[0]) if peak_pos else None


def _peak_col(result: dict) -> int | None:
    peak_pos = result.get("peak_pos")
    return int(peak_pos[1]) if peak_pos else None


def _get_image(db, image_id: int | None) -> ImageRecord:
    if image_id is None:
        raise ValueError("任务 payload 缺少图像 ID")
    image = db.get(ImageRecord, int(image_id))
    if image is None:
        raise ValueError(f"图像记录不存在：{image_id}")
    return image


def _get_job(db, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError(f"任务不存在：{job_id}")
    return job


@celery_app.task(name="build_fingerprint_job")
def build_fingerprint_job(job_id: int) -> int:
    try:
        with SessionLocal() as db:
            job = _get_job(db, job_id)
            is_rebuild = job.type == "rebuild_fingerprint"
            job.status = "running"
            job.progress = "正在重构设备指纹" if is_rebuild else "正在构建设备指纹"
            job.started_at = datetime.now(TZ)
            db.commit()
            device_id = int(job.payload.get("device_id"))
            image_ids = [int(image_id) for image_id in job.payload.get("image_ids", [])]
            if not image_ids:
                raise ValueError("设备指纹构建任务缺少参考图像")

            images = [_get_image(db, image_id) for image_id in image_ids]
            image_bytes_list = [
                storage.get_bytes(settings.prnu_image_bucket, image.object_key)
                for image in images
            ]
            fingerprint_array = prnu_service.build_device_fingerprint(
                image_bytes_list,
                output_size=settings.prnu_image_size,
            )

            storage.ensure_buckets()
            object_key = storage.build_object_key("fingerprints/devices", device_id, f"job-{job_id}.npy")
            storage.put_bytes(
                settings.prnu_artifact_bucket,
                object_key,
                _array_to_bytes(fingerprint_array),
                "application/octet-stream",
            )

            enhancement_config = {"enh_list": list(getattr(prnu_service, "DEFAULT_ENHANCEMENT_CONFIG", ()))}
            replace_fingerprint_id = job.payload.get("replace_fingerprint_id")
            if replace_fingerprint_id is not None:
                fingerprint = db.get(Fingerprint, int(replace_fingerprint_id))
                if fingerprint is None:
                    raise ValueError(f"待替换指纹不存在：{replace_fingerprint_id}")
                fingerprint.device_id = device_id
                fingerprint.source_image_id = images[0].id
                fingerprint.object_key = object_key
                fingerprint.image_count = len(image_ids)
                fingerprint.height = int(fingerprint_array.shape[0])
                fingerprint.width = int(fingerprint_array.shape[1])
                fingerprint.enhancement_config = enhancement_config
            else:
                fingerprint = Fingerprint(
                    device_id=device_id,
                    source_image_id=images[0].id,
                    object_key=object_key,
                    image_count=len(image_ids),
                    height=int(fingerprint_array.shape[0]),
                    width=int(fingerprint_array.shape[1]),
                    enhancement_config=enhancement_config,
                )
                db.add(fingerprint)
            job.status = "succeeded"
            job.progress = "设备指纹重构已完成" if is_rebuild else "设备指纹任务已完成"
            job.finished_at = datetime.now(TZ)
            db.commit()
        return job_id
    except Exception as exc:
        _mark_job(job_id, "failed", "设备指纹任务失败", str(exc))
        raise


@celery_app.task(name="database_comparison_job")
def database_comparison_job(job_id: int) -> int:
    try:
        _mark_job(job_id, "running", "正在执行指纹数据库比对")
        with SessionLocal() as db:
            job = _get_job(db, job_id)
            query_image = _get_image(db, job.payload.get("query_image_id"))
            query_bytes = storage.get_bytes(settings.prnu_image_bucket, query_image.object_key)
            query_fingerprint = prnu_service.build_single_image_fingerprint(
                query_bytes,
                output_size=settings.prnu_image_size,
            )

            fingerprints = db.query(Fingerprint).order_by(Fingerprint.created_at.desc()).all()
            references: dict[str, np.ndarray] = {}
            meta_by_name: dict[str, Fingerprint] = {}
            for fingerprint in fingerprints:
                device = db.get(Device, fingerprint.device_id) if fingerprint.device_id else None
                base_name = device.name if device is not None else f"指纹{fingerprint.id}"
                name = base_name if base_name not in references else f"{base_name}#{fingerprint.id}"
                reference_bytes = storage.get_bytes(settings.prnu_artifact_bucket, fingerprint.object_key)
                references[name] = _array_from_bytes(reference_bytes)
                meta_by_name[name] = fingerprint

            if references:
                comparison = prnu_service.compare_with_database(
                    query_fingerprint,
                    references,
                    threshold=settings.pce_threshold,
                )
                candidates = comparison["candidates"]
                decision = comparison["decision"]
            else:
                candidates = []
                decision = "库中未检索到匹配设备"

            if not candidates:
                db.add(
                    ComparisonResult(
                        job_id=job.id,
                        comparison_type="database_comparison",
                        query_image_id=query_image.id,
                        is_hit=False,
                        decision=decision,
                    )
                )
            for candidate in candidates:
                fingerprint = meta_by_name.get(str(candidate.get("name")))
                device_id = fingerprint.device_id if fingerprint is not None else None
                db.add(
                    ComparisonResult(
                        job_id=job.id,
                        comparison_type="database_comparison",
                        query_image_id=query_image.id,
                        candidate_device_id=device_id,
                        candidate_fingerprint_id=fingerprint.id if fingerprint is not None else None,
                        rank=int(candidate.get("rank") or 0) or None,
                        ncc=float(candidate["ncc"]) if candidate.get("ncc") is not None else None,
                        pce=float(candidate["pce"]) if candidate.get("pce") is not None else None,
                        peak_row=_peak_row(candidate),
                        peak_col=_peak_col(candidate),
                        is_hit=bool(candidate.get("is_hit", False)),
                        decision=str(candidate.get("decision") or decision),
                    )
                )

            job.status = "succeeded"
            hit_count = sum(1 for candidate in candidates if candidate.get("is_hit"))
            job.progress = f"PCE 命中 {hit_count} 个候选" if hit_count > 0 else "库中未检索到匹配设备"
            job.finished_at = datetime.now(TZ)
            db.commit()
        return job_id
    except Exception as exc:
        _mark_job(job_id, "failed", "指纹数据库比对失败", str(exc))
        raise


@celery_app.task(name="external_comparison_job")
def external_comparison_job(job_id: int) -> int:
    try:
        _mark_job(job_id, "running", "正在执行外来图像比对")
        with SessionLocal() as db:
            job = _get_job(db, job_id)
            image_a = _get_image(db, job.payload.get("image_a_id"))
            image_b = _get_image(db, job.payload.get("image_b_id"))
            image_a_bytes = storage.get_bytes(settings.prnu_image_bucket, image_a.object_key)
            image_b_bytes = storage.get_bytes(settings.prnu_image_bucket, image_b.object_key)
            fingerprint_a = prnu_service.build_single_image_fingerprint(
                image_a_bytes,
                output_size=settings.prnu_image_size,
            )
            fingerprint_b = prnu_service.build_single_image_fingerprint(
                image_b_bytes,
                output_size=settings.prnu_image_size,
            )
            comparison = prnu_service.compare_external_images(
                fingerprint_a,
                fingerprint_b,
                threshold=settings.pce_threshold,
            )

            db.add(
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="external_comparison",
                    image_a_id=image_a.id,
                    image_b_id=image_b.id,
                    rank=1,
                    ncc=float(comparison["ncc"]) if comparison.get("ncc") is not None else None,
                    pce=float(comparison["pce"]) if comparison.get("pce") is not None else None,
                    peak_row=_peak_row(comparison),
                    peak_col=_peak_col(comparison),
                    is_hit=bool(comparison.get("is_hit", False)),
                    decision=comparison["decision"],
                )
            )
            job.status = "succeeded"
            job.progress = "外来图像比对已完成"
            job.finished_at = datetime.now(TZ)
            db.commit()
        return job_id
    except Exception as exc:
        _mark_job(job_id, "failed", "外来图像比对失败", str(exc))
        raise
