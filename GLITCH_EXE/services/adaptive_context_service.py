import json
import re
import time
from collections import deque
from pathlib import Path

from models.conversation_context import (
    ConversationContext
)


class AdaptiveContextService:
    """
    GLITCH adaptive context + lightweight user profile.

    Short-term (this run):
        rolling conversation context, what GLITCH just did for you,
        and how you seem to be doing (rushed, frustrated, upbeat)

    Long-term:
        durable non-sensitive preferences, how you like to be
        addressed, project/tool context and when you were last
        around, stored in data/glitch_profile.json

    The AI receives this as quiet background so it can talk like
    someone who has been in the room the whole time.
    """

    # How long a "you seem frustrated" read stays relevant.
    MOOD_TTL_S = 4 * 60

    def __init__(
        self
    ):

        self.context = (
            ConversationContext()
        )

        self.profile_path = (
            Path("data")
            / "glitch_profile.json"
        )

        self.profile_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.profile = {
            "response_preference":
                "brief",

            "explanation_preference":
                "direct_then_expand",

            "active_projects":
                [],

            "preferred_tools":
                [],

            "interests":
                [],

            # How GLITCH addresses you ("sir" by default).
            "preferred_address":
                "",

            "user_name":
                "",

            "last_seen":
                None,

            "session_count":
                0,
        }

        self._load_profile()

        # Things GLITCH did recently: (time, description).
        self.recent_actions = deque(
            maxlen=8
        )

        # (label, guidance, time) or None.
        self.user_mood = None

        # Remember how long it has been since the last run, then
        # stamp this run.
        self.previous_seen = self.profile.get(
            "last_seen"
        )

        self.profile["session_count"] = int(
            self.profile.get("session_count") or 0
        ) + 1

        self._stamp_seen(force=True)

    # ---------------------------------------------------------
    # PROFILE STORAGE
    # ---------------------------------------------------------

    def _load_profile(
        self
    ):

        if not self.profile_path.exists():
            return

        try:

            data = json.loads(
                self.profile_path
                .read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(
                data,
                dict
            ):

                self.profile.update(
                    data
                )

        except Exception as error:

            print(
                "GLITCH PROFILE LOAD ERROR:",
                error
            )


    def _save_profile(
        self
    ):

        try:

            self.profile_path.write_text(
                json.dumps(
                    self.profile,
                    indent=2
                ),
                encoding="utf-8"
            )

        except Exception as error:

            print(
                "GLITCH PROFILE SAVE ERROR:",
                error
            )


    def _stamp_seen(
        self,
        force=False
    ):

        now = time.time()

        last = self.profile.get("last_seen") or 0

        # Avoid rewriting the file on every single message.
        if force or now - last > 60:

            self.profile["last_seen"] = now

            self._save_profile()

    # ---------------------------------------------------------
    # ADDRESSING THE USER
    # ---------------------------------------------------------

    def address(
        self
    ):

        """How GLITCH should address you in quick spoken lines."""

        preferred = (
            self.profile.get("preferred_address")
            or ""
        ).strip()

        return preferred or "sir"

    # ---------------------------------------------------------
    # WORKING CONTEXT
    # ---------------------------------------------------------

    def set_active_reference(
        self,
        topic=None,
        entity_type=None,
        entity_name=None,
        metric=None,
        value=None
    ):

        if topic is not None:
            self.context.current_topic = (
                topic
            )

        if entity_type is not None:
            self.context.active_entity_type = (
                entity_type
            )

        if entity_name is not None:
            self.context.active_entity_name = (
                entity_name
            )

        if metric is not None:
            self.context.active_metric = (
                metric
            )

        if value is not None:
            self.context.active_value = (
                value
            )


    def note_action(
        self,
        description
    ):

        """Record something GLITCH just did ("Opening Spotify.")."""

        description = str(description or "").strip()

        if description:

            self.recent_actions.append(
                (time.time(), description[:160])
            )


    def observe_user(
        self,
        message
    ):

        self.context.add_turn(
            "user",
            message
        )

        self._stamp_seen()

        self._read_mood(
            message
        )

        self._learn_safe_profile_fact(
            message
        )


    def observe_assistant(
        self,
        message
    ):

        self.context.add_turn(
            "assistant",
            message
        )

    # ---------------------------------------------------------
    # MOOD (simple, transparent heuristics)
    # ---------------------------------------------------------

    MOOD_RULES = (
        (
            "frustrated",
            (
                "not working", "doesn't work", "does not work", "still broken",
                "this is broken", "ugh", "come on", "why won't", "why does it keep",
                "i give up", "so annoying", "for the last time", "again?!",
                "wtf", "damn", "seriously",
            ),
            "They sound frustrated. Be calm, steady and solution-first. "
            "Skip jokes until things are working.",
        ),
        (
            "rushed",
            (
                "quick", "quickly", "hurry", "asap", "real quick", "no time",
                "fast", "in a rush", "running late",
            ),
            "They're in a hurry. Be extra brief and lead with the answer.",
        ),
        (
            "tired",
            (
                "i'm tired", "im tired", "exhausted", "so tired", "long day",
                "can't sleep", "cant sleep",
            ),
            "They sound tired. Be warm and low-key; a gentle nudge to rest "
            "is fine if it's late.",
        ),
        (
            "upbeat",
            (
                "it works", "it worked", "let's go", "lets go", "yes!", "awesome",
                "perfect", "nailed it", "finally",
            ),
            "They're in a good mood (something just worked). Match the energy "
            "a little; a light remark is welcome.",
        ),
    )


    def _read_mood(
        self,
        message
    ):

        lowered = f" {message.strip().lower()} "

        for label, phrases, guidance in self.MOOD_RULES:

            if any(phrase in lowered for phrase in phrases):

                self.user_mood = (label, guidance, time.time())

                return


    def _current_mood(
        self
    ):

        if self.user_mood is None:

            return None

        label, guidance, stamp = self.user_mood

        if time.time() - stamp > self.MOOD_TTL_S:

            self.user_mood = None

            return None

        return guidance

    # ---------------------------------------------------------
    # SAFE PROFILE LEARNING
    # ---------------------------------------------------------

    def _add_unique(
        self,
        key,
        value
    ):

        value = (
            value
            .strip()
        )

        if not value:
            return

        values = (
            self.profile
            .setdefault(
                key,
                []
            )
        )

        lowered = {
            item.lower()
            for item in values
        }

        if value.lower() not in lowered:

            values.append(
                value
            )

            self._save_profile()


    def _learn_safe_profile_fact(
        self,
        message
    ):

        lowered = (
            message
            .strip()
            .lower()
        )

        # Keep automatic learning intentionally conservative.
        # Only durable address/project/tool/response-style
        # information is inferred here.

        # "call me boss", "you can call me 404 from now on".
        # Only explicit phrasings, so "call me an uber" is ignored.
        address = re.search(
            r"^(?:glitch[, ]+)?(?:just |you can |please |from now on )*"
            r"call me ([a-z0-9][a-z0-9' .-]{0,23}?)"
            r"(?:\s+(?:from now on|instead|please))?[.!?]*$",
            lowered,
        )

        if address and not address.group(1).startswith(("a ", "an ", "the ")):

            value = address.group(1).strip(" .")

            if value in ("sir", "default", "normal"):

                value = ""

            elif value not in ("boss", "chief", "captain", "ma'am", "madam"):

                value = value.title()

            self.profile["preferred_address"] = value

            self._save_profile()


        name = re.search(
            r"\bmy name is ([a-z0-9][a-z0-9'-]{0,23})\b",
            lowered,
        )

        if name:

            self.profile["user_name"] = name.group(1).title()

            self._save_profile()


        if any(
            phrase in lowered
            for phrase in [
                "keep it brief",
                "keep it short",
                "short answers",
                "be concise",
            ]
        ):

            self.profile[
                "response_preference"
            ] = "brief"

            self._save_profile()


        elif any(
            phrase in lowered
            for phrase in [
                "go deeper",
                "more detail",
                "be more detailed",
            ]
        ):

            self.profile[
                "response_preference"
            ] = "detailed"

            self._save_profile()


        known_projects = [
            "glitch.exe",
            "glitch",
        ]

        for project in known_projects:

            if (
                project in lowered
                and any(
                    word in lowered
                    for word in [
                        "project",
                        "building",
                        "working on",
                        "developing",
                    ]
                )
            ):

                self._add_unique(
                    "active_projects",
                    "GLITCH.EXE"
                )


        # "I'm working on a beat for ..." -> short project note.
        working = re.search(
            r"\bi(?:'m| am) (?:working on|building|making) "
            r"(?:a |an |the |my )?([a-z0-9][a-z0-9 '-]{2,40}?)(?:[.,!?]|$| for | with )",
            lowered,
        )

        if working and "glitch" not in working.group(1):

            self._add_unique(
                "active_projects",
                working.group(1).strip()
            )

            projects = self.profile.get("active_projects", [])

            if len(projects) > 8:

                self.profile["active_projects"] = projects[-8:]

                self._save_profile()


        known_tools = [
            "visual studio",
            "python",
            "c++",
            "github",
            "android studio",
            "serato",
            "fl studio",
            "ableton",
            "pytorch",
            "tensorflow",
        ]

        for tool in known_tools:

            if (
                tool in lowered
                and any(
                    phrase in lowered
                    for phrase in [
                        "i use",
                        "i work in",
                        "i prefer",
                        "using",
                    ]
                )
            ):

                self._add_unique(
                    "preferred_tools",
                    tool
                )

    # ---------------------------------------------------------
    # PROMPT CONTEXT
    # ---------------------------------------------------------

    @staticmethod
    def _ago(
        seconds
    ):

        seconds = max(0, int(seconds))

        if seconds < 60:

            return "just now"

        if seconds < 3600:

            return f"{seconds // 60} min ago"

        if seconds < 86400:

            return f"{seconds // 3600} h ago"

        return f"{seconds // 86400} days ago"


    def build_context_block(
        self,
        include_recent=False
    ):

        """
        include_recent: the assistant now keeps the real back-and-forth
        itself, so the rolling summary is only added when asked for.
        """

        pieces = []

        if self.context.current_topic:

            pieces.append(
                (
                    "CURRENT TOPIC: "
                    f"{self.context.current_topic}"
                )
            )

        if self.context.active_entity_name:

            entity = (
                f"{self.context.active_entity_type or 'entity'}="
                f"{self.context.active_entity_name}"
            )

            pieces.append(
                f"ACTIVE ENTITY: {entity}"
            )

        if self.context.active_metric:

            pieces.append(
                (
                    "ACTIVE METRIC: "
                    f"{self.context.active_metric}"
                )
            )

        if self.context.active_value:

            pieces.append(
                (
                    "LAST OBSERVED VALUE: "
                    f"{self.context.active_value}"
                )
            )


        now = time.time()

        actions = [
            f"{description} ({self._ago(now - stamp)})"
            for stamp, description in self.recent_actions
            if now - stamp < 30 * 60
        ]

        if actions:

            pieces.append(
                "WHAT YOU (GLITCH) DID RECENTLY: "
                + "; ".join(actions[-5:])
            )


        mood = self._current_mood()

        if mood:

            pieces.append(
                f"HOW THEY SEEM RIGHT NOW: {mood}"
            )


        if self.previous_seen:

            away = now - float(self.previous_seen)

            if away > 6 * 3600:

                pieces.append(
                    "CONTINUITY: before this run, they were last around "
                    f"{self._ago(away)}."
                )


        if include_recent:

            recent = (
                self.context
                .recent_summary()
            )

            if recent:

                pieces.append(
                    (
                        "RECENT CONVERSATION:\n"
                        + recent
                    )
                )


        profile_bits = []

        name = self.profile.get("user_name")

        if name:

            profile_bits.append(
                f"name={name}"
            )

        preferred = self.profile.get("preferred_address")

        if preferred:

            profile_bits.append(
                f"prefers to be addressed as '{preferred}' (not 'sir')"
            )

        response_pref = (
            self.profile.get(
                "response_preference"
            )
        )

        if response_pref:

            profile_bits.append(
                (
                    "preferred response length="
                    f"{response_pref}"
                )
            )


        projects = (
            self.profile.get(
                "active_projects",
                []
            )
        )

        if projects:

            profile_bits.append(
                (
                    "active projects="
                    + ", ".join(
                        projects[-5:]
                    )
                )
            )


        tools = (
            self.profile.get(
                "preferred_tools",
                []
            )
        )

        if tools:

            profile_bits.append(
                (
                    "preferred tools="
                    + ", ".join(
                        tools[:6]
                    )
                )
            )


        if profile_bits:

            pieces.append(
                (
                    "USER PROFILE: "
                    + "; ".join(
                        profile_bits
                    )
                )
            )


        if not pieces:
            return ""


        return (
            "GLITCH ADAPTIVE CONTEXT:\n"
            + "\n\n".join(
                pieces
            )
        )