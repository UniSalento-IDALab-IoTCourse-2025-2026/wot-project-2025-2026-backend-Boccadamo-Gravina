import logging
import signal
import sys
import threading
import config
from models.detector import OnlineAnomalyDetector
from storage.state_manager import JSONStateManager
from mqtt.client import create_mqtt_client, run_mqtt_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

shutdown_event = threading.Event() # Attesa evento shutdown senza consumo CPU
    
def handle_shutdown(signum, frame):
    logging.info(f"Ricevuto segnale di arresto ({signum}). Avvio graceful shutdown...")
    shutdown_event.set()

def main():
    # Registra gli handler per SIGINT (Ctrl+C) e SIGTERM (docker stop)
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logging.info("Avvio Anomaly Detection Service...")
    
    state_manager = JSONStateManager(filepath=config.STATE_FILE_PATH)
    detector = OnlineAnomalyDetector(
        alpha=config.ALPHA,
        warmup_samples=config.WARMUP_SAMPLES,
        z_threshold=config.Z_THRESHOLD,
        state_manager=state_manager
    )

    client = create_mqtt_client(detector)
    
    run_mqtt_service(client, shutdown_event=shutdown_event)
    
    logging.info("Servizio terminato in modo pulito.")
    sys.exit(0)

if __name__ == "__main__":
    main()