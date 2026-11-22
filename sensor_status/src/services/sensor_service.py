import json
from datetime import datetime, timezone

from domain.sensor import SensorStatus, SensorState
from storage.sensor_repository import SensorRepository
from dto.sensor_dto import (
    SensorStatusDTO,
    SensorsOverviewDTO,
    StatusSummaryDTO,
)


class SensorService:
    def __init__(self, repository: SensorRepository):
        self._repo = repository

    def update_from_mqtt(self, topic_device_id: str, payload_raw: str) -> SensorStatus:
        data = json.loads(payload_raw)

        # Usa il device_id nel JSON se presente, altrimenti quello estratto dal topic
        device_id = data.get("device_id") or topic_device_id
        raw_status = str(data.get("status", "offline")).lower()
        normalized_state: SensorState = "up" if raw_status == "online" else "down"

        now_iso = datetime.now(timezone.utc).isoformat()
        sensor_timestamp = data.get("timestamp", now_iso)

        # Recupera eventuale stato precedente per non perdere batteria/firmware su LWT
        previous = self._repo.find_by_id(device_id)

        if normalized_state == "up":
            sensor = SensorStatus(
                device_id=device_id,
                status="up",
                last_seen=sensor_timestamp,
                updated_at=now_iso,
                battery_level=data.get("battery_level"),
                firmware_version=data.get("firmware_version"),
                sensors_health=data.get("sensors_health"),
                offline_reason=None,  # Azzera eventuali motivi di disconnessione precedenti
            )
        else:
            sensor = SensorStatus(
                device_id=device_id,
                status="down",
                last_seen=sensor_timestamp,
                updated_at=now_iso,
                battery_level=previous.battery_level if previous else None,
                firmware_version=previous.firmware_version if previous else None,
                sensors_health=previous.sensors_health if previous else None,
                offline_reason=data.get("reason", "unknown"),
            )

        self._repo.save(sensor)
        return sensor

    def get_overview(self) -> SensorsOverviewDTO:
        sensors = self._repo.find_all()
        up_count = sum(1 for s in sensors if s.status == "up")
        down_count = len(sensors) - up_count

        return SensorsOverviewDTO(
            summary=StatusSummaryDTO(
                total=len(sensors),
                up=up_count,
                down=down_count,
            ),
            sensors=[self._to_dto(s) for s in sensors],
        )

    def get_sensor_by_id(self, device_id: str) -> SensorStatusDTO | None:
        sensor = self._repo.find_by_id(device_id)
        if not sensor:
            return None
        return self._to_dto(sensor)

    @staticmethod
    def _to_dto(sensor: SensorStatus) -> SensorStatusDTO:
        return SensorStatusDTO(
            device_id=sensor.device_id,
            status=sensor.status,
            last_seen=sensor.last_seen,
            updated_at=sensor.updated_at,
            battery_level=sensor.battery_level,
            firmware_version=sensor.firmware_version,
            sensors_health=sensor.sensors_health,
            offline_reason=sensor.offline_reason,
        )