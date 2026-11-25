from dataclasses import dataclass

# Utilizza gli stessi nomi dell'edge
# Tutti i valore sono nullable (opzionali) perché non è detto
# che un sensore riesca a rilevare tutti i parametri in ogni misurazione 
@dataclass
class Measurement:
    time: str
    device_id: str
    no2: float | None
    pm25: float | None
    o3: float | None
    pah: float | None
    temperature: float | None
    humidity: float | None
