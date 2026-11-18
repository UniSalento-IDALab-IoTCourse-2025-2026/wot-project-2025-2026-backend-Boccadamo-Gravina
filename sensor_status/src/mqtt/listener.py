import logging
import paho.mqtt.client as mqtt

import config
from services.sensor_service import SensorService

logger = logging.getLogger(__name__)


class MqttStatusListener:
    def __init__(self, client: mqtt.Client, service: SensorService):
        self._client = client
        self._service = service
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"Connesso a MQTT Broker. Subscribing a: {config.TOPIC_STATUS}")
            client.subscribe(config.TOPIC_STATUS)
        else:
            logger.error(f"Connessione fallita con codice {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            topic_device_id = parts[1] if len(parts) >= 2 else "unknown_device"
            payload_raw = msg.payload.decode("utf-8")

            updated = self._service.update_from_mqtt(topic_device_id, payload_raw)
            logger.info(f"[{updated.device_id}] Stato aggiornato -> {updated.status}")
        except Exception as e:
            logger.error(f"Errore durante la gestione del messaggio su {msg.topic}: {e}")