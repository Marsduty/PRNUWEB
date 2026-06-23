from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.device import Device
from app.models.job import Job


def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_jobs_include_task_name_and_device_name():
    _reset_db()

    with SessionLocal() as db:
        device = Device(name="测试设备A", brand="Canon", model="A1")
        db.add(device)
        db.flush()
        build_job = Job(
            type="build_fingerprint",
            status="queued",
            progress="设备指纹构建任务已入队",
            payload={"device_id": device.id},
        )
        compare_job = Job(
            type="database_comparison",
            status="queued",
            progress="指纹数据库比对任务已入队",
            payload={"task_name": "案件A-数据库比对"},
        )
        db.add_all([build_job, compare_job])
        db.commit()
        build_job_id = build_job.id
        compare_job_id = compare_job.id

    with TestClient(app) as client:
        response = client.get("/jobs")

    assert response.status_code == 200
    payload = response.json()
    build_row = next(row for row in payload if row["id"] == build_job_id)
    compare_row = next(row for row in payload if row["id"] == compare_job_id)
    assert build_row["device_name"] == "测试设备A"
    assert build_row["task_name"] is None
    assert compare_row["task_name"] == "案件A-数据库比对"
    assert compare_row["device_name"] is None
