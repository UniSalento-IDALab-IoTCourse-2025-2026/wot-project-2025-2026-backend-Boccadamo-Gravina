import os

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)
TOPIC_INPUT = os.getenv("MQTT_TOPIC_INPUT", "telemetry/air_quality")
TOPIC_ANOMALY = os.getenv("MQTT_TOPIC_ANOMALY", "telemetry/anomalies")

# Parametri EWMA / Anomaly Detection
ALPHA = float(os.getenv("EWMA_ALPHA", 0.1))            # Fattore di smorzamento (0 < alpha <= 1)
WARMUP_SAMPLES = int(os.getenv("WARMUP_SAMPLES", 15))   # Campioni minimi prima di segnalare
Z_THRESHOLD = float(os.getenv("Z_THRESHOLD", 3.0))      # Soglia Z-Score
STATE_FILE_PATH = os.getenv("STATE_FILE_PATH", "data/state.json")