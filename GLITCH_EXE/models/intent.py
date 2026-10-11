from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InteractionIntent:
    """
    Represents what the user wants GLITCH to do.

    Different input systems can produce the same intent.

    Example:

        Voice:
            "Glitch open system matrix"

        Gesture:
            swipe left

        Both can become:

            action = "NAVIGATE"
            target = "SYSTEM_MATRIX"
    """

    action: str

    target: str | None = None

    source: str = "UNKNOWN"

    confidence: float = 1.0

    data: dict[str, Any] = field(
        default_factory=dict
    )

    timestamp: datetime = field(
        default_factory=datetime.now
    )


    def normalized_action(self):

        return (
            self.action
            .strip()
            .upper()
        )


    def normalized_target(self):

        if self.target is None:

            return None


        return (
            self.target
            .strip()
            .upper()
        )
