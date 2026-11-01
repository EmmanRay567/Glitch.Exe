"""
controllers/conversation_controller.py

Manages GLITCH's conversational presence and its quick, local
"in character" lines: greetings when you wake it, acknowledgements
when it carries out a command, and sign-offs. These are instant (no
AI round-trip), so commands still feel snappy, but they vary, notice
the time of day, avoid repeating themselves, and tell the adaptive
context what GLITCH just did so the AI can refer back to it later
("Spotify's already open, sir").

The wake word opens a session. While that session is active,
follow-up speech is accepted without requiring "Glitch" again.
"""

import random
import time
from collections import deque
from datetime import datetime


class ConversationController:

    def __init__(
        self,
        timeout_seconds=40.0,
        adaptive_context_service=None
    ):

        self.timeout_seconds = float(
            timeout_seconds
        )

        self.adaptive_context_service = (
            adaptive_context_service
        )

        self.active = False
        self.last_interaction_time = None
        self.turn_count = 0

        # Across sessions (for "welcome back" style greetings).
        self.app_started = time.time()
        self.last_session_end = None
        self.sessions_this_run = 0

        # Recently used lines, so GLITCH doesn't parrot itself.
        self._recent_lines = deque(maxlen=6)

        # Last confirmed action, for "again?" remarks.
        self._last_action = None
        self._last_action_time = 0.0

        # One late-night remark per run is plenty.
        self._late_remark_made = False

        self._rng = random.Random()


    def attach_context(
        self,
        adaptive_context_service
    ):

        """Called once the adaptive context service exists."""

        self.adaptive_context_service = (
            adaptive_context_service
        )


    # ---------------------------------------------------------
    # SESSION STATE
    # ---------------------------------------------------------

    def start_session(self):

        self.active = True

        self.last_interaction_time = (
            time.time()
        )

        self.turn_count = 0

        self.sessions_this_run += 1


    def end_session(self):

        if self.active:

            self.last_session_end = time.time()

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
    # HELPERS
    # ---------------------------------------------------------

    def _title(self):

        service = self.adaptive_context_service

        if service is not None and hasattr(service, "address"):

            try:

                return service.address()

            except Exception:

                pass

        return "sir"


    def _pick(
        self,
        options
    ):

        """Random line that wasn't used recently."""

        title = self._title()

        lines = [
            option.replace("{title}", title)
            for option in options
        ]

        fresh = [
            line
            for line in lines
            if line not in self._recent_lines
        ]

        line = self._rng.choice(
            fresh or lines
        )

        self._recent_lines.append(line)

        return line


    @staticmethod
    def _hour():

        return datetime.now().hour


    def _note_action(
        self,
        message
    ):

        service = self.adaptive_context_service

        if service is not None and hasattr(service, "note_action"):

            try:

                service.note_action(message)

            except Exception:

                pass


    # ---------------------------------------------------------
    # WAKE
    # ---------------------------------------------------------

    def wake_response(self):

        """What GLITCH says when you only say its name."""

        hour = self._hour()

        long_absence = (
            self.last_session_end is None
            and self.sessions_this_run <= 1
        ) or (
            self.last_session_end is not None
            and time.time() - self.last_session_end > 2 * 3600
        )

        if long_absence:

            if hour < 5:

                return self._pick(
                    [
                        "Still up, {title}? What do you need?",
                        "Burning the midnight oil again, {title}. What can I do?",
                    ]
                )

            if hour < 12:

                return self._pick(
                    [
                        "Good morning, {title}.",
                        "Morning, {title}. What's first?",
                    ]
                )

            if hour < 17:

                return self._pick(
                    [
                        "Good afternoon, {title}.",
                        "Afternoon, {title}. What are we doing?",
                    ]
                )

            return self._pick(
                [
                    "Good evening, {title}.",
                    "Evening, {title}. What can I do for you?",
                ]
            )

        line = self._pick(
            [
                "{title}?",
                "Yes, {title}?",
                "Go ahead.",
                "I'm listening.",
                "At your service.",
                "What do you need?",
            ]
        )

        return line[:1].upper() + line[1:]


    # ---------------------------------------------------------
    # LANGUAGE HELPERS
    # ---------------------------------------------------------

    END_PHRASES = {
        "that's all",
        "that is all",
        "that's all for now",
        "that'll be all",
        "that will be all",
        "nothing else",
        "no that's all",
        "no that is all",
        "no thanks",
        "nope that's it",
        "stop listening",
        "you can stop listening",
        "thanks",
        "thank you",
        "thanks that's all",
        "thank you that's all",
        "we're done",
        "we are done",
        "that's it",
        "that is it",
        "goodnight",
        "good night",
        "see you later",
        "later",
        "go to sleep",
        "standby",
        "stand by",
    }


    def is_end_phrase(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
            .replace(",", " ")
            .strip(" .!?:;-")
        )

        words = [
            word
            for word in command.split()
            if word not in ("glitch", "buddy", "man")
        ]

        command = " ".join(words).strip(" .!?:;-")

        return (
            command in self.END_PHRASES
        )


    def ending_response(self):

        hour = self._hour()

        if hour < 5 or hour >= 23:

            return self._pick(
                [
                    "Get some sleep, {title}. I'll keep watch.",
                    "Goodnight, {title}. I'll hold the fort.",
                    "Rest up, {title}. Everything will still be here in the morning.",
                ]
            )

        return self._pick(
            [
                "Alright. I'll be here when you need me.",
                "Very good, {title}. Standing by.",
                "Anytime, {title}.",
                "Understood. Just say the word.",
                "Of course. I'll be around.",
            ]
        )


    def decorate_confirmation(
        self,
        message
    ):
        """
        Wrap a short command confirmation (e.g. "Opening Spotify.") in a
        natural, in-character acknowledgement, and log the action so the
        AI knows what GLITCH just did. Long/factual responses stay clean.
        """

        self.turn_count += 1

        cleaned = (
            message
            .strip()
        )

        if not cleaned:

            return cleaned

        self._note_action(cleaned)

        now = time.time()

        repeated = (
            self._last_action is not None
            and cleaned.lower() == self._last_action
            and now - self._last_action_time < 90
        )

        self._last_action = cleaned.lower()

        self._last_action_time = now


        # Long/factual responses should not get unnecessary filler.
        if len(cleaned) > 120:

            return cleaned


        # Never joke around irreversible power actions.
        lowered = cleaned.lower()

        if (
            "powering off" in lowered
            or "restarting the computer" in lowered
            or "shutting down" in lowered
        ):

            return cleaned


        if repeated:

            return (
                self._pick(
                    [
                        "Again, {title}? Very well.",
                        "Once more, then.",
                        "As you wish. Again.",
                    ]
                )
                + " "
                + cleaned
            )


        hour = self._hour()

        if (
            not self._late_remark_made
            and (hour < 5)
            and self.turn_count >= 2
        ):

            self._late_remark_made = True

            return (
                cleaned
                + " "
                + self._pick(
                    [
                        "It's past {clock}, {title}, for the record.",
                        "You do know what time it is, {title}?",
                    ]
                ).replace(
                    "{clock}",
                    datetime.now().strftime("%I %p").lstrip("0")
                )
            )


        # Informational replies ("CPU is at 12 percent.") are answers,
        # not orders carried out, so "Consider it done" would sound odd.
        first_word = (
            lowered.split()[0].strip(".,!:;")
            if lowered.split()
            else ""
        )

        is_action = (
            first_word.endswith("ing")
            or first_word in {
                "done", "opened", "closed", "launched", "started",
                "stopped", "muted", "unmuted", "switched", "set",
                "paused", "resumed", "skipped", "locked", "saved",
            }
        )

        if not is_action:

            return cleaned


        # Mostly a short acknowledgement before the confirmation;
        # sometimes just the confirmation itself, like a person would.
        roll = self._rng.random()

        if roll < 0.35:

            return cleaned

        prefix = self._pick(
            [
                "Right away, {title}.",
                "On it.",
                "Done.",
                "Of course.",
                "Consider it done.",
                "As you wish.",
                "Right, {title}.",
                "Very well.",
            ]
        )

        # Occasionally keep the door open, but not every turn.
        if self._rng.random() < 0.15 and len(cleaned) < 60:

            return (
                f"{prefix} {cleaned} "
                + self._pick(
                    [
                        "Anything else?",
                        "What's next?",
                    ]
                )
            )

        return (
            f"{prefix} {cleaned}"
        )