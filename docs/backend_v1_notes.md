# Backend v1 Notes — Archived

This file records the original first backend design. It has been superseded by the completed backend implementation.

The current architecture now includes:

- FastAPI HTTP ingestion
- Pydantic validation
- a real transformation/enrichment stage
- PostgreSQL-compatible persistence
- MQTT / Mosquitto ingestion
- a Python consumer worker
- dead-letter persistence
- rule-based anomaly detection
- rolling 3-sigma detection
- Isolation Forest
- analytics endpoints
- Docker Compose
- automated tests and CI

See the current documentation:

- [Architecture](architecture.md)
- [API Reference](api.md)
- [Case Study](case-study.md)
