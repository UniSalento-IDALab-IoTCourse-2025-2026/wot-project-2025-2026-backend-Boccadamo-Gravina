import json
import logging
import paho.mqtt.client as mqtt

import config
from services.anomaly_service import AnomalyDetectionService

logger = logging.getLogger(__name__)


class MqttTelemetryListener:
    def __init__(self, client: mqtt.Client, service: AnomalyDetectionService):
        self._client = client
        self._service = service

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"Connesso a MQTT Broker. Subscribing a: {config.TOPIC_INPUT}")
            client.subscribe(config.TOPIC_INPUT)
        else:
            logger.error(f"Connessione fallita con codice {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            device_id = payload.get("device_id", "unknown_device")
            timestamp = payload.get("timestamp")
            sensors = payload.get("sensors", {})

            self._service.evaluate_device_telemetry(
                device_id=device_id,
                timestamp=timestamp,
                sensors=sensors,
            )

        except Exception as e:
            logger.error(f"Errore durante la gestione del messaggio su {msg.topic}: {e}")