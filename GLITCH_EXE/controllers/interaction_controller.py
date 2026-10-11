from models.intent import InteractionIntent
from models.events import GlitchEvent


class InteractionController:
    """
    Central interaction layer for GLITCH.EXE.

    Receives intents from:
    - voice
    - gestures
    - mouse
    - keyboard
    - future agents

    Then routes them into the existing
    CommandRouter / service architecture.
    """

    def __init__(
        self,
        command_router,
        event_bus=None
    ):

        self.command_router = (
            command_router
        )

        self.event_bus = (
            event_bus
        )

        self.interaction_history = []


    # ---------------------------------------------------------
    # HANDLE INTENT
    # ---------------------------------------------------------

    def handle_intent(
        self,
        intent: InteractionIntent
    ):

        action = (
            intent
            .normalized_action()
        )

        target = (
            intent
            .normalized_target()
        )


        self.record_interaction(
            intent
        )


        # -----------------------------------------------------
        # NAVIGATION
        # -----------------------------------------------------

        if action == "NAVIGATE":

            if target is None:

                return False


            result = (
                self.command_router
                .execute(
                    "NAVIGATE",
                    target
                )
            )


            self.publish_interaction_event(
                intent,
                result
            )


            return result


        # -----------------------------------------------------
        # UNKNOWN INTENT
        # -----------------------------------------------------

        self.publish_interaction_event(
            intent,
            False
        )


        return False


    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------

    def record_interaction(
        self,
        intent
    ):

        self.interaction_history.append(
            intent
        )


        # Prevent unlimited memory growth.
        if len(
            self.interaction_history
        ) > 100:

            self.interaction_history = (
                self.interaction_history[
                    -100:
                ]
            )


    def get_recent_interactions(
        self,
        limit=10
    ):

        return (
            self.interaction_history[
                -limit:
            ]
        )


    # ---------------------------------------------------------
    # EVENT BUS
    # ---------------------------------------------------------

    def publish_interaction_event(
        self,
        intent,
        handled
    ):

        if self.event_bus is None:

            return


        event = GlitchEvent(

            name="INTERACTION_PROCESSED",

            source="InteractionController",

            data={

                "action":
                    intent.normalized_action(),

                "target":
                    intent.normalized_target(),

                "source":
                    intent.source,

                "confidence":
                    intent.confidence,

                "handled":
                    handled,
            }
        )


        self.event_bus.publish(
            event
        )
