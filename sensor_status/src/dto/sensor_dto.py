from pydantic import BaseModel, Field
from domain.sensor import SensorState

class SensorLocationUpdateDTO(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitudine WGS84")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitudine WGS84")

class SensorLocationResponseDTO(BaseModel):
    device_id: str
    lat: float
    lon: float
    location_updated_at: str
    mqtt_topic: str

class SensorStatusDTO(BaseModel):
    device_id: str
    status: SensorState
    last_seen: str
    updated_at: str
    battery_level: float | None = None
    firmware_version: str | None = None
    sensors_health: dict[str, str] | None = None
    offline_reason: str | None = None
    lat: float | None = None
    lon: float | None = None
    location_updated_at: str | None = None


class StatusSummaryDTO(BaseModel):
    total: int
    up: int
    down: int


class SensorsOverviewDTO(BaseModel):
    summary: StatusSummaryDTO
    sensors: list[SensorStatusDTO]