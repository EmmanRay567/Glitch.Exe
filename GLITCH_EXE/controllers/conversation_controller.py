import time


class ConversationController:
    """
    Manages GLITCH's temporary conversational presence.

    The wake word opens a session. While that session is active,
    follow-up speech is accepted without requiring "Glitch" again.
    """

    def __init__(
        self,
        timeout_seconds=40.0
    ):

        self.timeout_seconds = float(
            timeout_seconds
        )

        self.active = False
        self.last_interaction_time = None
        self.turn_count = 0


    # ---------------------------------------------------------
    # SESSION STATE
    # ---------------------------------------------------------

    def start_session(self):

        self.active = True

        self.last_interaction_time = (
            time.time()
        )

        self.turn_count = 0


    def end_session(self):

        self.active = False
        self.last_interaction_time = None
        self.turn_count = 0


    def touch(self):

        if not self.active:
            return

        self.last_interaction_time = (
            time.time()
        )


    def is_active(self):

        if not self.active:
            return False


        if self.last_interaction_time is None:

            self.end_session()

            return False


        elapsed = (
            time.time()
            - self.last_interaction_time
        )


        if elapsed > self.timeout_seconds:

            self.end_session()

            return False


        return True


    # ---------------------------------------------------------
    # LANGUAGE HELPERS
    # ---------------------------------------------------------

    def is_end_phrase(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
            .strip(" ,.!?:;-")
        )


        end_phrases = {
            "that's all",
            "that is all",
            "nothing else",
            "no that's all",
            "no that is all",
            "stop listening",
            "you can stop listening",
            "thanks glitch",
            "thank you glitch",
            "thanks",
            "thank you",
            "we're done",
            "we are done",
            "that's it",
            "that is it",
        }


        return (
            command in end_phrases
        )


    def ending_response(self):

        return (
            "Alright. I'll be here when you need me."
        )


    def decorate_confirmation(
        self,
        message
    ):
        """
        Add a light conversational acknowledgement to short
        command confirmations while keeping factual answers clean.
        """

        self.turn_count += 1

        cleaned = (
            message
            .strip()
        )


        # Long/factual responses should not get unnecessary filler.
        if len(cleaned) > 120:

            return cleaned


        # Avoid decorating irreversible power execution messages.
        lowered = cleaned.lower()

        if (
            "powering off" in lowered
            or "restarting the computer" in lowered
        ):

            return cleaned


        variants = [
            "Done.",
            "Got it.",
            "All set.",
            "Done. Anything else?",
            "Got it. What else can I do?",
        ]


        prefix = (
            variants[
                (self.turn_count - 1)
                % len(variants)
            ]
        )


        # If the existing response is already naturally complete,
        # preserve its useful content after the acknowledgement.
        return (
            f"{prefix} {cleaned}"
        )

