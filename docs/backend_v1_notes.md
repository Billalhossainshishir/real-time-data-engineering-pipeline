# Architecture (v1)

Sensor Simulator
    ↓
FastAPI POST /events
    ↓
Pydantic Validation ── invalid ──→ Dead-Letter Events
    ↓ valid
Rule Threshold Detection
    ↓
SQL Database
  ├─ devices
  ├─ sensor_readings
  ├─ alerts
  ├─ pipeline_events
  └─ dead_letter_events
    ↓
Analytics API + Live Dashboard

Planned v2: Simulator → MQTT broker → Consumer/Worker → Validation → PostgreSQL → FastAPI → Dashboard
