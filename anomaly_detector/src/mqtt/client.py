import logging
import threading
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt

import config

logger = logging.getLogger(__name__)


class MqttClientManager:
    def __init__(self):
        self.client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id=config.MQTT_CLIENT_ID,
        )
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

        self.client.on_disconnect = self._on_disconnect

    def _on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        if rc != 0:
            logger.warning(f"Disconnessione inattesa da MQTT (codice {rc}). Riconnessione automatica in corso...")
        else:
            logger.info("Disconnessione da MQTT completata con successo.")

    def connect_with_retry(self, shutdown_event: threading.Event) -> bool:
        connected = False
        while not shutdown_event.is_set() and not connected:
            try:
                self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
                connected = True
            except Exception as e:
                logger.warning(f"Broker MQTT non raggiungibile ({e}), attendo 3 secondi...")
                shutdown_event.wait(timeout=3)
        return connected

    def start_loop(self) -> None:
        self.client.loop_start()

    def stop(self) -> None:
        logger.info("Chiusura del client MQTT...")
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Client MQTT disconnesso con successo.")