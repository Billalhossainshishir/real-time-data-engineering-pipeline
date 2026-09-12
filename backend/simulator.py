import asyncio
import os
import random
from datetime import datetime, timezone

ROOMS = [f"ROOM-{i:02d}" for i in range(1, 11)]
INTERVAL = float(os.getenv("SIMULATION_INTERVAL_SECONDS", "2"))


class Simulator:
    def __init__(self):
        self.running = False
        self.task: asyncio.Task | None = None
        self.inject_next_anomaly = False

    def make_event(self):
        device_id = random.choice(ROOMS)
        temperature = round(random.uniform(19.0, 26.5), 1)
        humidity = round(random.uniform(35.0, 65.0), 1)
        energy_usage = round(random.uniform(0.4, 4.2), 2)

        if self.inject_next_anomaly:
            anomaly_kind = random.choice(["temperature", "humidity", "energy"])
            if anomaly_kind == "temperature":
                temperature = 42.0
            elif anomaly_kind == "humidity":
                humidity = 95.0
            else:
                energy_usage = 11.5
            self.inject_next_anomaly = False

        return {
            "device_id": device_id,
            "temperature": temperature,
            "humidity": humidity,
            "energy_usage": energy_usage,
            "timestamp": datetime.now(timezone.utc),
        }

    async def start(self, processor):
        if self.running:
            return
        self.running = True

        async def loop():
            while self.running:
                await processor(self.make_event())
                await asyncio.sleep(INTERVAL)

        self.task = asyncio.create_task(loop())

    async def pause(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    def inject_anomaly(self):
        self.inject_next_anomaly = True


simulator = Simulator()
