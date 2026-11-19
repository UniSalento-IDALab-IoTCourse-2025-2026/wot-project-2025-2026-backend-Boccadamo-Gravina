import json
import logging
import paho.mqtt.client as mqtt

import config
from mqtt.publisher import MqttAnomalyPublisher

logger = logging.getLogger(__name__)


class MqttTelemetryListener:
    def __init__(self, client: mqtt.Client, detector, publisher: MqttAnomalyPublisher):
        self._client = client
        self._detector = detector
        self._publisher = publisher

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

            anomalies_detected = {}
            analysis_summary = {}

            for pollutant, val in sensors.items():
                res = self._detector.process_reading(device_id, pollutant, float(val))
                analysis_summary[pollutant] = res
                if res["is_anomaly"]:
                    anomalies_detected[pollutant] = res

            logger.info(
                f"[{device_id}] Campionamento elaborato. Stato: "
                f"{ {k: v['status'] for k, v in analysis_summary.items()} }"
            )

            if anomalies_detected:
                self._publisher.publish_anomaly(device_id, timestamp, anomalies_detected)

        except Exception as e:
            logger.error(f"Errore durante la gestione del messaggio su {msg.topic}: {e}")