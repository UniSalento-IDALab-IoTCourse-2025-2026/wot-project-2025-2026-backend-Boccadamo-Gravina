from pydantic import BaseModel
from domain.sensor import SensorState


class SensorStatusDTO(BaseModel):
    device_id: str
    status: SensorState
    last_seen: str
    updated_at: str
    battery_level: float | None = None
    firmware_version: str | None = None
    sensors_health: dict[str, str] | None = None
    offline_reason: str | None = None


class StatusSummaryDTO(BaseModel):
    total: int
    up: int
    down: int


class SensorsOverviewDTO(BaseModel):
    summary: StatusSummaryDTO
    sensors: list[SensorStatusDTO]