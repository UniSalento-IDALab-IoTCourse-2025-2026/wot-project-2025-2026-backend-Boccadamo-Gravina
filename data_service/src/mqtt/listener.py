import json
import logging
import paho.mqtt.client as mqtt
import config
from services.data_service import DataService
import re

logger = logging.getLogger(__name__)


def match_mqtt_topic(pattern: str, topic: str) -> dict[str, str] | None:
    """
    Verifica se `topic` rispetta `pattern` (con wildcard `+`)
    e restituisce i segmenti catturati, oppure None se non matcha.
    """
    parts = pattern.split("/")
    regex_parts = []
    for i, part in enumerate(parts):
        if part == "+":
            regex_parts.append(f"(?P<w_{i}>[^/]+)")
        else:
            regex_parts.append(re.escape(part))

    regex = "^" + "/".join(regex_parts) + "$"
    match = re.match(regex, topic)
    return match.groupdict() if match else None

class MqttDataListener:
    def __init__(self, client: mqtt.Client, service: DataService):
        self._client = client
        self._service = service

        # Configura i callback per la connessione e la ricezione dei messaggi
        # I callback sono on_connect e on_message,
        # e vengono chiamati automaticamente da paho-mqtt quando si verifica l'evento corrispondente
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    # E' una funzione a parte (cioè NON è nel costruttore) perché le subscription
    # vanno rifatte a ogni riconnessione al broker MQTT, non solo quando il listener viene creato la prima volta.
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(config.MQTT_TOPIC_TELEMETRY)
            client.subscribe(config.MQTT_TOPIC_LOCATION)
            logger.info(f"Connesso a MQTT. Subscribing a: {config.MQTT_TOPIC_TELEMETRY}, {config.MQTT_TOPIC_LOCATION}")
        else:
            logger.error(f"Connessione fallita con codice {rc}")

    # Chiamata automaticamente ogni volta che arriva un messaggio su uno dei topic a cui siamo iscritti
    # Decodifica il payload JSON e chiama il metodo appropriato di DataService per gestire i dati ricevuti,
    # quindi per fare tipo salvataggio nel db o upsert posizione
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))

            if match_mqtt_topic(config.MQTT_TOPIC_TELEMETRY, msg.topic):
                self._service.handle_telemetry(payload)
            elif match_mqtt_topic(config.MQTT_TOPIC_LOCATION, msg.topic):
                self._service.handle_location(payload)
            else:
                logger.warning(f"Messaggio ricevuto su topic inatteso: {msg.topic}")

        except Exception as e:
            logger.error(f"Errore durante la gestione del messaggio su {msg.topic}: {e}")
