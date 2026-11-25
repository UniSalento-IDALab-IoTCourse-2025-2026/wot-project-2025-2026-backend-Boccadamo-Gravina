import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI

import config
from api.anomaly_router import router as anomaly_router
from models.detector import OnlineAnomalyDetector
from storage.state_manager import JSONStateManager
from services.anomaly_service import AnomalyDetectionService
from mqtt.client import MqttClientManager
from mqtt.publisher import MqttAnomalyPublisher
from mqtt.listener import MqttTelemetryListener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_event = threading.Event()

    repository = JSONStateManager(filepath=config.STATE_FILE_PATH)
    mqtt_manager = MqttClientManager()
    publisher = MqttAnomalyPublisher(mqtt_manager.client)

    detector = OnlineAnomalyDetector(
        alpha=config.ALPHA,
        warmup_samples=config.WARMUP_SAMPLES,
        z_threshold=config.Z_THRESHOLD,
        initial_state=repository.load_state(),
    )

    service = AnomalyDetectionService(
        detector=detector,
        state_manager=repository,
        publisher=publisher,
    )
    app.state.anomaly_service = service

    MqttTelemetryListener(client=mqtt_manager.client, service=service)

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


app = FastAPI(title="Anomaly Detection Service", lifespan=lifespan)
app.include_router(anomaly_router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
