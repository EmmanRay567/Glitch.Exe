class ServiceContainer:

    def __init__(self):
        self._services = {}

    def register(
        self,
        name: str,
        service
    ):
        key = (
            name
            .strip()
            .lower()
        )

        self._services[key] = service

    def get(
        self,
        name: str
    ):
        key = (
            name
            .strip()
            .lower()
        )

        if key not in self._services:
            raise KeyError(
                f"Service not registered: {name}"
            )

        return self._services[key]

    def has(
        self,
        name: str
    ) -> bool:
        return (
            name
            .strip()
            .lower()
            in self._services
        )
