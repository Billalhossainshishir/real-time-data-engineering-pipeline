from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class SensorEvent(BaseModel):
    device_id: str = Field(min_length=4, max_length=50)
    temperature: float
    humidity: float
    energy_usage: float
    timestamp: datetime

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        if not re.fullmatch(r"ROOM-\d{2}", value):
            raise ValueError("device_id must match ROOM-XX, for example ROOM-07")
        return value

    @field_validator("humidity")
    @classmethod
    def validate_humidity(cls, value: float) -> float:
        if not 0 <= value <= 100:
            raise ValueError("humidity must be between 0 and 100")
        return value

    @field_validator("energy_usage")
    @classmethod
    def validate_energy(cls, value: float) -> float:
        if value < 0:
            raise ValueError("energy_usage cannot be negative")
        return value


class SimulationState(BaseModel):
    running: bool
    interval_seconds: float
