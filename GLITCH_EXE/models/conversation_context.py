from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: datetime = field(
        default_factory=datetime.now
    )


@dataclass
class ConversationContext:
    current_topic: str | None = None
    active_entity_type: str | None = None
    active_entity_name: str | None = None
    active_metric: str | None = None
    active_value: str | None = None

    recent_turns: list[ConversationTurn] = field(
        default_factory=list
    )

    max_turns: int = 8

    def add_turn(
        self,
        role,
        content
    ):

        content = (
            str(content)
            .strip()
        )

        if not content:
            return

        self.recent_turns.append(
            ConversationTurn(
                role=role,
                content=content
            )
        )

        if len(
            self.recent_turns
        ) > self.max_turns:

            self.recent_turns = (
                self.recent_turns[
                    -self.max_turns:
                ]
            )

    def recent_summary(
        self
    ):

        if not self.recent_turns:
            return ""

        lines = []

        for turn in self.recent_turns:

            label = (
                "USER"
                if turn.role == "user"
                else "GLITCH"
            )

            lines.append(
                f"{label}: {turn.content}"
            )

        return "\n".join(
            lines
        )

