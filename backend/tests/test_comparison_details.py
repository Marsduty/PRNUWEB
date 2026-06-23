from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.comparison_result import ComparisonResult
from app.models.device import Device
from app.models.fingerprint import Fingerprint
from app.models.image import ImageRecord
from app.models.job import Job


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_comparison_detail_includes_candidate_device_and_fingerprint():
    _reset_db()

    with SessionLocal() as db:
        device = Device(name="Redmi-K70-ABC123", brand="Redmi", model="K70", mac_address="AA:BB:CC")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([device, query])
        db.flush()
        fingerprint = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/devices/1/job-1.npy",
            image_count=3,
            height=1024,
            width=1024,
            enhancement_config={},
        )
        db.add(fingerprint)
        db.flush()
        job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 1 个候选")
        db.add(job)
        db.flush()
        db.add(
            ComparisonResult(
                job_id=job.id,
                comparison_type="database_comparison",
                query_image_id=query.id,
                candidate_device_id=device.id,
                candidate_fingerprint_id=fingerprint.id,
                rank=1,
                pce=91.5,
                ncc=0.44,
                peak_row=8,
                peak_col=9,
                is_hit=True,
                decision="倾向认定设备指纹：Redmi-K70-ABC123 与待检图像同源",
            )
        )
        job_id = job.id
        device_id = device.id
        fingerprint_id = fingerprint.id
        db.commit()

    with TestClient(app) as client:
        response = client.get(f"/comparisons/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "倾向认定设备指纹：Redmi-K70-ABC123 与待检图像同源"
    result = payload["results"][0]
    assert result["device"] == {
        "id": device_id,
        "name": "Redmi-K70-ABC123",
        "brand": "Redmi",
        "model": "K70",
        "mac_address": "AA:BB:CC",
    }
    assert result["fingerprint"]["id"] == fingerprint_id
    assert result["fingerprint"]["image_count"] == 3


def test_comparison_detail_normalizes_legacy_database_decision_text():
    _reset_db()

    with SessionLocal() as db:
        device = Device(name="Redmi-K70-ABC123", brand="Redmi", model="K70")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([device, query])
        db.flush()
        job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 0 个候选")
        db.add(job)
        db.flush()
        db.add(
            ComparisonResult(
                job_id=job.id,
                comparison_type="database_comparison",
                query_image_id=query.id,
                candidate_device_id=device.id,
                rank=1,
                pce=20.1,
                is_hit=False,
                decision="倾向认定设备指纹 Redmi-K70-ABC123 / 图像 Redmi-K70-ABC123 与待检图像同源",
            )
        )
        job_id = job.id
        db.commit()

    with TestClient(app) as client:
        response = client.get(f"/comparisons/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "库中未检索到匹配设备"
    assert payload["results"][0]["decision"] == "库中未检索到匹配设备"


def test_database_comparison_detail_returns_only_hit_candidates_when_hits_exist():
    _reset_db()

    with SessionLocal() as db:
        hit_device = Device(name="Hit-Camera", brand="Canon", model="A1")
        miss_device = Device(name="Miss-Camera", brand="Sony", model="B1")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([hit_device, miss_device, query])
        db.flush()
        job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 1 个候选")
        db.add(job)
        db.flush()
        db.add_all(
            [
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=hit_device.id,
                    rank=1,
                    pce=92.1,
                    is_hit=True,
                    decision="倾向认定设备指纹：Hit-Camera 与待检图像同源",
                ),
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=miss_device.id,
                    rank=2,
                    pce=43.2,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
            ]
        )
        job_id = job.id
        db.commit()

    with TestClient(app) as client:
        response = client.get(f"/comparisons/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "倾向认定设备指纹：Hit-Camera 与待检图像同源"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["device"]["name"] == "Hit-Camera"
    assert payload["results"][0]["is_hit"] is True


def test_database_comparison_detail_returns_best_candidate_when_no_hits_exist():
    _reset_db()

    with SessionLocal() as db:
        weak_device = Device(name="Weak-Camera", brand="Canon", model="A1")
        best_device = Device(name="Best-Camera", brand="Sony", model="B1")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([weak_device, best_device, query])
        db.flush()
        job = Job(type="database_comparison", status="succeeded", progress="库中未检索到匹配设备")
        db.add(job)
        db.flush()
        db.add_all(
            [
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=weak_device.id,
                    rank=1,
                    pce=14.1,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=best_device.id,
                    rank=2,
                    pce=52.8,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
            ]
        )
        job_id = job.id
        db.commit()

    with TestClient(app) as client:
        response = client.get(f"/comparisons/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "库中未检索到匹配设备"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["device"]["name"] == "Best-Camera"
    assert payload["results"][0]["pce"] == 52.8
