import json
import logging
import os

class JSONStateManager:
    """Gestisce la persistenza dello stato in un file JSON atomico."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def load_state(self) -> dict:
        if not os.path.exists(self.filepath):
            logging.info(f"Nessun file di stato trovato in '{self.filepath}'. Avvio da zero.")
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                logging.info(f"Stato caricato con successo da '{self.filepath}' ({len(data)} chiavi registrate).")
                return data
        except Exception as e:
            logging.error(f"Errore durante il caricamento dello stato: {e}. Si riparte da vuoto.")
            return {}

    def save_state(self, state_dict: dict):
        """Scrittura atomica per evitare file corrotti in caso di crash improvviso."""
        temp_file = f"{self.filepath}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2)
            os.replace(temp_file, self.filepath)
        except Exception as e:
            logging.error(f"Errore durante il salvataggio dello stato su JSON: {e}")