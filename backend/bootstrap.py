from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Device

ROOM_IDS = [f"ROOM-{i:02d}" for i in range(1, 11)]


def seed_devices(db: Session) -> None:
    existing = db.scalar(select(func.count()).select_from(Device)) or 0
    if existing:
        return

    for i, device_id in enumerate(ROOM_IDS, start=1):
        floor = 1 if i <= 5 else 2
        zone = "North" if i % 2 else "South"
        db.add(
            Device(
                device_id=device_id,
                room_name=f"Room {i}",
                floor=floor,
                zone=zone,
                active=True,
            )
        )
    db.commit()
