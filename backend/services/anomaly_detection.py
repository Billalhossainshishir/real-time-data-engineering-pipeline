from dataclasses import dataclass
from math import sqrt

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SensorReading
from ..schemas import SensorEvent

STAT_WINDOW = 30
STAT_MIN_HISTORY = 10
STAT_Z_THRESHOLD = 3.0
ISOLATION_MIN_HISTORY = 25
ISOLATION_WINDOW = 80


@dataclass(frozen=True)
class DetectionResult:
    anomaly: bool
    method: str | None = None
    reason: str | None = None
    severity: str | None = None
    score: float | None = None


def detect_rule_anomaly(event: SensorEvent) -> DetectionResult | None:
    reasons: list[str] = []
    if event.temperature > 35 or event.temperature < 10:
        reasons.append(f"temperature={event.temperature}C")
    if event.humidity > 85 or event.humidity < 15:
        reasons.append(f"humidity={event.humidity}%")
    if event.energy_usage > 7.5:
        reasons.append(f"energy_usage={event.energy_usage}kW")

    if not reasons:
        return None

    severity = "Critical" if event.temperature > 40 or event.energy_usage > 10 else "High"
    return DetectionResult(
        anomaly=True,
        method="RULE_THRESHOLD",
        reason=", ".join(reasons),
        severity=severity,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _pstdev(values: list[float]) -> float:
    mean = _mean(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def detect_statistical_anomaly(db: Session, event: SensorEvent) -> DetectionResult | None:
    rows = db.scalars(
        select(SensorReading)
        .where(
            SensorReading.device_id == event.device_id,
            SensorReading.anomaly.is_(False),
        )
        .order_by(SensorReading.timestamp.desc())
        .limit(STAT_WINDOW)
    ).all()

    if len(rows) < STAT_MIN_HISTORY:
        return None

    candidates = {
        "temperature": (event.temperature, [row.temperature for row in rows], "C"),
        "humidity": (event.humidity, [row.humidity for row in rows], "%"),
        "energy_usage": (event.energy_usage, [row.energy_usage for row in rows], "kW"),
    }

    strongest: tuple[str, float, float, str] | None = None
    for field, (value, history, unit) in candidates.items():
        sd = _pstdev(history)
        if sd < 0.05:
            continue
        z_score = abs((value - _mean(history)) / sd)
        if z_score >= STAT_Z_THRESHOLD and (strongest is None or z_score > strongest[1]):
            strongest = (field, z_score, value, unit)

    if strongest is None:
        return None

    field, z_score, value, unit = strongest
    return DetectionResult(
        anomaly=True,
        method="ROLLING_3SIGMA",
        reason=f"{field}={value}{unit} ({z_score:.2f} sigma from recent mean)",
        severity="High",
        score=round(z_score, 4),
    )


def detect_isolation_forest(db: Session, event: SensorEvent) -> DetectionResult | None:
    rows = db.scalars(
        select(SensorReading)
        .where(
            SensorReading.device_id == event.device_id,
            SensorReading.anomaly.is_(False),
        )
        .order_by(SensorReading.timestamp.desc())
        .limit(ISOLATION_WINDOW)
    ).all()

    if len(rows) < ISOLATION_MIN_HISTORY:
        return None

    history = np.array(
        [[row.temperature, row.humidity, row.energy_usage] for row in rows],
        dtype=float,
    )
    sample = np.array([[event.temperature, event.humidity, event.energy_usage]], dtype=float)

    scaler = StandardScaler()
    history_scaled = scaler.fit_transform(history)
    sample_scaled = scaler.transform(sample)

    model = IsolationForest(
        n_estimators=150,
        contamination=0.05,
        random_state=42,
    )
    model.fit(history_scaled)
    prediction = int(model.predict(sample_scaled)[0])
    score = float(-model.score_samples(sample_scaled)[0])

    if prediction != -1:
        return None

    return DetectionResult(
        anomaly=True,
        method="ISOLATION_FOREST",
        reason="Multivariate reading differs from the device's recent operating pattern",
        severity="Medium",
        score=round(score, 6),
    )


def detect_anomaly(db: Session, event: SensorEvent) -> DetectionResult:
    for detector in (
        lambda: detect_rule_anomaly(event),
        lambda: detect_statistical_anomaly(db, event),
        lambda: detect_isolation_forest(db, event),
    ):
        result = detector()
        if result is not None:
            return result
    return DetectionResult(anomaly=False)
