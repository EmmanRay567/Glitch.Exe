import json
from pathlib import Path

from models.conversation_context import (
    ConversationContext
)


class AdaptiveContextService:
    """
    GLITCH adaptive context + lightweight user profile.

    Short-term:
        rolling conversation context

    Long-term:
        durable non-sensitive preferences and project/tool context
        stored in data/glitch_profile.json
    """

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
        }

        self._load_profile()

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


    def observe_user(
        self,
        message
    ):

        self.context.add_turn(
            "user",
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
        # Only durable project/tool/response-style information
        # is inferred here.

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


        known_tools = [
            "visual studio",
            "python",
            "c++",
            "github",
            "android studio",
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

    def build_context_block(
        self
    ):

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
                        projects[:5]
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
                        tools[:5]
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

