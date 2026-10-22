from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LocationState:
    latitude: float = 0.0
    longitude: float = 0.0
    accuracy_meters: float | None = None
    source: str = "UNKNOWN"
    available: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def coordinates(self):
        return (
            self.latitude,
            self.longitude,
        )
