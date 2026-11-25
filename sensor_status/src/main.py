import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI

from api.sensor_router import router as sensor_router
from mqtt.client import MqttClientManager
from mqtt.publisher import MqttLocationPublisher
from mqtt.listener import MqttStatusListener
from storage.sensor_repository import SensorRepository
from services.sensor_service import SensorService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_event = threading.Event()

    repository = SensorRepository()
    mqtt_manager = MqttClientManager()
    publisher = MqttLocationPublisher(mqtt_manager.client)

    service = SensorService(
        repository=repository,
        publisher=publisher,
    )
    app.state.sensor_service = service

    MqttStatusListener(client=mqtt_manager.client, service=service)

    # Avvia il retry in background così FastAPI si avvia subito senza bloccarsi
    def _connect_and_start():
        if mqtt_manager.connect_with_retry(shutdown_event):
            mqtt_manager.start_loop()

    connect_thread = threading.Thread(target=_connect_and_start, daemon=True)
    connect_thread.start()

    yield

    shutdown_event.set()
    connect_thread.join(timeout=5)
    mqtt_manager.stop()


app = FastAPI(title="Sensors Status Service", lifespan=lifespan)
app.include_router(sensor_router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}