from io import BytesIO
from types import SimpleNamespace

import numpy as np

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.comparison_result import ComparisonResult
from app.models.device import Device
from app.models.fingerprint import Fingerprint
from app.models.image import ImageRecord
from app.models.job import Job
from app.services import storage
from app.worker import tasks


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _fingerprint_bytes(array: np.ndarray) -> bytes:
    buf = BytesIO()
    np.save(buf, array)
    return buf.getvalue()


def test_external_comparison_worker_writes_result(monkeypatch):
    _reset_db()

    fake_prnu_service = SimpleNamespace(
        build_single_image_fingerprint=lambda data, output_size: np.ones((8, 8)),
        compare_external_images=lambda fp_a, fp_b, threshold: {
            "pce": 72.5,
            "ncc": 0.41,
            "peak_pos": [3, 4],
            "is_hit": True,
            "decision": "倾向认定图像 A 和图像 B 同源",
            "threshold": threshold,
        },
    )
    monkeypatch.setattr(storage, "get_bytes", lambda bucket, object_key: object_key.encode())
    monkeypatch.setattr(tasks, "prnu_service", fake_prnu_service, raising=False)

    with SessionLocal() as db:
        image_a = ImageRecord(kind="external_a", filename="a.png", object_key="external/a.png", content_type="image/png")
        image_b = ImageRecord(kind="external_b", filename="b.png", object_key="external/b.png", content_type="image/png")
        db.add_all([image_a, image_b])
        db.flush()
        job = Job(type="external_comparison", status="queued", payload={"image_a_id": image_a.id, "image_b_id": image_b.id})
        db.add(job)
        db.commit()
        job_id = job.id

    tasks.external_comparison_job(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        result = db.query(ComparisonResult).one()

    assert job.status == "succeeded"
    assert result.comparison_type == "external_comparison"
    assert result.image_a_id is not None
    assert result.image_b_id is not None
    assert result.pce == 72.5
    assert result.ncc == 0.41
    assert result.peak_row == 3
    assert result.peak_col == 4
    assert result.is_hit is True
    assert result.decision == "倾向认定图像 A 和图像 B 同源"


def test_database_comparison_worker_writes_ranked_candidates(monkeypatch):
    _reset_db()

    fake_prnu_service = SimpleNamespace(
        build_single_image_fingerprint=lambda data, output_size: np.ones((8, 8)),
        compare_with_database=lambda query_fingerprint, database_fingerprints, threshold: {
            "decision": "倾向认定设备指纹：测试相机A 与待检图像同源",
            "hits": [],
            "candidates": [
                {
                    "name": "测试相机A",
                    "rank": 1,
                    "pce": 81.2,
                    "ncc": 0.52,
                    "peak_pos": [1, 2],
                    "is_hit": True,
                    "decision": "倾向认定设备指纹：测试相机A 与待检图像同源",
                }
            ],
        },
    )
    monkeypatch.setattr(storage, "get_bytes", lambda bucket, object_key: _fingerprint_bytes(np.ones((8, 8))))
    monkeypatch.setattr(tasks, "prnu_service", fake_prnu_service, raising=False)

    with SessionLocal() as db:
        device = Device(name="测试相机A", brand="Canon", model="A1", mac_address="AA:BB")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([device, query])
        db.flush()
        fingerprint = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/device-a.npy",
            image_count=2,
            height=8,
            width=8,
            enhancement_config={},
        )
        db.add(fingerprint)
        db.flush()
        job = Job(type="database_comparison", status="queued", payload={"query_image_id": query.id})
        db.add(job)
        db.commit()
        job_id = job.id
        fingerprint_id = fingerprint.id
        device_id = device.id

    tasks.database_comparison_job(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        result = db.query(ComparisonResult).one()

    assert job.status == "succeeded"
    assert result.comparison_type == "database_comparison"
    assert result.query_image_id is not None
    assert result.candidate_device_id == device_id
    assert result.candidate_fingerprint_id == fingerprint_id
    assert result.rank == 1
    assert result.pce == 81.2
    assert result.is_hit is True
    assert result.decision == "倾向认定设备指纹：测试相机A 与待检图像同源"


def test_build_fingerprint_worker_creates_fingerprint_record(monkeypatch):
    _reset_db()
    stored = []

    fake_prnu_service = SimpleNamespace(build_device_fingerprint=lambda image_bytes_list, output_size: np.ones((8, 8)))
    monkeypatch.setattr(storage, "get_bytes", lambda bucket, object_key: object_key.encode())
    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(
            {"bucket": bucket, "object_key": object_key, "data": data, "content_type": content_type}
        ),
    )
    monkeypatch.setattr(tasks, "prnu_service", fake_prnu_service, raising=False)

    with SessionLocal() as db:
        device = Device(name="测试相机A")
        db.add(device)
        db.flush()
        image = ImageRecord(
            device_id=device.id,
            kind="reference",
            filename="ref.png",
            object_key="reference/ref.png",
            content_type="image/png",
        )
        db.add(image)
        db.flush()
        job = Job(type="build_fingerprint", status="queued", payload={"device_id": device.id, "image_ids": [image.id]})
        db.add(job)
        db.commit()
        job_id = job.id
        device_id = device.id

    tasks.build_fingerprint_job(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        fingerprint = db.query(Fingerprint).one()

    assert job.status == "succeeded"
    assert fingerprint.device_id == device_id
    assert fingerprint.image_count == 1
    assert fingerprint.height == 8
    assert fingerprint.width == 8
    assert stored[0]["object_key"].endswith(f"job-{job_id}.npy")


def test_build_fingerprint_worker_replaces_existing_fingerprint(monkeypatch):
    _reset_db()

    fake_prnu_service = SimpleNamespace(build_device_fingerprint=lambda image_bytes_list, output_size: np.ones((10, 10)))
    monkeypatch.setattr(storage, "get_bytes", lambda bucket, object_key: object_key.encode())
    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(storage, "put_bytes", lambda bucket, object_key, data, content_type="application/octet-stream": None)
    monkeypatch.setattr(tasks, "prnu_service", fake_prnu_service, raising=False)

    with SessionLocal() as db:
        device = Device(name="测试相机A")
        db.add(device)
        db.flush()
        image = ImageRecord(
            device_id=device.id,
            kind="reference",
            filename="ref-new.png",
            object_key="reference/ref-new.png",
            content_type="image/png",
        )
        db.add(image)
        db.flush()
        fingerprint = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/devices/1/job-old.npy",
            image_count=1,
            height=8,
            width=8,
            enhancement_config={},
        )
        db.add(fingerprint)
        db.flush()
        job = Job(
            type="rebuild_fingerprint",
            status="queued",
            payload={
                "device_id": device.id,
                "image_ids": [image.id],
                "replace_fingerprint_id": fingerprint.id,
            },
        )
        db.add(job)
        db.commit()
        job_id = job.id
        fingerprint_id = fingerprint.id

    tasks.build_fingerprint_job(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        fingerprints = db.query(Fingerprint).all()
        fingerprint = db.get(Fingerprint, fingerprint_id)

    assert job.status == "succeeded"
    assert len(fingerprints) == 1
    assert fingerprint.object_key.endswith(f"job-{job_id}.npy")
    assert fingerprint.image_count == 1
    assert fingerprint.height == 10
    assert fingerprint.width == 10
