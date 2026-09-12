from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    room_name: Mapped[str] = mapped_column(String(100))
    floor: Mapped[int] = mapped_column(Integer, default=1)
    zone: Mapped[str] = mapped_column(String(50), default="General")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    energy_usage: Mapped[float] = mapped_column(Float)
    energy_watts: Mapped[float] = mapped_column(Float)
    temperature_band: Mapped[str] = mapped_column(String(30))
    humidity_band: Mapped[str] = mapped_column(String(30))
    energy_band: Mapped[str] = mapped_column(String(30))
    comfort_status: Mapped[str] = mapped_column(String(30))
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    anomaly: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    anomaly_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    anomaly_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="HTTP")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20), default="High")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage: Mapped[str] = mapped_column(String(50), default="INGESTION", index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    device_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="HTTP")
    message: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)


class DeadLetterEvent(Base):
    __tablename__ = "dead_letter_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_payload: Mapped[str] = mapped_column(Text)
    error_reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="HTTP")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
