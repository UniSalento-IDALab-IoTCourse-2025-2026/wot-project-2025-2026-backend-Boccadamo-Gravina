import json
import logging
import paho.mqtt.client as mqtt

import config

logger = logging.getLogger(__name__)


class MqttLocationPublisher:
    def __init__(self, client: mqtt.Client):
        self._client = client

    def publish_location(self, device_id: str, lat: float, lon: float, updated_at: str) -> str:
        topic = f"{config.TOPIC_LOCATION}"
        payload = {
            "device_id": device_id,
            "lat": lat,
            "lon": lon,
            "updated_at": updated_at,
        }
        info = self._client.publish(
            topic,
            json.dumps(payload),
            qos=1,
            retain=True,
        )
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Posizione [{device_id}] pubblicata su {topic}: {payload}")
        else:
            logger.error(f"Errore pubblicazione posizione per [{device_id}] su {topic} (rc={info.rc})")
            raise RuntimeError(f"Errore pubblicazione MQTT su '{topic}' (rc={info.rc})")
        return topic