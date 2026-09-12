from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.main import app


def test_health():
    with TestClient(app) as client:
        r = client.get('/health')
        assert r.status_code == 200
        assert r.json()['status'] == 'ok'


def test_valid_event():
    payload = {
        'device_id':'ROOM-01',
        'temperature':22.8,
        'humidity':58,
        'energy_usage':2.1,
        'timestamp':datetime.now(timezone.utc).isoformat(),
    }
    with TestClient(app) as client:
        r = client.post('/events', json=payload)
        assert r.status_code == 200
        assert r.json()['accepted'] is True


def test_invalid_event_is_dead_lettered():
    payload = {'device_id':'BAD', 'temperature':'wrong'}
    with TestClient(app) as client:
        r = client.post('/events', json=payload)
        assert r.status_code == 422
        assert r.json()['dead_lettered'] is True
