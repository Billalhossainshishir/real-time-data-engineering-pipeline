# Architecture

## Public GitHub Pages demo

The public demo is intentionally client-side so a recruiter can open it without an account, backend wake-up delay, credentials, or infrastructure dependencies.

```text
Browser sensor simulator
        |
        v
JavaScript validation
        |---- invalid ----> Dead-letter queue panel
        |
      valid
        v
Transformation + in-memory storage
        |
        v
Threshold + rolling statistical anomaly checks
        |
        v
Live charts, device fleet, alerts and observability
```

## Full backend implementation in this repository

```text
Simulator -> HTTP / MQTT -> FastAPI validation -> worker / transforms
                                      |
                                      +-> dead_letter_events
                                      |
                                      v
                                  PostgreSQL
                                      |
                                      v
                                   FastAPI
                                      |
                                      v
                                  Dashboard
```

Core server-side tables are designed around:

- `devices`
- `sensor_readings`
- `alerts`
- `pipeline_events`
- `dead_letter_events`

The browser demo and backend implementation share the same core concepts: stable ROOM-XX device IDs, data-quality validation, anomaly rules, alerts, pipeline activity and monitoring metrics.
