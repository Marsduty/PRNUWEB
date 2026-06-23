from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app import models  # noqa: F401


def ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    if "devices" not in inspector.get_table_names():
        return
    device_columns = {column["name"] for column in inspector.get_columns("devices")}
    if "mac_address" not in device_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE devices ADD COLUMN mac_address VARCHAR(80)"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    yield


app = FastAPI(title="PRNU 智能取证与比对分析平台", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
