import json
import logging
import paho.mqtt.client as mqtt

import config

logger = logging.getLogger(__name__)


class MqttAnomalyPublisher:
    def __init__(self, client: mqtt.Client):
        self._client = client

    def publish_anomaly(self, device_id: str, timestamp: str, anomalies: dict) -> None:
        anomaly_payload = {
            "device_id": device_id,
            "timestamp": timestamp,
            "anomalies": anomalies,
        }
        info = self._client.publish(
            config.TOPIC_ANOMALY,
            json.dumps(anomaly_payload),
            qos=1,
        )
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.warning(f"ANOMALIA [{device_id}]! Pubblicata su {config.TOPIC_ANOMALY}: {anomaly_payload}")
        else:
            logger.error(f"Errore durante la pubblicazione dell'anomalia per [{device_id}] (rc={info.rc})")