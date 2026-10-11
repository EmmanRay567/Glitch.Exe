from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# =========================================================
# BASE EVENT
# =========================================================

@dataclass
class GlitchEvent:
    """
    Base event used by the GLITCH EventBus.

    Every event has:
    - a name
    - optional data
    - a source
    - a timestamp
    """

    name: str

    data: dict[str, Any] = field(
        default_factory=dict
    )

    source: str = "GLITCH"

    timestamp: datetime = field(
        default_factory=datetime.now
    )


# =========================================================
# NAVIGATION EVENT
# =========================================================

@dataclass
class NavigationEvent(
    GlitchEvent
):

    target: str = "HOME"


# =========================================================
# SYSTEM EVENT
# =========================================================

@dataclass
class SystemEvent(
    GlitchEvent
):

    severity: str = "INFO"


# =========================================================
# SECURITY EVENT
# =========================================================

@dataclass
class SecurityEvent(
    GlitchEvent
):

    severity: str = "LOW"


# =========================================================
# VOICE EVENT
# =========================================================

@dataclass
class VoiceEvent(
    GlitchEvent
):

    transcript: str = ""

    command: str = ""

    handled: bool = False

    action_type: str | None = None


# =========================================================
# GESTURE EVENT
# =========================================================

@dataclass
class GestureEvent(
    GlitchEvent
):

    gesture: str = ""

    current_mode: str = ""

    handled: bool = False


# =========================================================
# APPLICATION EVENT
# =========================================================

@dataclass
class ApplicationEvent(
    GlitchEvent
):

    app_key: str = ""

    action: str = ""

    success: bool = False


# =========================================================
# TELEMETRY EVENT
# =========================================================

@dataclass
class TelemetryEvent(
    GlitchEvent
):

    cpu_percent: float = 0.0

    memory_percent: float = 0.0

    network_status: str = "UNKNOWN"

    hostname: str = ""