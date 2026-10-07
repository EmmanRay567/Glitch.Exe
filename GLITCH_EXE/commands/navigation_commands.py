from commands.base_command import Command


class NavigationCommand(Command):

    def __init__(
        self,
        navigation_controller,
        destination: str
    ):
        self.navigation_controller = (
            navigation_controller
        )

        self.destination = (
            destination.upper()
        )

    def execute(self):
        return (
            self.navigation_controller
            .navigate(
                self.destination
            )
        )
