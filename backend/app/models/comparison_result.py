from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TZ = ZoneInfo("Asia/Shanghai")


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(40), nullable=False)
    query_image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    image_a_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    image_b_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    candidate_device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    candidate_fingerprint_id: Mapped[int | None] = mapped_column(ForeignKey("fingerprints.id"), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ncc: Mapped[float | None] = mapped_column(Float, nullable=True)
    pce: Mapped[float | None] = mapped_column(Float, nullable=True)
    peak_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peak_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(TZ), nullable=False)

    job = relationship("Job", back_populates="comparison_results")
    candidate_device = relationship("Device", foreign_keys=[candidate_device_id])
    candidate_fingerprint = relationship("Fingerprint", foreign_keys=[candidate_fingerprint_id])
