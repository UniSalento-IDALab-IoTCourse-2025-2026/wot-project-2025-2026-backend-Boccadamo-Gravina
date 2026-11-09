import json
import logging
import math
import os
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
TOPIC_INPUT = os.getenv("MQTT_TOPIC_INPUT", "telemetry/air_quality")
TOPIC_ANOMALY = os.getenv("MQTT_TOPIC_ANOMALY", "telemetry/anomalies")

# Parametri di Online Learning
WARMUP_SAMPLES = int(os.getenv("WARMUP_SAMPLES", 30))  # Campioni minimi prima di segnalare
Z_THRESHOLD = float(os.getenv("Z_THRESHOLD", 3.0))     # Soglia Z-Score per anomalia

class WelfordOnlineStats:
    """Calcola media e varianza in modo incrementale (Algoritmo di Welford)."""
    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.M2 = 0.0

    def update(self, x: float):
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.M2 += delta * delta2

    @property
    def std_dev(self) -> float:
        if self.count < 2:
            return 0.0
        variance = self.M2 / (self.count - 1)
        return math.sqrt(variance)

class OnlineAnomalyDetector:
    def __init__(self, warmup_samples: int, z_threshold: float):
        self.warmup_samples = warmup_samples
        self.z_threshold = z_threshold
        # Un tracciatore di statistiche per ogni inquinante
        self.stats = {}

    def process_reading(self, pollutant: str, value: float) -> dict:
        if pollutant not in self.stats:
            self.stats[pollutant] = WelfordOnlineStats()

        st = self.stats[pollutant]
        is_anomaly = False
        z_score = 0.0

        # Se abbiamo superato il warmup e la deviazione standard è valida
        if st.count >= self.warmup_samples and st.std_dev > 0:
            z_score = abs(value - st.mean) / st.std_dev
            if z_score > self.z_threshold:
                is_anomaly = True

        # Aggiorna il modello online con il nuovo dato
        st.update(value)

        return {
            "value": value,
            "mean": round(st.mean, 2),
            "std_dev": round(st.std_dev, 2),
            "z_score": round(z_score, 2),
            "is_anomaly": is_anomaly,
            "status": "learning" if st.count <= self.warmup_samples else ("ANOMALY" if is_anomaly else "NORMAL")
        }

detector = OnlineAnomalyDetector(WARMUP_SAMPLES, Z_THRESHOLD)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        device_id = data.get("device_id")
        timestamp = data.get("timestamp")
        sensors = data.get("sensors", {})

        anomalies_detected = {}
        analysis_summary = {}

        for pollutant, val in sensors.items():
            res = detector.process_reading(pollutant, float(val))
            analysis_summary[pollutant] = res
            if res["is_anomaly"]:
                anomalies_detected[pollutant] = res

        # Log sintetico
        logging.info(f"[{device_id}] Elaborato campionamento. Stato inquinanti: "
                     f"{ {k: v['status'] for k, v in analysis_summary.items()} }")

        # Se c'è almeno un'anomalia, pubblica un evento sul topic dedicato
        if anomalies_detected:
            anomaly_payload = {
                "device_id": device_id,
                "timestamp": timestamp,
                "anomalies": anomalies_detected
            }
            client.publish(TOPIC_ANOMALY, json.dumps(anomaly_payload), qos=1)
            logging.warning(f"ANOMALIA RILEVATA! Pubblicata su {TOPIC_ANOMALY}: {anomaly_payload}")

    except Exception as e:
        logging.error(f"Errore durante l'elaborazione del messaggio: {e}")

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="anomaly-detector-service")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info("Anomaly Detector connesso a MQTT Broker. Ascolto su: " + TOPIC_INPUT)
            client.subscribe(TOPIC_INPUT)
        else:
            logging.error(f"Connessione fallita con codice {rc}")

    client.on_connect = on_connect
    client.on_message = on_message

    connected = False
    while not connected:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            connected = True
        except Exception:
            logging.warning("Broker non ancora pronto, attendo 3 secondi...")
            import time
            time.sleep(3)

    client.loop_forever()

if __name__ == "__main__":
    main()
