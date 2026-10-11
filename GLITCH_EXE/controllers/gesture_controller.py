from models.events import GestureEvent
from models.intent import InteractionIntent


class GestureController:
    """
    Converts recognized gestures into GLITCH intents.

    HandTracker detects physical movement.
    GestureController decides what the movement means.
    InteractionController decides how GLITCH executes it.
    """

    def __init__(
        self,
        interaction_controller,
        event_bus=None
    ):
        self.interaction_controller = (
            interaction_controller
        )

        self.event_bus = (
            event_bus
        )


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

            intent = InteractionIntent(

                action="NAVIGATE",

                target="SYSTEM_MATRIX",

                source="GESTURE",

                confidence=1.0,

                data={
                    "gesture": "SWIPE_LEFT",
                    "current_mode": current_mode,
                }
            )


            handled = (
                self.interaction_controller
                .handle_intent(
                    intent
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

            intent = InteractionIntent(

                action="NAVIGATE",

                target="HOME",

                source="GESTURE",

                confidence=1.0,

                data={
                    "gesture": "SWIPE_RIGHT",
                    "current_mode": current_mode,
                }
            )


            handled = (
                self.interaction_controller
                .handle_intent(
                    intent
                )
            )


        self.publish_gesture_event(
            "SWIPE_RIGHT",
            current_mode,
            handled
        )


        return handled