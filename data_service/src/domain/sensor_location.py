from dataclasses import dataclass

# Nota: non è detto che siano lat e long a definire la posizione,
# bisogna capire con il frontend

# Tutti i valori sono nullable (opzionali) perché non è detto
# che il sensore abbia sicuramente una posizione associata
@dataclass
class SensorLocation:
    device_id: str
    lat: float | None
    lon: float | None
