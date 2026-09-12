import json
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .bootstrap import seed_devices
from .database import Base, SessionLocal, engine, get_db
from .models import Alert, DeadLetterEvent, Device, PipelineEvent, SensorReading
from .schemas import SensorEvent
from .services.ingestion import process_sensor_event, record_dead_letter
from .simulator import INTERVAL, simulator

ROOT_DIR = Path(__file__).resolve().parent.parent


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


ASSETS_DIR = ROOT_DIR / "assets"
INDEX_FILE = ROOT_DIR / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_devices(db)
    yield
    await simulator.pause()


app = FastAPI(
    title="Real-Time Data Engineering Pipeline",
    version="2.0.0",
    description=(
        "Portfolio backend for smart-building sensor ingestion, validation, transformation, "
        "PostgreSQL persistence, anomaly detection, analytics and MQTT worker processing."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/", include_in_schema=False)
def root():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return {"service": "real-time-data-pipeline", "docs": "/docs"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc
    return {
        "status": "ok",
        "service": "real-time-data-pipeline",
        "database": database_status,
        "version": "2.0.0",
    }


@app.post("/events")
def ingest_event(event: SensorEvent, db: Session = Depends(get_db)):
    return process_sensor_event(event, db, source="HTTP")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.body()
        raw = body.decode("utf-8", errors="replace") or "<empty body>"
    except Exception:
        raw = "<unavailable>"

    if request.url.path == "/events":
        with SessionLocal() as db:
            record_dead_letter(
                db,
                raw,
                json.dumps(exc.errors(), default=str),
                source="HTTP",
            )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "dead_lettered": True},
        )

    return JSONResponse(status_code=422, content={"detail": exc.errors()})


async def process_simulated_event(payload: dict[str, Any]):
    try:
        event = SensorEvent.model_validate(payload)
        with SessionLocal() as db:
            process_sensor_event(event, db, source="SIMULATOR")
    except Exception as exc:
        with SessionLocal() as db:
            record_dead_letter(db, payload, str(exc), source="SIMULATOR")


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
    return {
        "queued": True,
        "message": "The next simulated event will contain an abnormal reading.",
    }


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
    rows = db.scalars(
        select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "device_id": row.device_id,
            "temperature": row.temperature,
            "humidity": row.humidity,
            "energy_usage": row.energy_usage,
            "energy_watts": row.energy_watts,
            "temperature_band": row.temperature_band,
            "humidity_band": row.humidity_band,
            "energy_band": row.energy_band,
            "comfort_status": row.comfort_status,
            "timestamp": row.timestamp.isoformat(),
            "processed_at": row.processed_at.isoformat(),
            "source": row.source,
            "anomaly": row.anomaly,
            "anomaly_method": row.anomaly_method,
            "anomaly_score": row.anomaly_score,
            "anomaly_reason": row.anomaly_reason,
        }
        for row in reversed(rows)
    ]


