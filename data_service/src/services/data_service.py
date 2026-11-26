import logging
from domain.measurement import Measurement
from domain.sensor_location import SensorLocation
from storage.repository import DataRepository

logger = logging.getLogger(__name__)

# Dependency injection del repository (che viene creato nel main e passatodentro DataService))
# come parametro al costruttore della classe DataService.
# Così DataService si limita a usare i metodi di quel repository indipendentemente
# dal codice di implementazione del repository stesso, che può cambiare senza che DataService ne risenta.
class DataService:
    def __init__(self, repository: DataRepository):
        self._repository = repository

    def handle_telemetry(self, payload: dict) -> None:
        device_id = payload.get("device_id", "unknown_device")
        timestamp = payload.get("timestamp")
        sensors = payload.get("sensors", {})

        measurement = Measurement(
            time=timestamp,
            device_id=device_id,
            no2=sensors.get("no2"),
            pm25=sensors.get("pm25"),
            o3=sensors.get("o3"),
            pah=sensors.get("pah"),
            temperature=sensors.get("temperature"),
            humidity=sensors.get("humidity"),
        )

        self._repository.save_measurement(measurement)
        logger.info(f"[{device_id}] Misurazione salvata (time={timestamp})")

    def handle_location(self, payload: dict) -> None:
        device_id = payload.get("device_id", "unknown_device")
        lat = payload.get("lat")
        lon = payload.get("lon")

        location = SensorLocation(
            device_id=device_id,
            lat=lat,
            lon=lon,
        )

        self._repository.upsert_location(location)
        logger.info(f"[{device_id}] Posizione aggiornata (lat={lat}, lon={lon})")
