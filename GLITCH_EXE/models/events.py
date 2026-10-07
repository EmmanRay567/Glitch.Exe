from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class GlitchEvent:
    name: str
    data: dict[str, Any] = field(
        default_factory=dict
    )
    source: str = "GLITCH"
    timestamp: datetime = field(
        default_factory=datetime.now
    )


@dataclass
class NavigationEvent(GlitchEvent):
    target: str = "HOME"


@dataclass
class SystemEvent(GlitchEvent):
    severity: str = "INFO"


@dataclass
class SecurityEvent(GlitchEvent):
    severity: str = "LOW"


@dataclass
class VoiceEvent(GlitchEvent):
    transcript: str = ""


@dataclass
class GestureEvent(GlitchEvent):
    gesture: str = ""
