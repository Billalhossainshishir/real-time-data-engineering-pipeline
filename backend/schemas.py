from datetime import datetime
import re

from pydantic import BaseModel, Field, field_validator


class SensorEvent(BaseModel):
    device_id: str = Field(min_length=7, max_length=20)
    temperature: float = Field(ge=-60, le=100)
    humidity: float = Field(ge=0, le=100)
    energy_usage: float = Field(ge=0, le=100)
    timestamp: datetime

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        if not re.fullmatch(r"ROOM-\d{2}", value):
            raise ValueError("device_id must match ROOM-XX, for example ROOM-07")
        return value


class SimulationState(BaseModel):
    running: bool
    interval_seconds: float


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str
