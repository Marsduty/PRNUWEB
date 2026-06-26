from datetime import date, datetime, time, timedelta

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


def test_metrics_summary_counts_fingerprints_and_groups_by_brand():
    _reset_db()

    with SessionLocal() as db:
        device_a = Device(name="Canon-EOS5D-ABC123", brand="Canon", model="EOS 5D")
        device_b = Device(name="Redmi-K70-DEF456", brand="Redmi", model="K70")
        db.add_all([device_a, device_b])
        db.flush()
        image = ImageRecord(
            device_id=device_a.id,
            kind="reference",
            filename="ref.png",
            object_key="references/ref.png",
            content_type="image/png",
        )
        fingerprint = Fingerprint(
            device_id=device_a.id,
            object_key="fingerprints/device-a.npy",
            image_count=1,
            height=8,
            width=8,
            enhancement_config={},
        )
        job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 1 个候选")
        db.add_all([image, fingerprint, job])
        db.flush()
        db.add(
            ComparisonResult(
                job_id=job.id,
                comparison_type="database_comparison",
                query_image_id=image.id,
                candidate_device_id=device_a.id,
                candidate_fingerprint_id=fingerprint.id,
                rank=1,
                pce=81.2,
                is_hit=True,
                decision="倾向认定设备指纹：Canon-EOS5D-ABC123 与待检图像同源",
            )
        )
        device_a_id = device_a.id
        db.commit()

    with TestClient(app) as client:
        response = client.get("/metrics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["image_count"] == 1
    assert payload["today_uploads"] == 1
    assert payload["device_distribution"] == [{"name": "Canon", "value": 1}]
    assert payload["recent_results"][0]["decision"] == "倾向认定设备指纹：Canon-EOS5D-ABC123 与待检图像同源"
    assert payload["recent_results"][0]["pce"] == 81.2
    assert payload["recent_results"][0]["device"] == {
        "id": device_a_id,
        "name": "Canon-EOS5D-ABC123",
        "brand": "Canon",
        "model": "EOS 5D",
        "mac_address": None,
    }


def test_metrics_summary_recent_database_results_keep_only_hits_or_best_candidate():
    _reset_db()

    with SessionLocal() as db:
        hit_device = Device(name="Hit-Camera", brand="Canon", model="A1")
        miss_device = Device(name="Miss-Camera", brand="Sony", model="B1")
        best_device = Device(name="Best-Camera", brand="Nikon", model="C1")
        weak_device = Device(name="Weak-Camera", brand="Apple", model="D1")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([hit_device, miss_device, best_device, weak_device, query])
        db.flush()
        hit_job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 1 个候选")
        no_hit_job = Job(type="database_comparison", status="succeeded", progress="库中未检索到匹配设备")
        db.add_all([hit_job, no_hit_job])
        db.flush()
        db.add_all(
            [
                ComparisonResult(
                    job_id=hit_job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=hit_device.id,
                    rank=1,
                    pce=91.0,
                    is_hit=True,
                    decision="倾向认定设备指纹：Hit-Camera 与待检图像同源",
                ),
                ComparisonResult(
                    job_id=hit_job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=miss_device.id,
                    rank=2,
                    pce=42.0,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
                ComparisonResult(
                    job_id=no_hit_job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=weak_device.id,
                    rank=1,
                    pce=11.0,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
                ComparisonResult(
                    job_id=no_hit_job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=best_device.id,
                    rank=2,
                    pce=57.0,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                ),
            ]
        )
        db.commit()

    with TestClient(app) as client:
        response = client.get("/metrics/summary")

    assert response.status_code == 200
    results = response.json()["recent_results"]
    device_names = [row["device"]["name"] for row in results if row["comparison_type"] == "database_comparison"]
    assert "Hit-Camera" in device_names
    assert "Best-Camera" in device_names
    assert "Miss-Camera" not in device_names
    assert "Weak-Camera" not in device_names


def test_metrics_summary_recent_results_do_not_drop_rank_one_hit_when_many_candidates():
    _reset_db()

    with SessionLocal() as db:
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add(query)
        db.flush()
        job = Job(type="database_comparison", status="succeeded", progress="PCE 命中 1 个候选")
        db.add(job)
        db.flush()

        hit_device = Device(name="Hit-Camera", brand="Canon", model="A1")
        hit_fingerprint = Fingerprint(
            device_id=None,
            object_key="fingerprints/hit.npy",
            image_count=10,
            height=1024,
            width=1024,
            enhancement_config={},
        )
        db.add_all([hit_device, hit_fingerprint])
        db.flush()
        hit_fingerprint.device_id = hit_device.id
        db.add(
            ComparisonResult(
                job_id=job.id,
                comparison_type="database_comparison",
                query_image_id=query.id,
                candidate_device_id=hit_device.id,
                candidate_fingerprint_id=hit_fingerprint.id,
                rank=1,
                pce=235.6,
                is_hit=True,
                decision="倾向认定设备指纹：Hit-Camera 与待检图像同源",
            )
        )

        for index in range(2, 107):
            device = Device(name=f"Miss-Camera-{index}", brand="Miss", model=str(index))
            fingerprint = Fingerprint(
                device_id=None,
                object_key=f"fingerprints/miss-{index}.npy",
                image_count=10,
                height=1024,
                width=1024,
                enhancement_config={},
            )
            db.add_all([device, fingerprint])
            db.flush()
            fingerprint.device_id = device.id
            db.add(
                ComparisonResult(
                    job_id=job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    candidate_device_id=device.id,
                    candidate_fingerprint_id=fingerprint.id,
                    rank=index,
                    pce=40.0 - index / 100,
                    is_hit=False,
                    decision="库中未检索到匹配设备",
                )
            )
        db.commit()

    with TestClient(app) as client:
        response = client.get("/metrics/summary")

    assert response.status_code == 200
    results = response.json()["recent_results"]
    assert len(results) == 1
    assert results[0]["is_hit"] is True
    assert results[0]["decision"] == "倾向认定设备指纹：Hit-Camera 与待检图像同源"
    assert results[0]["pce"] == 235.6


def test_metrics_summary_includes_yesterday_percent_changes():
    _reset_db()

    today_start = datetime.combine(date.today(), time.min)
    yesterday_start = today_start - timedelta(days=1)

    with SessionLocal() as db:
        device = Device(name="Trend-Camera", brand="Trend", model="T1")
        query = ImageRecord(kind="query", filename="q.png", object_key="query/q.png", content_type="image/png")
        db.add_all([device, query])
        db.flush()
        yesterday_fingerprint = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/yesterday.npy",
            image_count=1,
            height=8,
            width=8,
            enhancement_config={},
            created_at=yesterday_start + timedelta(hours=1),
        )
        today_fingerprint_a = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/today-a.npy",
            image_count=1,
            height=8,
            width=8,
            enhancement_config={},
            created_at=today_start + timedelta(hours=1),
        )
        today_fingerprint_b = Fingerprint(
            device_id=device.id,
            object_key="fingerprints/today-b.npy",
            image_count=1,
            height=8,
            width=8,
            enhancement_config={},
            created_at=today_start + timedelta(hours=2),
        )
        yesterday_job_a = Job(type="database_comparison", status="succeeded", created_at=yesterday_start + timedelta(hours=1))
        yesterday_job_b = Job(type="external_comparison", status="succeeded", created_at=yesterday_start + timedelta(hours=2))
        yesterday_build_job = Job(type="build_fingerprint", status="succeeded", created_at=yesterday_start + timedelta(hours=3))
        yesterday_rebuild_job = Job(type="rebuild_fingerprint", status="succeeded", created_at=yesterday_start + timedelta(hours=4))
        today_job = Job(type="database_comparison", status="succeeded", created_at=today_start + timedelta(hours=1))
        today_build_job = Job(type="build_fingerprint", status="succeeded", created_at=today_start + timedelta(hours=2))
        db.add_all(
            [
                yesterday_fingerprint,
                today_fingerprint_a,
                today_fingerprint_b,
                yesterday_job_a,
                yesterday_job_b,
                yesterday_build_job,
                yesterday_rebuild_job,
                today_job,
                today_build_job,
            ]
        )
        db.flush()
        db.add_all(
            [
                ComparisonResult(
                    job_id=yesterday_job_a.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    is_hit=True,
                    decision="昨日命中A",
                    created_at=yesterday_start + timedelta(hours=1),
                ),
                ComparisonResult(
                    job_id=yesterday_job_b.id,
                    comparison_type="external_comparison",
                    image_a_id=query.id,
                    image_b_id=query.id,
                    is_hit=True,
                    decision="昨日命中B",
                    created_at=yesterday_start + timedelta(hours=2),
                ),
                ComparisonResult(
                    job_id=today_job.id,
                    comparison_type="database_comparison",
                    query_image_id=query.id,
                    is_hit=True,
                    decision="今日命中",
                    created_at=today_start + timedelta(hours=1),
                ),
            ]
        )
        db.commit()

    with TestClient(app) as client:
        response = client.get("/metrics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["today_comparisons"] == 1
    trends = payload["metric_trends"]
    assert trends["image_count"] == {"previous": 1, "percent_change": 200.0}
    assert trends["today_uploads"] == {"previous": 1, "percent_change": 100.0}
    assert trends["today_comparisons"] == {"previous": 2, "percent_change": -50.0}
    assert trends["today_hits"] == {"previous": 2, "percent_change": -50.0}
