# API Reference

Interactive Swagger documentation is available at `/docs` whenever the FastAPI service is running.

## Health

### `GET /health`

Checks the API and executes a database `SELECT 1`.

## Event ingestion

### `POST /events`

Example request:

```json
{
  "device_id": "ROOM-07",
  "temperature": 22.8,
  "humidity": 58,
  "energy_usage": 2.1,
  "timestamp": "2026-09-13T10:00:00Z"
}
```

Successful events are:

1. schema validated
2. checked against the registered device table
3. transformed/enriched
4. evaluated by anomaly detectors
5. stored
6. converted into alerts when anomalous

Malformed events are stored in `dead_letter_events`.

## Monitoring data

### `GET /readings/latest?limit=100`
Returns recent transformed readings.

### `GET /alerts?limit=50`
Returns recent anomaly alerts.

### `GET /dead-letter?limit=20`
Returns rejected payloads and validation errors.

### `GET /pipeline-events?limit=50`
Returns the processing-stage audit trail.

## Analytics

### `GET /analytics/summary`
Overall device, event, alert, anomaly, invalid-event, average-measurement and freshness metrics.

### `GET /analytics/devices`
Per-device event count, averages, anomaly count and last-seen time.

### `GET /analytics/energy?hours=24`
Hourly energy aggregation for up to seven days.

### `GET /analytics/anomalies`
Total anomalies, counts by detection method and recent anomaly details.

## Demo simulator API

These endpoints control the FastAPI process's built-in HTTP simulator. They are separate from the MQTT simulator container.

### `POST /simulation/start`
### `POST /simulation/pause`
### `POST /simulation/inject-anomaly`
### `POST /demo/reset`
