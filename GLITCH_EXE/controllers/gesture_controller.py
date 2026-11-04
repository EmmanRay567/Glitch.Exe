from models.events import GestureEvent
from models.intent import InteractionIntent


# Order of the sections you move through with vertical swipes.
SECTION_DECK = (
    "HOME",
    "CHAT",
    "CREATE",
    "SEARCH",
    "CODE",
    "APPS",
    "SETTINGS",
)

# The matrices hang off HOME, so a vertical swipe from a matrix
# behaves as if you were on HOME.
MATRIX_PARENT = {
    "SYSTEM_MATRIX": "HOME",
    "SECURITY_MATRIX": "HOME",
    "CAREER_MATRIX": "HOME",
}


class GestureController:
    """
    Converts recognized gestures into GLITCH intents.

    Section deck (swipe UP = next section, swipe DOWN = previous,
    wraps around at both ends):
        HOME -> CHAT -> CREATE -> SEARCH -> CODE -> APPS -> SETTINGS

    Matrix swipe chain (left / right, from HOME only):
        HOME
          <- / ->
        SYSTEM_MATRIX
          <- / ->
        SECURITY_MATRIX
          <- / ->
        CAREER_MATRIX

    Pinch-click:
        The holographic fingertip hovers a HUD button and a pinch
        clicks it. The click itself is performed by the main window
        (button.click()); this controller records it as a gesture
        event so the rest of GLITCH can see it.
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
    # NAVIGATION HELPER
    # ---------------------------------------------------------

    def _navigate(
        self,
        target,
        gesture,
        current_mode
    ):

        intent = InteractionIntent(

            action="NAVIGATE",

            target=target,

            source="GESTURE",

            confidence=1.0,

            data={
                "gesture": gesture,
                "current_mode": current_mode,
                "destination": target,
            }
        )

        return (
            self.interaction_controller
            .handle_intent(
                intent
            )
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

            handled = self._navigate(
                "SYSTEM_MATRIX",
                "SWIPE_LEFT",
                current_mode
            )

        elif current_mode == "SYSTEM_MATRIX":

            handled = self._navigate(
                "SECURITY_MATRIX",
                "SWIPE_LEFT",
                current_mode
            )

        elif current_mode == "SECURITY_MATRIX":

            handled = self._navigate(
                "CAREER_MATRIX",
                "SWIPE_LEFT",
                current_mode
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

        if current_mode == "CAREER_MATRIX":

            handled = self._navigate(
                "SECURITY_MATRIX",
                "SWIPE_RIGHT",
                current_mode
            )

        elif current_mode == "SECURITY_MATRIX":

            handled = self._navigate(
                "SYSTEM_MATRIX",
                "SWIPE_RIGHT",
                current_mode
            )

        elif current_mode == "SYSTEM_MATRIX":

            handled = self._navigate(
                "HOME",
                "SWIPE_RIGHT",
                current_mode
            )

        self.publish_gesture_event(
            "SWIPE_RIGHT",
            current_mode,
            handled
        )

        return handled


    # ---------------------------------------------------------
    # PINCH CLICK
    # ---------------------------------------------------------

    def pinch_click(
        self,
        target,
        current_mode,
        handled=True
    ):

        """
        Record a pinch-click on a HUD control.

        target        -- label of the button that was clicked
        current_mode  -- page the HUD was on when it was clicked
        handled       -- True when a button was actually hit
        """

        target = (
            str(target)
            .strip()
            .upper()
        ) or "HUD CONTROL"

        current_mode = (
            str(current_mode)
            .strip()
            .upper()
        )

        self.publish_gesture_event(
            f"PINCH_CLICK:{target}",
            current_mode,
            bool(handled)
        )

        return bool(handled)


    # ---------------------------------------------------------
    # SWIPE UP / DOWN (section deck)
    # ---------------------------------------------------------

    def next_section(
        self,
        current_mode,
        step
    ):

        current_mode = (
            str(current_mode)
            .strip()
            .upper()
        )

        current_mode = MATRIX_PARENT.get(
            current_mode,
            current_mode
        )

        if current_mode not in SECTION_DECK:

            return "HOME"

        index = SECTION_DECK.index(
            current_mode
        )

        return SECTION_DECK[
            (index + step) % len(SECTION_DECK)
        ]


    def swipe_up(
        self,
        current_mode
    ):

        current_mode = (
            str(current_mode)
            .strip()
            .upper()
        )

        target = self.next_section(
            current_mode,
            1
        )

        handled = self._navigate(
            target,
            "SWIPE_UP",
            current_mode
        )

        self.publish_gesture_event(
            "SWIPE_UP",
            current_mode,
            handled
        )

        return handled


    def swipe_down(
        self,
        current_mode
    ):

        current_mode = (
            str(current_mode)
            .strip()
            .upper()
        )

        target = self.next_section(
            current_mode,
            -1
        )

        handled = self._navigate(
            target,
            "SWIPE_DOWN",
            current_mode
        )

        self.publish_gesture_event(
            "SWIPE_DOWN",
            current_mode,
            handled
        )

        return handled