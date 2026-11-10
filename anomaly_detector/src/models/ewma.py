import math

class EWMAOnlineStats:
    """Calcola media e varianza pesate esponenzialmente (EWMA / EWMSD)."""
    def __init__(self, alpha: float = 0.1, count: int = 0, mean: float = 0.0, var: float = 0.0):
        self.alpha = alpha
        self.count = count
        self.mean = mean
        self.var = var

    def update(self, x: float):
        self.count += 1
        if self.count == 1:
            self.mean = x
            self.var = 0.0
        else:
            delta = x - self.mean
            self.mean += self.alpha * delta
            # Aggiornamento varianza esponenziale
            self.var = (1 - self.alpha) * (self.var + self.alpha * (delta ** 2))

    @property
    def std_dev(self) -> float:
        return math.sqrt(max(0.0, self.var))

    def to_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "count": self.count,
            "mean": self.mean,
            "var": self.var
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EWMAOnlineStats":
        return cls(
            alpha=data.get("alpha", 0.1),
            count=data.get("count", 0),
            mean=data.get("mean", 0.0),
            var=data.get("var", 0.0)
        )