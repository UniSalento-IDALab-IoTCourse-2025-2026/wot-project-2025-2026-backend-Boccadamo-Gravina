import logging
from models.detector import OnlineAnomalyDetector
from storage.state_manager import JSONStateManager
from mqtt.publisher import MqttAnomalyPublisher

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    def __init__(
        self,
        detector: OnlineAnomalyDetector,
        state_manager: JSONStateManager,
        publisher: MqttAnomalyPublisher,
    ):
        self._detector = detector
        self._state_manager = state_manager
        self._publisher = publisher
        self._publisher = publisher

    def evaluate_device_telemetry(self, device_id: str, timestamp: str, sensors: dict[str, float]) -> None:
        if not sensors:
            return

        anomalies_detected = {}
        analysis_summary = {}

        for pollutant, val in sensors.items():
            res = self._detector.process_reading(device_id, pollutant, float(val))
            analysis_summary[pollutant] = res
            if res["is_anomaly"]:
                anomalies_detected[pollutant] = res

        # Persistenza singola per l'intero batch di sensori
        self._state_manager.save_state(self._detector.dump_state())

        logger.info(
            f"[{device_id}] Campionamento elaborato. Stato: "
            f"{ {k: v['status'] for k, v in analysis_summary.items()} }"
        )

        if anomalies_detected:
            self._publisher.publish_anomaly(device_id, timestamp, anomalies_detected)