import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.data_router import router as data_router
from mqtt.client import MqttClientManager
from mqtt.listener import MqttDataListener
from storage.repository import DataRepository
from services.data_service import DataService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Funzione in cui il codice prima di yield viene eseguito all'avvio del servizio/applicazione,
# ovvero prima che FastAPI cominci ad accettare richieste;
# tutto il codice della funzione che sta dopo yield viene eseguito al termine del servizio.
@asynccontextmanager
async def lifespan(app: FastAPI):
    shutdown_event = threading.Event()

    repository = DataRepository()
    repository.initialize()

    service = DataService(repository=repository)

    app.state.repository = repository

    mqtt_manager = MqttClientManager()
    MqttDataListener(client=mqtt_manager.client, service=service)

    def _connect_and_start():
        if mqtt_manager.connect_with_retry(shutdown_event):
            mqtt_manager.start_loop()

    # Crea la connessione al broker in un thread separato
    # daemon = True vuol dire che il thread si chiude in automatico
    # quando il processo principale si chiude, senza doverlo gestire esplicitamente.
    connect_thread = threading.Thread(target=_connect_and_start, daemon=True)
    connect_thread.start()

    yield

    # In ordine:
    # - diciamo al thread di fermarsi;
    # - aspettiamo al max 5 sec che termini gracefully;
    # - disconnettiamo il client MQTT.
    shutdown_event.set()
    connect_thread.join(timeout=5)
    mqtt_manager.stop()

# Crea l'app FastAPI e registra il router
app = FastAPI(title="Data Service", lifespan=lifespan)
app.include_router(data_router)

# Include l'endpoint /health
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