@app.get("/alerts")
def alerts(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Alert).order_by(Alert.created_at.desc()).limit(max(1, min(limit, 200)))
    ).all()
    return [
        {
            "id": row.id,
            "device_id": row.device_id,
            "type": row.alert_type,
            "message": row.message,
            "severity": row.severity,
            "active": row.active,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/dead-letter")
def dead_letter(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(DeadLetterEvent)
        .order_by(DeadLetterEvent.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()
    return [
        {
            "id": row.id,
            "payload": row.original_payload,
            "error": row.error_reason,
            "source": row.source,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/pipeline-events")
def pipeline_events(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PipelineEvent)
        .order_by(PipelineEvent.created_at.desc())
        .limit(max(1, min(limit, 300)))
    ).all()
    return [
        {
            "id": row.id,
            "stage": row.stage,
            "event_type": row.event_type,
            "device_id": row.device_id,
            "source": row.source,
            "message": row.message,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    active_devices = db.scalar(
        select(func.count()).select_from(Device).where(Device.active.is_(True))
    ) or 0
    total_events = db.scalar(select(func.count()).select_from(SensorReading)) or 0
    active_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.active.is_(True))
    ) or 0
    invalid_events = db.scalar(select(func.count()).select_from(DeadLetterEvent)) or 0
    avg_temp = db.scalar(select(func.avg(SensorReading.temperature)))
    avg_humidity = db.scalar(select(func.avg(SensorReading.humidity)))
    avg_energy = db.scalar(select(func.avg(SensorReading.energy_usage)))
    latest_ts = db.scalar(select(func.max(SensorReading.timestamp)))
    anomaly_count = db.scalar(
        select(func.count()).select_from(SensorReading).where(SensorReading.anomaly.is_(True))
    ) or 0

    freshness_seconds = None
    if latest_ts:
        freshness_seconds = max(0, int((utcnow_naive() - latest_ts).total_seconds()))

    return {
        "active_devices": active_devices,
        "events_stored": total_events,
        "active_alerts": active_alerts,
        "anomaly_count": anomaly_count,
        "invalid_events": invalid_events,
        "average_temperature": round(float(avg_temp), 2) if avg_temp is not None else None,
        "average_humidity": round(float(avg_humidity), 2) if avg_humidity is not None else None,
        "average_energy_kw": round(float(avg_energy), 3) if avg_energy is not None else None,
        "data_freshness_seconds": freshness_seconds,
        "pipeline_health": "RUNNING" if simulator.running else "READY",
    }


@app.get("/analytics/devices")
def analytics_devices(db: Session = Depends(get_db)):
    devices = db.scalars(select(Device).order_by(Device.device_id)).all()
    output = []
    for device in devices:
        rows = db.scalars(
            select(SensorReading)
            .where(SensorReading.device_id == device.device_id)
            .order_by(SensorReading.timestamp.desc())
            .limit(500)
        ).all()
        if rows:
            avg_temp = sum(r.temperature for r in rows) / len(rows)
            avg_humidity = sum(r.humidity for r in rows) / len(rows)
            avg_energy = sum(r.energy_usage for r in rows) / len(rows)
            anomaly_count = sum(1 for r in rows if r.anomaly)
            last_seen = rows[0].timestamp.isoformat()
        else:
            avg_temp = avg_humidity = avg_energy = None
            anomaly_count = 0
            last_seen = None

        output.append(
            {
                "device_id": device.device_id,
                "room_name": device.room_name,
                "floor": device.floor,
                "zone": device.zone,
                "active": device.active,
                "events": len(rows),
                "average_temperature": round(avg_temp, 2) if avg_temp is not None else None,
                "average_humidity": round(avg_humidity, 2) if avg_humidity is not None else None,
                "average_energy_kw": round(avg_energy, 3) if avg_energy is not None else None,
                "anomalies": anomaly_count,
                "last_seen": last_seen,
            }
        )
    return output


@app.get("/analytics/energy")
def analytics_energy(hours: int = 24, db: Session = Depends(get_db)):
    hours = max(1, min(hours, 168))
    cutoff = utcnow_naive() - timedelta(hours=hours)
    rows = db.scalars(
        select(SensorReading)
        .where(SensorReading.timestamp >= cutoff)
        .order_by(SensorReading.timestamp)
    ).all()

    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        key = row.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[key].append(row.energy_usage)

    return [
        {
            "hour": hour,
            "events": len(values),
            "average_energy_kw": round(sum(values) / len(values), 3),
            "estimated_energy_kwh": round(sum(values) / max(1, len(values)), 3),
        }
        for hour, values in sorted(buckets.items())
    ]


@app.get("/analytics/anomalies")
def analytics_anomalies(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SensorReading)
        .where(SensorReading.anomaly.is_(True))
        .order_by(SensorReading.timestamp.desc())
        .limit(500)
    ).all()
    counts = Counter(row.anomaly_method or "UNKNOWN" for row in rows)
    return {
        "total": len(rows),
        "by_method": dict(counts),
        "recent": [
            {
                "device_id": row.device_id,
                "timestamp": row.timestamp.isoformat(),
                "method": row.anomaly_method,
                "score": row.anomaly_score,
                "reason": row.anomaly_reason,
                "source": row.source,
            }
            for row in rows[:25]
        ],
    }
