# Case Study — Real-Time Data Engineering Pipeline

## Problem

A dashboard alone does not prove data-engineering capability. This project was designed to show the processing decisions that happen before a chart receives clean data: ingestion, validation, isolation of bad records, transformation, persistence, anomaly detection and operational monitoring.

## Portfolio constraint

The public project needed to be:

- clickable without login
- understandable in 30–60 seconds
- reliable on a static portfolio host
- technically honest

GitHub Pages cannot run Python, PostgreSQL or an MQTT broker. The project therefore uses two deliberately separate layers.

## Layer 1 — recruiter-facing live demo

The GitHub Pages experience simulates 10 smart-building rooms directly in the browser. A recruiter can start the stream, inject an anomaly, inject malformed data and immediately see the resulting alert or dead-letter event.

This gives instant visual proof of the concepts without pretending the static page is a hosted backend.

## Layer 2 — engineering implementation

The repository contains a complete local backend stack:

- FastAPI ingestion and analytics API
- Pydantic schema validation
- SQLAlchemy data layer
- PostgreSQL Docker service
- MQTT / Mosquitto broker
- Python MQTT consumer worker
- Python MQTT simulator
- transformation/enrichment service
- dead-letter persistence
- rule anomaly detection
- rolling 3-sigma detection
- Isolation Forest
- pipeline audit events
- automated tests
- CI workflow

## Data flow

```text
Sensor Simulator
→ MQTT Broker
→ Worker
→ Validation
→ Transformation
→ Anomaly Detection
→ PostgreSQL
→ FastAPI Analytics
```

Invalid data follows a different path:

```text
Incoming event
→ Validation fails
→ dead_letter_events
→ pipeline audit event
```

## Transformation examples

The pipeline normalizes UTC timestamps and derives:

- energy in watts
- temperature band
- humidity band
- energy band
- comfort status

These fields make downstream analytics easier and demonstrate that the transformation stage is functional rather than decorative.

## Anomaly strategy

Three complementary approaches are included.

**Rules** provide immediate, explainable protection for known operational limits.

**Rolling 3-sigma** identifies values that are unusual for a particular room even when they do not cross a global threshold.

**Isolation Forest** provides multivariate ML-based detection using temperature, humidity and energy together.

## Data quality decision

Invalid events are not silently discarded and are not allowed to crash the pipeline. They are stored with the original payload, source, validation reason and timestamp. This mirrors a common production dead-letter pattern and makes failure visible for later investigation.

## Observability decision

The system stores explicit pipeline events for ingestion, validation, transformation, storage and detection. This makes the internal processing path queryable through the API rather than relying only on console logs.

## Testing

The automated test suite covers:

- API/database health
- valid ingestion
- transformation output
- malformed input
- unknown device handling
- dead-letter persistence
- rule anomalies
- statistical anomalies
- pipeline-stage logging
- analytics
- demo reset

GitHub Actions runs these tests on repository pushes and pull requests.

## What I would deploy next

The full backend is currently designed to run locally through Docker Compose while the recruiter demo stays on GitHub Pages. The next infrastructure step would be to host FastAPI and PostgreSQL, then optionally connect the GitHub Pages dashboard to that backend while keeping demo mode available as a fallback.

## Result

The final project demonstrates both sides of the portfolio problem:

1. an immediate, recruiter-friendly interactive demo
2. a deeper engineering repository showing backend, data, ML, messaging, database, testing and containerisation skills
