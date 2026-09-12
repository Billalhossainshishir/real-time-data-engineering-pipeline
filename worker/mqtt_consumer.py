import json
import os
import time

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from backend.bootstrap import seed_devices
from backend.database import Base, SessionLocal, engine
from backend.schemas import SensorEvent
from backend.services.ingestion import process_sensor_event, record_dead_letter

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "building/sensors/#")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to {MQTT_TOPIC}")
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, message):
    raw = message.payload.decode("utf-8", errors="replace")
    with SessionLocal() as db:
        try:
            payload = json.loads(raw)
            event = SensorEvent.model_validate(payload)
            result = process_sensor_event(event, db, source="MQTT")
            print(
                f"Processed {event.device_id} from {message.topic}; "
                f"anomaly={result['anomaly']} method={result['anomaly_method']}"
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            record_dead_letter(db, raw, str(exc), source="MQTT")
            print(f"Dead-lettered invalid MQTT payload from {message.topic}: {exc}")
        except Exception as exc:
            record_dead_letter(db, raw, str(exc), source="MQTT")
            print(f"MQTT processing error: {exc}")


def main():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_devices(db)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="pipeline-worker")
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            print(f"Waiting for MQTT broker: {exc}")
            time.sleep(2)

    client.loop_forever()


if __name__ == "__main__":
    main()
