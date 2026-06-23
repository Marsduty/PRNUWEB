from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import comparisons as comparisons_module
from app.api.routes import fingerprints as fingerprints_module
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.device import Device
from app.models.image import ImageRecord
from app.models.job import Job
from app.services import storage
from app.worker import tasks


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _png_bytes(size=(1024, 1024), color=(120, 130, 140)):
    image = Image.new("RGB", size, color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_external_comparison_uploads_images_and_dispatches_worker(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(
            {"bucket": bucket, "object_key": object_key, "data": data, "content_type": content_type}
        ),
    )
    monkeypatch.setattr(tasks.external_comparison_job, "delay", lambda job_id: dispatched.append(job_id))

    with TestClient(app) as client:
        response = client.post(
            "/comparisons/external",
            data={"task_name": "案件A-外来图像比对"},
            files=[
                ("image_a", ("a.png", _png_bytes(color=(10, 20, 30)), "image/png")),
                ("image_b", ("b.png", _png_bytes(color=(40, 50, 60)), "image/png")),
            ],
        )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert dispatched == [job_id]
    assert len(stored) == 2

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        images = db.query(ImageRecord).order_by(ImageRecord.id.asc()).all()

    assert job is not None
    assert job.status == "queued"
    assert job.payload["task_name"] == "案件A-外来图像比对"
    assert job.payload["image_a_id"] == images[0].id
    assert job.payload["image_b_id"] == images[1].id
    assert [image.kind for image in images] == ["external_a", "external_b"]
    assert all(image.width == 1024 and image.height == 1024 for image in images)


def test_external_comparison_accepts_different_original_dimensions_when_both_are_croppable(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(object_key),
    )
    monkeypatch.setattr(tasks.external_comparison_job, "delay", lambda job_id: dispatched.append(job_id))

    with TestClient(app) as client:
        response = client.post(
            "/comparisons/external",
            data={"task_name": "不同原始尺寸裁剪测试"},
            files=[
                ("image_a", ("a.png", _png_bytes(size=(1200, 1024), color=(10, 20, 30)), "image/png")),
                ("image_b", ("b.png", _png_bytes(size=(1024, 1300), color=(40, 50, 60)), "image/png")),
            ],
        )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert dispatched == [job_id]
    assert len(stored) == 2

    with SessionLocal() as db:
        images = db.query(ImageRecord).order_by(ImageRecord.id.asc()).all()

    assert [(image.width, image.height) for image in images] == [(1200, 1024), (1024, 1300)]


def test_external_comparison_rejects_images_smaller_than_crop_size(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(object_key),
    )
    monkeypatch.setattr(tasks.external_comparison_job, "delay", lambda job_id: dispatched.append(job_id))

    with TestClient(app) as client:
        response = client.post(
            "/comparisons/external",
            data={"task_name": "尺寸过小测试"},
            files=[
                ("image_a", ("a.png", _png_bytes(size=(1024, 1024), color=(10, 20, 30)), "image/png")),
                ("image_b", ("b.png", _png_bytes(size=(1000, 1024), color=(40, 50, 60)), "image/png")),
            ],
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "图像尺寸过小，最小边需要 >= 1024px"
    assert stored == []
    assert dispatched == []

    with SessionLocal() as db:
        assert db.query(Job).count() == 0
        assert db.query(ImageRecord).count() == 0


def test_build_fingerprint_uploads_reference_images_and_dispatches_worker(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(object_key),
    )
    monkeypatch.setattr(tasks.build_fingerprint_job, "delay", lambda job_id: dispatched.append(job_id))

    with SessionLocal() as db:
        device = Device(name="测试相机A", brand="Canon", model="A1")
        db.add(device)
        db.commit()
        device_id = device.id

    with TestClient(app) as client:
        response = client.post(
            "/fingerprints/build",
            data={"device_id": str(device_id)},
            files=[
                ("files", ("ref1.png", _png_bytes(color=(11, 22, 33)), "image/png")),
                ("files", ("ref2.png", _png_bytes(color=(44, 55, 66)), "image/png")),
            ],
        )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert dispatched == [job_id]
    assert len(stored) == 2

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        images = db.query(ImageRecord).order_by(ImageRecord.id.asc()).all()

    assert job is not None
    assert job.payload["device_id"] == device_id
    assert job.payload["image_ids"] == [image.id for image in images]
    assert [image.kind for image in images] == ["reference", "reference"]
    assert all(image.device_id == device_id for image in images)


def test_database_comparison_upload_stores_task_name(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(object_key),
    )
    monkeypatch.setattr(tasks.database_comparison_job, "delay", lambda job_id: dispatched.append(job_id))

    with TestClient(app) as client:
        response = client.post(
            "/comparisons/database",
            data={"task_name": "案件A-数据库比对"},
            files=[("file", ("query.png", _png_bytes(color=(20, 30, 40)), "image/png"))],
        )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert dispatched == [job_id]
    assert len(stored) == 1

    with SessionLocal() as db:
        job = db.get(Job, job_id)

    assert job is not None
    assert job.payload["task_name"] == "案件A-数据库比对"


def test_database_comparison_rejects_images_smaller_than_crop_size(monkeypatch):
    _reset_db()
    stored = []
    dispatched = []

    monkeypatch.setattr(storage, "ensure_buckets", lambda client=None: None)
    monkeypatch.setattr(
        storage,
        "put_bytes",
        lambda bucket, object_key, data, content_type="application/octet-stream": stored.append(object_key),
    )
    monkeypatch.setattr(tasks.database_comparison_job, "delay", lambda job_id: dispatched.append(job_id))

    with TestClient(app) as client:
        response = client.post(
            "/comparisons/database",
            data={"task_name": "小尺寸数据库比对"},
            files=[("file", ("query.png", _png_bytes(size=(1024, 800), color=(20, 30, 40)), "image/png"))],
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "图像尺寸过小，最小边需要 >= 1024px"
    assert stored == []
    assert dispatched == []

    with SessionLocal() as db:
        assert db.query(Job).count() == 0
        assert db.query(ImageRecord).count() == 0
