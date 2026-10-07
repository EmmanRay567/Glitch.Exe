from abc import ABC


class BaseService(ABC):

    def __init__(
        self,
        event_bus=None
    ):
        self.event_bus = event_bus

    def publish(
        self,
        event
    ):
        if self.event_bus is not None:
            self.event_bus.publish(
                event
            )
