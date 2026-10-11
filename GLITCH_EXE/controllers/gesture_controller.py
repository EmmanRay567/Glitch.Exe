from models.events import GestureEvent


class GestureController:
    """
    Converts recognized gestures into GLITCH actions.

    HandTracker detects physical movement.
    GestureController decides what that movement means.
    """

    def __init__(
        self,
        command_router,
        event_bus=None
    ):
        self.command_router = command_router
        self.event_bus = event_bus


    # ---------------------------------------------------------
    # EVENT PUBLISHING
    # ---------------------------------------------------------

    def publish_gesture_event(
        self,
        gesture,
        current_mode,
        handled
    ):

        if self.event_bus is None:

            return


        event = GestureEvent(

            name="GESTURE_DETECTED",

            source="GestureController",

            gesture=gesture,

            current_mode=current_mode,

            handled=handled,

            data={
                "gesture": gesture,
                "current_mode": current_mode,
                "handled": handled,
            }
        )


        self.event_bus.publish(
            event
        )


    # ---------------------------------------------------------
    # SWIPE LEFT
    # ---------------------------------------------------------

    def swipe_left(
        self,
        current_mode
    ):

        current_mode = (
            current_mode
            .strip()
            .upper()
        )


        handled = False


        if current_mode == "HOME":

            handled = (
                self.command_router
                .execute(
                    "NAVIGATE",
                    "SYSTEM_MATRIX"
                )
            )


        self.publish_gesture_event(
            "SWIPE_LEFT",
            current_mode,
            handled
        )


        return handled


    # ---------------------------------------------------------
    # SWIPE RIGHT
    # ---------------------------------------------------------

    def swipe_right(
        self,
        current_mode
    ):

        current_mode = (
            current_mode
            .strip()
            .upper()
        )


        handled = False


        if current_mode == "SYSTEM_MATRIX":

            handled = (
                self.command_router
                .execute(
                    "NAVIGATE",
                    "HOME"
                )
            )


        self.publish_gesture_event(
            "SWIPE_RIGHT",
            current_mode,
            handled
        )


        return handled