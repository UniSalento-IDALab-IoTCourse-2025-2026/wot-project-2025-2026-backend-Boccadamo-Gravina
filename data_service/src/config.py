import os

def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Manca la variabile d'ambiente: {name}")
    return value

# Prendo le env vars e le faccio diventare costanti

MQTT_BROKER = _required_env("MQTT_BROKER")
MQTT_PORT = int(_required_env("MQTT_PORT"))
MQTT_USERNAME = _required_env("MQTT_USERNAME")
MQTT_PASSWORD = _required_env("MQTT_PASSWORD")
MQTT_CLIENT_ID = _required_env("MQTT_CLIENT_ID")
MQTT_TOPIC_TELEMETRY = _required_env("MQTT_TOPIC_TELEMETRY")
MQTT_TOPIC_LOCATION = _required_env("MQTT_TOPIC_LOCATION")

TIMESCALE_HOST = _required_env("TIMESCALE_HOST")
TIMESCALE_PORT = int(_required_env("TIMESCALE_PORT"))
TIMESCALE_USER = _required_env("TIMESCALE_USER")
TIMESCALE_PASSWORD = _required_env("TIMESCALE_PASSWORD")
TIMESCALE_DB = _required_env("TIMESCALE_DB")

OIDC_JWKS_URL = _required_env("OIDC_JWKS_URL")
OIDC_ISSUER = _required_env("OIDC_ISSUER").rstrip("/")
OIDC_AUDIENCE = _required_env("OIDC_AUDIENCE")
