from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    source_image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    enhancement_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    device = relationship("Device", back_populates="fingerprints")
    source_image = relationship("ImageRecord", back_populates="fingerprints")
