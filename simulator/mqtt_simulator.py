import json
import os
import time

import paho.mqtt.client as mqtt

from backend.simulator import Simulator

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INTERVAL = float(os.getenv("MQTT_SIMULATION_INTERVAL_SECONDS", "2"))
ANOMALY_EVERY = int(os.getenv("MQTT_ANOMALY_EVERY", "30"))


def connect_with_retry(client: mqtt.Client) -> None:
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            return
        except OSError as exc:
            print(f"Waiting for MQTT broker: {exc}")
            time.sleep(2)


def main():
    simulator = Simulator()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sensor-simulator")
    connect_with_retry(client)
    client.loop_start()

    event_count = 0
    try:
        while True:
            event_count += 1
            if ANOMALY_EVERY > 0 and event_count % ANOMALY_EVERY == 0:
                simulator.inject_anomaly()

            event = simulator.make_event()
            serializable = {**event, "timestamp": event["timestamp"].isoformat()}
            topic = f"building/sensors/{event['device_id']}"
            client.publish(topic, json.dumps(serializable), qos=1)
            print(f"Published {topic}: {serializable}")
            time.sleep(INTERVAL)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
