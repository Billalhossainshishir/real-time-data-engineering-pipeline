# Real-Time Data Engineering Pipeline

A recruiter-friendly portfolio project that simulates smart-building / IoT sensor data and demonstrates ingestion, validation, data-quality handling, transformation, anomaly detection, alerting and live observability.

## Live demo

The repository root is a **GitHub Pages-ready interactive demo**. No login or server is required for the basic recruiter experience.

Demo flow:

1. Click **Start Simulation**.
2. Watch 10 virtual rooms stream temperature, humidity and energy readings.
3. Click **Inject Anomaly**.
4. Watch the abnormal event pass validation, get stored and create an alert.
5. Click **Inject Invalid Event** to see malformed data isolated in the dead-letter queue.
6. Use **Pause** or **Reset Demo** at any time.

> The public Pages demo runs its simulation in the browser for instant access. The Python/FastAPI backend implementation is also included in this repository as engineering evidence.

## Project stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL-compatible data layer
- Pydantic validation
- JavaScript
- Chart.js
- Docker / Docker Compose
- pytest
- MQTT planned as the next server-side integration stage

## Repository structure

```text
.
├── index.html                 # GitHub Pages live demo
├── assets/
│   ├── css/style.css
│   └── js/app.js
├── backend/                   # FastAPI server-side implementation
├── tests/                     # Backend API tests
├── docs/architecture.md
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── .nojekyll
└── README.md
```

## Publish with GitHub Pages

1. Create a GitHub repository, for example `real-time-data-engineering-pipeline`.
2. Upload/push **all files in this folder to the repository root**.
3. On GitHub open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select branch **main** and folder **/ (root)**.
6. Save.
7. After deployment, the site will be available at a URL in this format:

```text
https://YOUR-GITHUB-USERNAME.github.io/real-time-data-engineering-pipeline/
```

If the repository itself is named `YOUR-GITHUB-USERNAME.github.io`, the site will instead be available directly at:

```text
https://YOUR-GITHUB-USERNAME.github.io/
```

## Run the backend locally

For the current backend dependencies, use **Python 3.13**.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Backend API:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

## What the demo proves

- Continuous event-stream thinking
- Stable device identities and realistic simulated telemetry
- Validation before storage
- Production-style dead-letter handling for malformed data
- Rule-based threshold anomaly detection
- Rolling statistical anomaly checks
- Live alerting and pipeline observability
- Data freshness and throughput metrics
- A separation between recruiter-facing demo UX and server-side engineering implementation

## Portfolio description

**Real-Time Data Engineering Pipeline** — Built a real-time IoT data pipeline for simulated smart-building telemetry, with schema validation, dead-letter handling, live monitoring, anomaly detection and alerting. Implemented a recruiter-friendly public demo alongside a Python/FastAPI backend architecture designed for PostgreSQL, MQTT and containerised deployment.

## Next engineering stages

- MQTT / Mosquitto ingestion path
- Worker service separation
- PostgreSQL deployment
- Isolation Forest comparison
- Docker Compose end-to-end runtime
- Hosted API integration with the GitHub Pages frontend
