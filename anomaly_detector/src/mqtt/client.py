import json
import logging
import time
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt
import config

def create_mqtt_client(detector):
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="anomaly-detector-service")

    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info(f"Connesso a MQTT Broker. Subscribing a: {config.TOPIC_INPUT}")
            client.subscribe(config.TOPIC_INPUT)
        else:
            logging.error(f"Connessione fallita con codice {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            device_id = payload.get("device_id", "unknown_device")
            timestamp = payload.get("timestamp")
            sensors = payload.get("sensors", {})

            anomalies_detected = {}
            analysis_summary = {}

            for pollutant, val in sensors.items():
                res = detector.process_reading(device_id, pollutant, float(val))
                analysis_summary[pollutant] = res
                if res["is_anomaly"]:
                    anomalies_detected[pollutant] = res

            # Log sintetico
            logging.info(
                f"[{device_id}] Campionamento elaborato. Stato: "
                f"{ {k: v['status'] for k, v in analysis_summary.items()} }"
            )

            # Se c'è almeno un'anomalia, pubblica un evento sul topic dedicato
            if anomalies_detected:
                anomaly_payload = {
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "anomalies": anomalies_detected
                }
                client.publish(config.TOPIC_ANOMALY, json.dumps(anomaly_payload), qos=1)
                logging.warning(f"ANOMALIA [{device_id}]! Pubblicata su {config.TOPIC_ANOMALY}: {anomaly_payload}")

        except Exception as e:
            logging.error(f"Errore durante la gestione del messaggio: {e}")

    def on_disconnect(client, userdata, disconnect_flags, rc, properties=None):
        if rc != 0:
            logging.warning(f"Disconnessione inattesa da MQTT (codice {rc}). Tenterò la riconnessione automatica...")
        else:
            logging.info("Disconnessione da MQTT completata con successo.")

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    return client

def run_mqtt_service(client, shutdown_event):
    """
    Gestisce la prima connessione con retry, avvia il loop in background 
    e attende il segnale di stop per chiudere in modo pulito.
    """
    connected = False
    while not shutdown_event.is_set() and not connected:
        try:
            client.connect(config.MQTT_BROKER, config.MQTT_PORT, keepalive=30)
            connected = True
        except Exception as e:
            logging.warning(f"Broker MQTT non raggiungibile ({e}), attendo 3 secondi...")
            shutdown_event.wait(timeout=3)

    if shutdown_event.is_set():
        return

    client.loop_start()

    try:
        shutdown_event.wait()
    finally:
        logging.info("Chiusura del client MQTT...")
        client.loop_stop()
        client.disconnect()
        logging.info("Client MQTT disconnesso con successo.")