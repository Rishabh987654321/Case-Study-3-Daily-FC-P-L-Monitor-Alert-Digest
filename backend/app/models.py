"""SQLAlchemy ORM models matching docs/data_model.md."""

import uuid
from datetime import UTC
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _uuid() -> str:
    return str(uuid.uuid4())


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="processing")  # processing|completed|failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fc_count: Mapped[int] = mapped_column(Integer, default=0)
    day_count: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    fc_days: Mapped[list["FCDay"]] = relationship(back_populates="upload", cascade="all, delete-orphan")
    anomalies: Mapped[list["AnomalyRow"]] = relationship(back_populates="upload", cascade="all, delete-orphan")
    digests: Mapped[list["DigestRow"]] = relationship(back_populates="upload", cascade="all, delete-orphan")


class FCDay(Base):
    __tablename__ = "fc_days"
    __table_args__ = (
        Index("ix_fc_days_upload_fc_date", "upload_id", "fc_name", "date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"))
    fc_name: Mapped[str] = mapped_column(String)
    date: Mapped[date_type] = mapped_column(Date)

    revenue: Mapped[float] = mapped_column(Float)
    manpower_cost: Mapped[float] = mapped_column(Float)
    packaging_cost: Mapped[float] = mapped_column(Float)
    power_fuel: Mapped[float] = mapped_column(Float)
    fc_rent: Mapped[float] = mapped_column(Float)
    equipment_rentals: Mapped[float] = mapped_column(Float)
    overheads: Mapped[float] = mapped_column(Float)

    cm1: Mapped[float] = mapped_column(Float)
    cm1_pct: Mapped[float] = mapped_column(Float)
    cm2: Mapped[float] = mapped_column(Float)
    cm2_pct: Mapped[float] = mapped_column(Float)
    manpower_pct: Mapped[float] = mapped_column(Float)
    packaging_pct: Mapped[float] = mapped_column(Float)
    power_fuel_pct: Mapped[float] = mapped_column(Float)
    fc_rent_pct: Mapped[float] = mapped_column(Float)
    equipment_pct: Mapped[float] = mapped_column(Float)
    overheads_pct: Mapped[float] = mapped_column(Float)

    color_code: Mapped[str] = mapped_column(String)
    insight: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    upload: Mapped["Upload"] = relationship(back_populates="fc_days")


class AnomalyRow(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("ix_anomalies_upload_fc_date", "upload_id", "fc_name", "date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"))
    fc_day_id: Mapped[str | None] = mapped_column(ForeignKey("fc_days.id"), nullable=True)
    fc_name: Mapped[str] = mapped_column(String)
    date: Mapped[date_type] = mapped_column(Date)
    line_item: Mapped[str] = mapped_column(String)
    actual_pct: Mapped[float] = mapped_column(Float)
    target_min: Mapped[float] = mapped_column(Float)
    target_max: Mapped[float] = mapped_column(Float)
    deviation: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    upload: Mapped["Upload"] = relationship(back_populates="anomalies")


class DigestRow(Base):
    __tablename__ = "digests"
    __table_args__ = (
        Index("ix_digests_upload_fc_date", "upload_id", "fc_name", "date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"))
    fc_name: Mapped[str] = mapped_column(String)
    date: Mapped[date_type] = mapped_column(Date)
    color_code: Mapped[str] = mapped_column(String)
    summary_text: Mapped[str] = mapped_column(Text)
    html_content: Mapped[str] = mapped_column(Text)
    generation_mode: Mapped[str] = mapped_column(String, default="rule")
    delivered_via: Mapped[str | None] = mapped_column(String, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    upload: Mapped["Upload"] = relationship(back_populates="digests")
