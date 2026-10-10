class GestureController:
    """
    Converts recognized gestures into GLITCH actions.

    The hand tracker detects movement.
    This controller decides what that movement means.
    """

    def __init__(
        self,
        command_router,
        event_bus=None
    ):
        self.command_router = command_router
        self.event_bus = event_bus

    def swipe_left(
        self,
        current_mode
    ):
        """
        Handle a left swipe.
        """

        current_mode = (
            current_mode
            .strip()
            .upper()
        )

        if current_mode == "HOME":

            return self.command_router.execute(
                "NAVIGATE",
                "SYSTEM_MATRIX"
            )

        return False

    def swipe_right(
        self,
        current_mode
    ):
        """
        Handle a right swipe.
        """

        current_mode = (
            current_mode
            .strip()
            .upper()
        )

        if current_mode == "SYSTEM_MATRIX":

            return self.command_router.execute(
                "NAVIGATE",
                "HOME"
            )

        return False
