import os

def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Manca la variabile d'ambiente: {name}")
    return value

MQTT_BROKER = _required_env("MQTT_BROKER")
MQTT_PORT = int(_required_env("MQTT_PORT"))
MQTT_USERNAME = _required_env("MQTT_USERNAME")
MQTT_PASSWORD = _required_env("MQTT_PASSWORD")
MQTT_CLIENT_ID = _required_env("MQTT_CLIENT_ID")
TOPIC_STATUS = _required_env("MQTT_TOPIC_STATUS")
TOPIC_LOCATION = _required_env("MQTT_TOPIC_LOCATION")

REDIS_HOST = _required_env("REDIS_HOST")
REDIS_PORT = int(_required_env("REDIS_PORT"))

OIDC_JWKS_URL = _required_env("OIDC_JWKS_URL")
OIDC_ISSUER = _required_env("OIDC_ISSUER").rstrip("/")
OIDC_AUDIENCE = _required_env("OIDC_AUDIENCE")
