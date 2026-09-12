from dataclasses import dataclass
from datetime import datetime, timezone

from ..schemas import SensorEvent


@dataclass(frozen=True)
class TransformedReading:
    device_id: str
    temperature: float
    humidity: float
    energy_usage: float
    energy_watts: float
    temperature_band: str
    humidity_band: str
    energy_band: str
    comfort_status: str
    timestamp_utc_naive: datetime


def _temperature_band(value: float) -> str:
    if value < 18:
        return "cold"
    if value <= 28:
        return "normal"
    if value <= 35:
        return "warm"
    return "critical"


def _humidity_band(value: float) -> str:
    if value < 30:
        return "dry"
    if value <= 70:
        return "normal"
    if value <= 85:
        return "humid"
    return "critical"


def _energy_band(value: float) -> str:
    if value <= 1:
        return "low"
    if value <= 3:
        return "normal"
    if value <= 5:
        return "high"
    return "very_high"


def transform_event(event: SensorEvent) -> TransformedReading:
    timestamp = event.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    temp_band = _temperature_band(event.temperature)
    humidity_band = _humidity_band(event.humidity)
    energy_band = _energy_band(event.energy_usage)
    comfort_status = (
        "comfortable"
        if 18 <= event.temperature <= 28 and 30 <= event.humidity <= 70
        else "review"
    )

    return TransformedReading(
        device_id=event.device_id,
        temperature=round(event.temperature, 2),
        humidity=round(event.humidity, 2),
        energy_usage=round(event.energy_usage, 3),
        energy_watts=round(event.energy_usage * 1000, 1),
        temperature_band=temp_band,
        humidity_band=humidity_band,
        energy_band=energy_band,
        comfort_status=comfort_status,
        timestamp_utc_naive=timestamp.replace(tzinfo=None),
    )
