from collections import defaultdict
from typing import Callable

from models.events import GlitchEvent


class EventBus:

    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(
        self,
        event_name: str,
        callback: Callable
    ):
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(
                callback
            )

    def unsubscribe(
        self,
        event_name: str,
        callback: Callable
    ):
        callbacks = self._subscribers.get(
            event_name,
            []
        )

        if callback in callbacks:
            callbacks.remove(
                callback
            )

    def publish(
        self,
        event: GlitchEvent
    ):
        callbacks = list(
            self._subscribers.get(
                event.name,
                []
            )
        )

        wildcard_callbacks = list(
            self._subscribers.get(
                "*",
                []
            )
        )

        for callback in (
            callbacks
            + wildcard_callbacks
        ):
            try:
                callback(
                    event
                )

            except Exception as error:
                print(
                    f"EVENT BUS ERROR // "
                    f"{event.name} // "
                    f"{error}"
                )

    def clear(self):
        self._subscribers.clear()

    def subscriber_count(
        self,
        event_name: str
    ) -> int:
        return len(
            self._subscribers.get(
                event_name,
                []
            )
        )
