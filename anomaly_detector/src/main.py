import logging
import signal
import sys
import threading

import config
from models.detector import OnlineAnomalyDetector
from storage.state_manager import JSONStateManager
from mqtt.client import MqttClientManager
from mqtt.publisher import MqttAnomalyPublisher
from mqtt.listener import MqttTelemetryListener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)
shutdown_event = threading.Event() # Attesa evento shutdown senza consumo CPU


def handle_shutdown(signum, frame):
    logger.info(f"Ricevuto segnale di arresto ({signum}). Avvio graceful shutdown...")
    shutdown_event.set()


def main():
    # Registra gli handler per SIGINT (Ctrl+C) e SIGTERM (docker stop)
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("Avvio Anomaly Detection Service...")

    # Inizializzazione logica di dominio
    state_manager = JSONStateManager(filepath=config.STATE_FILE_PATH)
    detector = OnlineAnomalyDetector(
        alpha=config.ALPHA,
        warmup_samples=config.WARMUP_SAMPLES,
        z_threshold=config.Z_THRESHOLD,
        state_manager=state_manager
    )

    # Inizializzazione infrastruttura MQTT e componenti (Dependency Injection)
    mqtt_manager = MqttClientManager()
    publisher = MqttAnomalyPublisher(mqtt_manager.client)
    MqttTelemetryListener(mqtt_manager.client, detector, publisher)

    # Avvio connessione e ciclo di vita del servizio
    if mqtt_manager.connect_with_retry(shutdown_event):
        mqtt_manager.start_loop()
        try:
            shutdown_event.wait()
        finally:
            mqtt_manager.stop()

    logger.info("Servizio terminato in modo pulito.")
    sys.exit(0)


if __name__ == "__main__":
    main()