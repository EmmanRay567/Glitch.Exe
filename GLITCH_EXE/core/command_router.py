class CommandRouter:

    def __init__(self):
        self._commands = {}

    def register(
        self,
        command_name: str,
        factory
    ):
        key = (
            command_name
            .strip()
            .upper()
        )

        self._commands[key] = factory

    def execute(
        self,
        command_name: str,
        *args,
        **kwargs
    ):
        key = (
            command_name
            .strip()
            .upper()
        )

        factory = (
            self._commands.get(
                key
            )
        )

        if factory is None:
            raise ValueError(
                f"Unknown GLITCH command: "
                f"{command_name}"
            )

        command = factory(
            *args,
            **kwargs
        )

        return (
            command.execute()
        )

    def has_command(
        self,
        command_name: str
    ) -> bool:
        return (
            command_name
            .strip()
            .upper()
            in self._commands
        )
