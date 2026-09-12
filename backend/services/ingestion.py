import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, DeadLetterEvent, Device, PipelineEvent, SensorReading
from ..schemas import SensorEvent
from .anomaly_detection import detect_anomaly
from .transformations import transform_event


def record_pipeline_event(
    db: Session,
    *,
    stage: str,
    event_type: str,
    message: str,
    source: str,
    device_id: str | None = None,
) -> None:
    db.add(
        PipelineEvent(
            stage=stage,
            event_type=event_type,
            device_id=device_id,
            source=source,
            message=message,
        )
    )


def record_dead_letter(
    db: Session,
    payload: Any,
    error_reason: str,
    *,
    source: str,
) -> None:
    raw_payload = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    db.add(
        DeadLetterEvent(
            original_payload=raw_payload,
            error_reason=error_reason,
            source=source,
        )
    )
    record_pipeline_event(
        db,
        stage="VALIDATION",
        event_type="DEAD_LETTER",
        message="Invalid event rejected and isolated",
        source=source,
    )
    db.commit()


def process_sensor_event(
    event: SensorEvent,
    db: Session,
    *,
    source: str = "HTTP",
) -> dict[str, Any]:
    device = db.scalar(select(Device).where(Device.device_id == event.device_id))
    if not device:
        record_dead_letter(
            db,
            event.model_dump(mode="json"),
            f"Unknown device_id: {event.device_id}",
            source=source,
        )
        raise HTTPException(status_code=422, detail="Unknown device_id")

    record_pipeline_event(
        db,
        stage="INGESTION",
        event_type="INGESTED",
        device_id=event.device_id,
        source=source,
        message="Sensor event accepted for processing",
    )
    record_pipeline_event(
        db,
        stage="VALIDATION",
        event_type="VALIDATED",
        device_id=event.device_id,
        source=source,
        message="Schema and registered-device validation passed",
    )

    transformed = transform_event(event)
    record_pipeline_event(
        db,
        stage="TRANSFORMATION",
        event_type="TRANSFORMED",
        device_id=event.device_id,
        source=source,
        message=(
            f"Normalized timestamp; derived bands temp={transformed.temperature_band}, "
            f"humidity={transformed.humidity_band}, energy={transformed.energy_band}"
        ),
    )

    detection = detect_anomaly(db, event)
    reading = SensorReading(
        device_id=transformed.device_id,
        temperature=transformed.temperature,
        humidity=transformed.humidity,
        energy_usage=transformed.energy_usage,
        energy_watts=transformed.energy_watts,
        temperature_band=transformed.temperature_band,
        humidity_band=transformed.humidity_band,
        energy_band=transformed.energy_band,
        comfort_status=transformed.comfort_status,
        timestamp=transformed.timestamp_utc_naive,
        anomaly=detection.anomaly,
        anomaly_method=detection.method,
        anomaly_score=detection.score,
        anomaly_reason=detection.reason,
        source=source,
    )
    db.add(reading)
    record_pipeline_event(
        db,
        stage="STORAGE",
        event_type="STORED",
        device_id=event.device_id,
        source=source,
        message="Transformed reading persisted",
    )

    if detection.anomaly:
        db.add(
            Alert(
                device_id=event.device_id,
                alert_type=detection.method or "ANOMALY",
                message=detection.reason or "Anomalous reading detected",
                severity=detection.severity or "High",
            )
        )
        record_pipeline_event(
            db,
            stage="DETECTION",
            event_type="ALERT_CREATED",
            device_id=event.device_id,
            source=source,
            message=f"{detection.method} alert created",
        )

    db.commit()
    db.refresh(reading)

    return {
        "accepted": True,
        "reading_id": reading.id,
        "source": source,
        "transformation": {
            "energy_watts": reading.energy_watts,
            "temperature_band": reading.temperature_band,
            "humidity_band": reading.humidity_band,
            "energy_band": reading.energy_band,
            "comfort_status": reading.comfort_status,
        },
        "anomaly": reading.anomaly,
        "anomaly_method": reading.anomaly_method,
        "anomaly_score": reading.anomaly_score,
        "anomaly_reason": reading.anomaly_reason,
    }
