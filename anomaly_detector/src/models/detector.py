from models.ewma import EWMAOnlineStats

class OnlineAnomalyDetector:
    def __init__(self, alpha: float, warmup_samples: int, z_threshold: float, initial_state: dict | None = None):
        self.alpha = alpha
        self.warmup_samples = warmup_samples
        self.z_threshold = z_threshold
        
        # Mappa: "device_id:pollutant" -> EWMAOnlineStats
        self.stats: dict[str, EWMAOnlineStats] = {}
        if initial_state:
            self.load_state(initial_state)


    def load_state(self, raw_state: dict) -> None:
        for key, data in raw_state.items():
            self.stats[key] = EWMAOnlineStats.from_dict(data)

    def dump_state(self) -> dict:
        return {key: st.to_dict() for key, st in self.stats.items()}

    def process_reading(self, device_id: str, pollutant: str, value: float) -> dict:
        key = f"{device_id}:{pollutant}"
        if key not in self.stats:
            self.stats[key] = EWMAOnlineStats(alpha=self.alpha)

        st = self.stats[key]
        is_anomaly = False
        z_score = 0.0

        if st.count >= self.warmup_samples and st.std_dev > 0:
            z_score = abs(value - st.mean) / st.std_dev
            if z_score > self.z_threshold:
                is_anomaly = True

        # Aggiorna lo stato EWMA
        st.update(value)

        return {
            "value": value,
            "mean": round(st.mean, 2),
            "std_dev": round(st.std_dev, 2),
            "z_score": round(z_score, 2),
            "is_anomaly": is_anomaly,
            "status": "learning" if st.count <= self.warmup_samples else ("ANOMALY" if is_anomaly else "NORMAL"),
        }