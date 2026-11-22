import json
from dataclasses import asdict
import redis

import config
from domain.sensor import SensorStatus


class SensorRepository:
    REDIS_KEY = "sensors:status"

    def __init__(self):
        self._client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            decode_responses=True,
        )

    def save(self, sensor: SensorStatus) -> None:
        self._client.hset(self.REDIS_KEY, sensor.device_id, json.dumps(asdict(sensor)))

    def find_by_id(self, device_id: str) -> SensorStatus | None:
        raw = self._client.hget(self.REDIS_KEY, device_id)
        if not raw:
            return None
        return SensorStatus(**json.loads(raw))

    def find_all(self) -> list[SensorStatus]:
        raw_map = self._client.hgetall(self.REDIS_KEY)
        return [SensorStatus(**json.loads(val)) for val in raw_map.values()]