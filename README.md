# Real-Time Data Engineering Pipeline

A recruiter-facing portfolio project that demonstrates a complete smart-building data-engineering workflow: simulated IoT telemetry, schema validation, transformation, persistence, anomaly detection, dead-letter handling, MQTT ingestion, analytics and operational observability.

## Live demo

**GitHub Pages:** https://billalhossainshishir.github.io/real-time-data-engineering-pipeline/

The public demo is intentionally lightweight and runs in the browser so a recruiter can test the project instantly without credentials, containers or backend wake-up time.

Demo flow:

1. Click **Start Simulation**.
2. Watch 10 virtual rooms stream temperature, humidity and energy readings.
3. Click **Inject Anomaly** and see an alert appear.
4. Click **Inject Invalid Event** and see the malformed payload isolated in the dead-letter queue.
5. Inspect throughput, freshness, device state and pipeline activity.

> **Important:** the GitHub Pages demo is not connected to a hosted FastAPI/PostgreSQL/MQTT stack. The full backend implementation is included in this repository and can be run locally with Docker Compose.

## What is implemented

### Public recruiter demo

- 10 stable `ROOM-01` to `ROOM-10` devices
- continuous browser-based event generation
- validation and dead-letter isolation
- threshold and rolling statistical anomaly detection
- live charts with Chart.js
- device status, alerts, throughput and data freshness
- start, pause, anomaly, invalid-event and reset controls

### Engineering backend

- FastAPI ingestion API
- Pydantic event validation
- SQLAlchemy persistence layer
- PostgreSQL-compatible schema
- real transformation stage with normalized timestamps and derived operational bands
- dead-letter persistence for invalid HTTP and MQTT payloads
- rule-based anomaly detection
- rolling 3-sigma statistical detection
- Isolation Forest multivariate anomaly detection
- alert creation and pipeline event logging
- analytics endpoints
- MQTT / Mosquitto ingestion worker
- MQTT sensor simulator
- Docker Compose stack
- automated pytest suite
- GitHub Actions backend test workflow

## Architecture

### Public GitHub Pages demo

```text
Browser simulator
      ↓
JavaScript validation
      ├── invalid → in-memory dead-letter queue
      ↓
Browser processing
      ↓
Rule + rolling statistical detection
      ↓
Chart.js dashboard
```

### Full engineering implementation

```text
MQTT sensor simulator
        ↓
Mosquitto broker
        ↓
Python MQTT worker
        ↓
Pydantic validation
        ├── invalid → dead_letter_events
        ↓
Transformation / enrichment
        ↓
Rule → rolling 3σ → Isolation Forest
        ↓
PostgreSQL
        ↓
FastAPI analytics / monitoring API
```

See [docs/architecture.md](docs/architecture.md) for the detailed design.

## Repository structure

```text
.
├── index.html
├── assets/
│   ├── css/style.css
│   └── js/app.js
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── bootstrap.py
│   ├── simulator.py
│   └── services/
│       ├── transformations.py
│       ├── anomaly_detection.py
│       └── ingestion.py
├── worker/
│   └── mqtt_consumer.py
├── simulator/
│   └── mqtt_simulator.py
├── mosquitto/
│   └── mosquitto.conf
├── tests/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── case-study.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .github/workflows/tests.yml
```

## Event schema

```json
{
  "device_id": "ROOM-07",
  "temperature": 22.8,
  "humidity": 58.0,
  "energy_usage": 2.1,
  "timestamp": "2026-09-13T10:00:00Z"
}
```

## Transformation stage

Accepted events are transformed before persistence. The backend currently derives:

- normalized UTC timestamp
- `energy_watts`
- `temperature_band`
- `humidity_band`
- `energy_band`
- `comfort_status`

This makes the Transformation stage a real processing step rather than only a diagram label.

## Anomaly detection

The backend applies detectors in this order:

1. **Rule thresholds** — catches obvious operational failures such as `temperature > 35°C`, `humidity > 85%`, or `energy_usage > 7.5 kW`.
2. **Rolling 3-sigma detection** — compares a new reading with recent per-device history after enough observations exist.
3. **Isolation Forest** — evaluates temperature, humidity and energy together after a larger history window is available.

The first detector that identifies an anomaly creates an alert and stores the method, reason and score where relevant.

## Database tables

- `devices`
- `sensor_readings`
- `alerts`
- `pipeline_events`
- `dead_letter_events`

Sensor readings also store derived transformation fields, anomaly metadata and the ingestion source (`HTTP`, `MQTT` or `SIMULATOR`).

## Run the full backend with Docker

Requirements:

- Docker Desktop / Docker Engine
- Docker Compose

Start the complete local stack:

```bash
docker compose up --build
```

This starts:

- PostgreSQL
- Mosquitto MQTT broker
- FastAPI API
- MQTT consumer worker
- MQTT sensor simulator

Open:

```text
Dashboard / API root: http://localhost:8000
Swagger API docs:     http://localhost:8000/docs
```

The MQTT simulator publishes a new sensor event approximately every two seconds and injects a demo anomaly periodically. The worker validates, transforms, detects anomalies and writes accepted events to PostgreSQL.

Stop the stack:

```bash
docker compose down
```

Remove the demo database volume as well:

```bash
docker compose down -v
```

## Run only FastAPI locally

Python 3.13 is recommended.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

By default this uses local SQLite. Set `DATABASE_URL` to use PostgreSQL.

## Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | service and database health |
| `POST` | `/events` | ingest one validated sensor event |
| `GET` | `/readings/latest` | recent transformed readings |
| `GET` | `/alerts` | anomaly alerts |
| `GET` | `/dead-letter` | rejected events |
| `GET` | `/pipeline-events` | processing-stage audit trail |
| `GET` | `/analytics/summary` | overall operational metrics |
| `GET` | `/analytics/devices` | per-device statistics |
| `GET` | `/analytics/energy` | hourly energy aggregation |
| `GET` | `/analytics/anomalies` | anomaly counts and methods |
| `POST` | `/simulation/start` | start FastAPI in-process simulator |
| `POST` | `/simulation/pause` | pause simulator |
| `POST` | `/simulation/inject-anomaly` | make next simulated event abnormal |
| `POST` | `/demo/reset` | clear operational demo data |

See [docs/api.md](docs/api.md) for more detail.

## Testing

Run:

```bash
pytest -q
```

The suite covers health checks, valid ingestion, transformation output, validation failures, dead-letter persistence, unknown devices, threshold anomalies, statistical anomalies, pipeline-stage logging, analytics and reset behaviour.

GitHub Actions also runs the backend test suite on pushes and pull requests.

## Case study

Read [docs/case-study.md](docs/case-study.md).

## Portfolio wording

**Real-Time Data Engineering Pipeline — Sep 2026**  
Built an interactive smart-building IoT pipeline with a Python/FastAPI backend, PostgreSQL-compatible persistence, Pydantic validation, MQTT ingestion, dead-letter handling, transformation/enrichment, rule-based and statistical anomaly detection, Isolation Forest analysis, operational analytics, Docker Compose infrastructure and an instant recruiter-facing GitHub Pages demo.

## Design decision: why the live demo is separate

A public portfolio link should open immediately and remain reliable. GitHub Pages provides that experience but only supports static browser code. Instead of pretending the static page is a deployed Python system, this project separates concerns:

- **GitHub Pages** demonstrates the user experience and core pipeline concepts interactively.
- **This repository** contains the full server-side implementation and infrastructure code.

That distinction is intentional and documented.
