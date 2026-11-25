from dataclasses import dataclass
from typing import Literal

SensorState = Literal["up", "down"]


@dataclass
class SensorStatus:
    device_id: str
    status: SensorState
    last_seen: str                          # Timestamp inviato dal sensore (campo "timestamp")
    updated_at: str                         # Timestamp di ricezione lato server
    battery_level: float | None = None
    firmware_version: str | None = None
    sensors_health: dict[str, str] | None = None
    offline_reason: str | None = None       # Valorizzato solo quando è down (es. "unexpected_disconnection")
    lat: float | None = None
    lon: float | None = None
    location_updated_at: str | None = None