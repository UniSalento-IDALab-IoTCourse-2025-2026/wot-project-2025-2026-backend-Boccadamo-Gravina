import logging
import psycopg2
import psycopg2.extras
import config   # File config.py creato per le env vars
from domain.measurement import Measurement
from domain.sensor_location import SensorLocation

logger = logging.getLogger(__name__)

# Funzione nostra per ottenere una connessione al TimescaleDB
def _get_connection():
    return psycopg2.connect(
        host=config.TIMESCALE_HOST,
        port=config.TIMESCALE_PORT,
        user=config.TIMESCALE_USER,
        password=config.TIMESCALE_PASSWORD,
        dbname=config.TIMESCALE_DB,
    )

class DataRepository:

    # Metodo che verrà chiamato una volta nel main per creare le tabelle se non esistono già
    # Converte inoltre la tabella measurements in hypertable per sfruttare le funzionalità di TimescaleDB
    def initialize(self) -> None:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sensor_locations (
                        device_id   TEXT PRIMARY KEY,
                        lat         DOUBLE PRECISION,
                        lon         DOUBLE PRECISION
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS measurements (
                        time        TIMESTAMPTZ     NOT NULL,
                        device_id   TEXT            NOT NULL,
                        no2         DOUBLE PRECISION,
                        pm25        DOUBLE PRECISION,
                        o3          DOUBLE PRECISION,
                        pah         DOUBLE PRECISION,
                        temperature DOUBLE PRECISION,
                        humidity    DOUBLE PRECISION,
                        lat         DOUBLE PRECISION,
                        lon         DOUBLE PRECISION
                    )
                """)

                # Trasforma la tabella measurements in hypertable per sfruttare le funzionalità di TimescaleDB
                # Di default TimescaleDB crea un hypertable partizionando i dati usando il campo time, che è quello che ci serve
                # Di default la partizione dovrebbe essere di 7 giorni, ma possiamo cambiarla se vogliamo
                cur.execute("""
                    SELECT create_hypertable(
                        'measurements', 'time',
                        if_not_exists => TRUE
                    )
                """)
        logger.info("Tabelle inizializzate correttamente.")

    # upsert è un pattern in cui, se il record esiste già, lo aggiorna con lat e long
    # nuove piuttosto che dare errore, altrimenti lo inserisce
    def upsert_location(self, location: SensorLocation) -> None:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sensor_locations (device_id, lat, lon)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (device_id) DO UPDATE
                        SET lat = EXCLUDED.lat,
                            lon = EXCLUDED.lon
                """, (location.device_id, location.lat, location.lon))

    # Riceve la misurazione dal sensore e la salva nel db
    def save_measurement(self, measurement: Measurement) -> None:
        with _get_connection() as conn:
            with conn.cursor() as cur:

                # Legge la posizione corrente del sensore da sensor_locations usando una SELECT.
                # Se il sensore esiste, restituisce lat e long, altrimenti None.
                cur.execute(
                    "SELECT lat, lon FROM sensor_locations WHERE device_id = %s",
                    (measurement.device_id,)
                )

                # Leggiamo la riga restituita dalla query
                row = cur.fetchone()
                lat = row[0] if row else None
                lon = row[1] if row else None

                # Inserisce la misurazione nella tabella measurements, includendo lat e long se presenti
                cur.execute("""
                    INSERT INTO measurements
                        (time, device_id, no2, pm25, o3, pah, temperature, humidity, lat, lon)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    measurement.time,
                    measurement.device_id,
                    measurement.no2,
                    measurement.pm25,
                    measurement.o3,
                    measurement.pah,
                    measurement.temperature,
                    measurement.humidity,
                    lat,
                    lon,
                ))

    # Recupera le misurazioni più recenti dal database
    # Di default restituisce le ultime limit (di default =100) misurazioni,
    # ma possiamo cambiare il limite passando un diverso limit come argomento
    def get_latest_measurements(self, limit: int = 100) -> list[dict]:
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

                # Restituisce le ultime limit misurazioni ordinate per tempo decrescente,
                # quindi le più recenti prima, e le mette in una lista di dizionari
                cur.execute("""
                    SELECT * FROM measurements
                    ORDER BY time DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]

    # Stessa funzione della precedente funzione, ma filtra le misurazioni per device_id,
    # quindi restituisce solo le misurazioni di un sensore specifico
    def get_measurements_by_device(self, device_id: str, limit: int = 100) -> list[dict]:
        with _get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM measurements
                    WHERE device_id = %s
                    ORDER BY time DESC
                    LIMIT %s
                """, (device_id, limit))
                return [dict(row) for row in cur.fetchall()]
