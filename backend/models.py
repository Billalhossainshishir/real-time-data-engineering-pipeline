from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    room_name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    energy_usage: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), index=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(20), default="High")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    device_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DeadLetterEvent(Base):
    __tablename__ = "dead_letter_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_payload: Mapped[str] = mapped_column(Text)
    error_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
