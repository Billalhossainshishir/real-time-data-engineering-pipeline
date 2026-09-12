import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine, get_db
from .models import Alert, DeadLetterEvent, Device, PipelineEvent, SensorReading
from .schemas import SensorEvent
from .simulator import INTERVAL, ROOMS, simulator

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Real-Time Data Engineering Pipeline", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def seed_devices(db: Session):
    existing = db.scalar(select(func.count()).select_from(Device)) or 0
    if existing == 0:
        for i, device_id in enumerate(ROOMS, start=1):
            db.add(Device(device_id=device_id, room_name=f"Room {i}"))
        db.commit()


@app.on_event("startup")
def startup_seed():
    with SessionLocal() as db:
        seed_devices(db)


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "service": "real-time-data-pipeline"}


def detect_rule_anomaly(event: SensorEvent) -> tuple[bool, str | None]:
    reasons = []
    if event.temperature > 35 or event.temperature < 10:
        reasons.append(f"temperature={event.temperature}C")
    if event.humidity > 85 or event.humidity < 15:
        reasons.append(f"humidity={event.humidity}%")
    if event.energy_usage > 7.5:
        reasons.append(f"energy_usage={event.energy_usage}")
    return (bool(reasons), ", ".join(reasons) if reasons else None)


def store_event(event: SensorEvent, db: Session) -> dict[str, Any]:
    device = db.scalar(select(Device).where(Device.device_id == event.device_id))
    if not device:
        raise HTTPException(status_code=422, detail="Unknown device_id")

    anomaly, reason = detect_rule_anomaly(event)
    reading = SensorReading(
        device_id=event.device_id,
        temperature=event.temperature,
        humidity=event.humidity,
        energy_usage=event.energy_usage,
        timestamp=event.timestamp.replace(tzinfo=None) if event.timestamp.tzinfo else event.timestamp,
        anomaly=anomaly,
        anomaly_reason=reason,
    )
    db.add(reading)
    db.add(PipelineEvent(event_type="INGESTED", device_id=event.device_id, message="Sensor event validated and stored"))

    if anomaly:
        db.add(Alert(
            device_id=event.device_id,
            alert_type="RULE_THRESHOLD",
            message=f"Abnormal reading detected: {reason}",
            severity="Critical" if event.temperature > 40 or event.energy_usage > 10 else "High",
        ))
        db.add(PipelineEvent(event_type="ALERT_CREATED", device_id=event.device_id, message=f"Alert created: {reason}"))

    db.commit()
    db.refresh(reading)
    return {"accepted": True, "reading_id": reading.id, "anomaly": anomaly, "anomaly_reason": reason}


@app.post("/events")
def ingest_event(event: SensorEvent, db: Session = Depends(get_db)):
    return store_event(event, db)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        raw = body.decode("utf-8", errors="replace") or "<empty body>"
    except Exception:
        raw = "<unavailable>"

    with SessionLocal() as db:
        db.add(DeadLetterEvent(original_payload=raw, error_reason=json.dumps(exc.errors(), default=str)))
        db.add(PipelineEvent(event_type="DEAD_LETTER", message="Invalid event rejected and stored in dead-letter table"))
        db.commit()
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "dead_lettered": True})


async def process_simulated_event(payload: dict):
    try:
        event = SensorEvent.model_validate(payload)
        with SessionLocal() as db:
            store_event(event, db)
    except Exception as exc:
        with SessionLocal() as db:
            db.add(DeadLetterEvent(original_payload=json.dumps(payload, default=str), error_reason=str(exc)))
            db.commit()


@app.post("/simulation/start")
async def start_simulation():
    await simulator.start(process_simulated_event)
    return {"running": simulator.running, "interval_seconds": INTERVAL}


@app.post("/simulation/pause")
async def pause_simulation():
    await simulator.pause()
    return {"running": simulator.running}


@app.post("/simulation/inject-anomaly")
def inject_anomaly():
    simulator.inject_anomaly()
    return {"queued": True, "message": "The next simulated event will contain an abnormal reading."}


@app.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    db.query(Alert).delete()
    db.query(SensorReading).delete()
    db.query(PipelineEvent).delete()
    db.query(DeadLetterEvent).delete()
    db.commit()
    return {"reset": True}


@app.get("/readings/latest")
def latest_readings(limit: int = 100, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = db.scalars(select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "temperature": r.temperature,
            "humidity": r.humidity,
            "energy_usage": r.energy_usage,
            "timestamp": r.timestamp.isoformat(),
            "anomaly": r.anomaly,
            "anomaly_reason": r.anomaly_reason,
        }
        for r in reversed(rows)
    ]


@app.get("/alerts")
def alerts(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": a.id,
            "device_id": a.device_id,
            "type": a.alert_type,
            "message": a.message,
            "severity": a.severity,
            "active": a.active,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


@app.get("/dead-letter")
def dead_letter(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(DeadLetterEvent).order_by(DeadLetterEvent.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "payload": r.original_payload,
            "error": r.error_reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@app.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    active_devices = db.scalar(select(func.count()).select_from(Device).where(Device.active.is_(True))) or 0
    total_events = db.scalar(select(func.count()).select_from(SensorReading)) or 0
    active_alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.active.is_(True))) or 0
    invalid_events = db.scalar(select(func.count()).select_from(DeadLetterEvent)) or 0
    avg_temp = db.scalar(select(func.avg(SensorReading.temperature)))
    avg_humidity = db.scalar(select(func.avg(SensorReading.humidity)))
    avg_energy = db.scalar(select(func.avg(SensorReading.energy_usage)))
    latest_ts = db.scalar(select(func.max(SensorReading.timestamp)))
    freshness_seconds = None
    if latest_ts:
        freshness_seconds = max(0, int((datetime.utcnow() - latest_ts).total_seconds()))
    return {
        "active_devices": active_devices,
        "events_stored": total_events,
        "active_alerts": active_alerts,
        "invalid_events": invalid_events,
        "average_temperature": round(float(avg_temp), 2) if avg_temp is not None else None,
        "average_humidity": round(float(avg_humidity), 2) if avg_humidity is not None else None,
        "average_energy": round(float(avg_energy), 2) if avg_energy is not None else None,
        "data_freshness_seconds": freshness_seconds,
        "pipeline_health": "RUNNING" if simulator.running else "PAUSED",
    }
