from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.device import Device
from app.models.fingerprint import Fingerprint
from app.models.image import ImageRecord
from app.models.job import Job
from app.services import storage
from app.worker import tasks


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_create_device_generates_name_and_stores_mac_address():
    _reset_db()

    with TestClient(app) as client:
        response = client.post(
            "/devices",
            json={
                "brand": "Redmi",
                "model": "K70",
                "mac_address": "AA:BB:CC:11:22:33",
                "notes": "现场录入",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"].startswith("Redmi-K70-")
    assert payload["brand"] == "Redmi"
    assert payload["model"] == "K70"
    assert payload["mac_address"] == "AA:BB:CC:11:22:33"


def test_device_update_regenerates_name_when_brand_or_model_changes():
    _reset_db()

    with SessionLocal() as db:
        device = Device(name="Redmi-K70-ABC123", brand="Redmi", model="K70")
        db.add(device)
        db.commit()
        device_id = device.id

    with TestClient(app) as client:
        response = client.patch(
            f"/devices/{device_id}",
            json={"brand": "Xiaomi", "model": "K70 Pro"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brand"] == "Xiaomi"
    assert payload["model"] == "K70 Pro"
    assert payload["name"].startswith("Xiaomi-K70Pro-")
    assert payload["name"] != "Redmi-K70-ABC123"


def test_fingerprint_list_detail_update_and_delete():
    _reset_db()

    with SessionLocal() as db:
        device = Device(name="Redmi-K70-ABC123", brand="Redmi", model="K70", mac_address="AA:BB")
        db.add(device)
        db.flush()
        fingerprint = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/devices/1/job-1.npy",
            image_count=2,
            height=8,
            width=8,
            enhancement_config={},
        )
        db.add(fingerprint)
        db.commit()
        fingerprint_id = fingerprint.id

    with TestClient(app) as client:
        list_response = client.get("/fingerprints")
        detail_response = client.get(f"/fingerprints/{fingerprint_id}")
        update_response = client.patch(
            f"/fingerprints/{fingerprint_id}",
            json={"brand": "Xiaomi", "model": "K70 Pro", "mac_address": "CC:DD", "notes": "已复核"},
        )
        delete_response = client.delete(f"/fingerprints/{fingerprint_id}")
        final_list_response = client.get("/fingerprints")

    assert list_response.status_code == 200
    assert list_response.json()[0]["device"]["mac_address"] == "AA:BB"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == fingerprint_id
    assert update_response.status_code == 200
    assert update_response.json()["device"]["brand"] == "Xiaomi"
    assert update_response.json()["device"]["model"] == "K70 Pro"
    assert update_response.json()["device"]["name"].startswith("Xiaomi-K70Pro-")
    assert update_response.json()["device"]["mac_address"] == "CC:DD"
    assert delete_response.status_code == 200
    assert final_list_response.json() == []


def test_rebuild_fingerprint_references_creates_replace_job(monkeypatch):
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

    image_data = np.full((1024, 1024, 3), 120, dtype=np.uint8)
    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(image_data).save(buffer, format="PNG")

    with SessionLocal() as db:
        device = Device(name="Redmi-K70-ABC123", brand="Redmi", model="K70")
        db.add(device)
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
        db.commit()
        fingerprint_id = fingerprint.id
        device_id = device.id

    with TestClient(app) as client:
        response = client.post(
            f"/fingerprints/{fingerprint_id}/references",
            files=[("files", ("new-ref.png", buffer.getvalue(), "image/png"))],
        )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert dispatched == [job_id]
    assert len(stored) == 1

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        image = db.query(ImageRecord).one()

    assert job.type == "rebuild_fingerprint"
    assert job.payload["device_id"] == device_id
    assert job.payload["replace_fingerprint_id"] == fingerprint_id
    assert job.payload["image_ids"] == [image.id]
