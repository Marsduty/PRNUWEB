from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.device import Device
from app.models.job import Job


def test_can_create_device_and_job_in_sqlite_memory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        device = Device(name="设备A", brand="Canon", model="A1")
        job = Job(type="build_fingerprint", status="queued", progress="等待处理")
        session.add_all([device, job])
        session.commit()

        assert session.query(Device).count() == 1
        assert session.query(Job).count() == 1
