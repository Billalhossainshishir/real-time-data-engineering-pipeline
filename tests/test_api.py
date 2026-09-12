from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.main import app


def event_payload(**overrides):
    payload = {
        "device_id": "ROOM-01",
        "temperature": 22.8,
        "humidity": 58.0,
        "energy_usage": 2.1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_health_checks_database():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_valid_event_is_transformed_and_stored():
    with TestClient(app) as client:
        response = client.post("/events", json=event_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["transformation"]["energy_watts"] == 2100.0
    assert body["transformation"]["temperature_band"] == "normal"
    assert body["transformation"]["comfort_status"] == "comfortable"


def test_invalid_event_is_dead_lettered():
    payload = {"device_id": "BAD", "temperature": "wrong"}
    with TestClient(app) as client:
        response = client.post("/events", json=payload)
        dead_letters = client.get("/dead-letter").json()
    assert response.status_code == 422
    assert response.json()["dead_lettered"] is True
    assert len(dead_letters) == 1
    assert dead_letters[0]["source"] == "HTTP"


def test_unknown_registered_device_is_dead_lettered():
    with TestClient(app) as client:
        response = client.post("/events", json=event_payload(device_id="ROOM-99"))
        dead_letters = client.get("/dead-letter").json()
    assert response.status_code == 422
    assert dead_letters
    assert "Unknown device_id" in dead_letters[0]["error"]


def test_rule_anomaly_creates_alert():
    with TestClient(app) as client:
        response = client.post("/events", json=event_payload(temperature=42.0))
        alerts = client.get("/alerts").json()
    assert response.status_code == 200
    assert response.json()["anomaly"] is True
    assert response.json()["anomaly_method"] == "RULE_THRESHOLD"
    assert alerts[0]["severity"] == "Critical"


def test_statistical_anomaly_after_history():
    history = [22.00, 22.08, 21.94, 22.04, 21.98, 22.10, 21.92, 22.06, 22.01, 21.96, 22.03, 21.99]
    with TestClient(app) as client:
        for value in history:
            response = client.post("/events", json=event_payload(temperature=value))
            assert response.status_code == 200
            assert response.json()["anomaly"] is False

        response = client.post("/events", json=event_payload(temperature=22.7))

    assert response.status_code == 200
    assert response.json()["anomaly"] is True
    assert response.json()["anomaly_method"] == "ROLLING_3SIGMA"


def test_pipeline_activity_includes_real_transformation_stage():
    with TestClient(app) as client:
        client.post("/events", json=event_payload())
        events = client.get("/pipeline-events").json()
    stages = {event["stage"] for event in events}
    event_types = {event["event_type"] for event in events}
    assert "TRANSFORMATION" in stages
    assert "TRANSFORMED" in event_types
    assert "STORED" in event_types


def test_analytics_endpoints_return_expected_shapes():
    with TestClient(app) as client:
        client.post("/events", json=event_payload())
        client.post("/events", json=event_payload(device_id="ROOM-02", energy_usage=3.4))
        summary = client.get("/analytics/summary").json()
        devices = client.get("/analytics/devices").json()
        energy = client.get("/analytics/energy").json()
        anomalies = client.get("/analytics/anomalies").json()

    assert summary["events_stored"] == 2
    assert summary["active_devices"] == 10
    assert len(devices) == 10
    assert isinstance(energy, list)
    assert anomalies["total"] == 0


def test_reset_clears_operational_data_but_preserves_devices():
    with TestClient(app) as client:
        client.post("/events", json=event_payload(temperature=42.0))
        reset = client.post("/demo/reset").json()
        summary = client.get("/analytics/summary").json()

    assert reset["reset"] is True
    assert summary["events_stored"] == 0
    assert summary["active_alerts"] == 0
    assert summary["invalid_events"] == 0
    assert summary["active_devices"] == 10
