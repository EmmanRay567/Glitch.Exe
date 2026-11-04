class ContextController:
    """
    Phase 2 conversational context.

    The AI now keeps the real conversation history itself
    (core/assistant.py), so build_ai_context only adds the
    situational background: what GLITCH just did, what "it" refers
    to, how the user seems, and the user profile.

    Tracks recent system, process, app, weather, and navigation
    references so short follow-ups can be resolved without
    requiring the user to repeat full commands.
    """

    def __init__(
        self,
        adaptive_context_service=None
    ):

        self.adaptive_context_service = (
            adaptive_context_service
        )

        self.last_system_topic = None
        self.last_metric = None

        self.last_process_name = None
        self.last_process_cpu = None
        self.last_process_memory_mb = None

        self.last_app_target = None

        self.last_weather_topic = None
        self.last_weather_day = None

        # Set by the main window once the Sports Nexus exists.
        self.sports_service = None

        # Set by the main window once the Career Matrix exists.
        self.career_service = None

    # ---------------------------------------------------------
    # SYSTEM MEMORY
    # ---------------------------------------------------------

    def remember_system_topic(
        self,
        query_type
    ):

        self.last_system_topic = (
            query_type
        )

        metric_map = {
            "TOP_CPU": "CPU",
            "TOP_MEMORY": "MEMORY",
            "HEALTH": "SYSTEM_HEALTH",
            "STORAGE": "STORAGE",
            "DRIVES": "STORAGE",
            "PROCESS_COUNT": "PROCESSES",
            "TOP_PROCESSES": "PROCESSES",
            "NETWORK": "NETWORK",
            "BATTERY": "BATTERY",
            "UPTIME": "UPTIME",
        }

        self.last_metric = (
            metric_map.get(
                query_type
            )
        )

    def remember_system_result(
        self,
        result
    ):

        query_type = (
            result.get(
                "type"
            )
        )

        if query_type:
            self.remember_system_topic(
                query_type
            )

        process_name = (
            result.get(
                "process_name"
            )
        )

        if process_name:
            self.last_process_name = (
                process_name
            )

        if (
            result.get(
                "process_cpu_percent"
            )
            is not None
        ):

            self.last_process_cpu = (
                result.get(
                    "process_cpu_percent"
                )
            )

        if (
            result.get(
                "process_memory_mb"
            )
            is not None
        ):

            self.last_process_memory_mb = (
                result.get(
                    "process_memory_mb"
                )
            )


        if self.adaptive_context_service is not None:

            metric = None
            value = None

            if query_type == "TOP_CPU":

                metric = "CPU"

                if (
                    self.last_process_cpu
                    is not None
                ):

                    value = (
                        f"{self.last_process_cpu:.1f}% CPU"
                    )

            elif query_type == "TOP_MEMORY":

                metric = "MEMORY"

                if (
                    self.last_process_memory_mb
                    is not None
                ):

                    value = (
                        f"{self.last_process_memory_mb:.0f} MB memory"
                    )


            self.adaptive_context_service.set_active_reference(
                topic="local system performance",
                entity_type=(
                    "process"
                    if self.last_process_name
                    else "system"
                ),
                entity_name=(
                    self.last_process_name
                    or query_type
                ),
                metric=(
                    metric
                    or self.last_metric
                ),
                value=value,
            )

    # ---------------------------------------------------------
    # WEATHER MEMORY
    # ---------------------------------------------------------

    def remember_weather_result(
        self,
        result
    ):

        topic = (
            result.get(
                "weather_topic"
            )
        )

        day = (
            result.get(
                "day_index"
            )
        )

        if topic:
            self.last_weather_topic = (
                topic
            )

        if day is not None:
            self.last_weather_day = (
                day
            )


        if self.adaptive_context_service is not None:

            self.adaptive_context_service.set_active_reference(
                topic="weather",
                entity_type="forecast",
                entity_name=(
                    "current weather"
                ),
                metric=topic,
                value=(
                    f"forecast day index {day}"
                    if day is not None
                    else None
                ),
            )

    # ---------------------------------------------------------
    # APPLICATION MEMORY
    # ---------------------------------------------------------

    def remember_app_from_command(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
        )

        known_apps = [
            "serato studio",
            "serato dj",
            "visual studio",
            "android studio",
            "file explorer",
            "chrome",
            "spotify",
            "notepad",
            "calculator",
        ]

        for app_name in known_apps:

            if app_name in command:

                self.last_app_target = (
                    app_name
                )


                if self.adaptive_context_service is not None:

                    self.adaptive_context_service.set_active_reference(
                        topic="application control",
                        entity_type="application",
                        entity_name=app_name,
                    )


                return

    # ---------------------------------------------------------
    # FOLLOW-UP RESOLUTION
    # ---------------------------------------------------------

    def resolve(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
            .strip(
                " ,.!?:;-"
            )
        )

        system_followups = {
            "what about cpu":
                "what's using the most cpu",

            "and cpu":
                "what's using the most cpu",

            "how about cpu":
                "what's using the most cpu",

            "cpu":
                "what's using the most cpu",

            "what about ram":
                "what's using the most ram",

            "what about memory":
                "what's using the most memory",

            "and memory":
                "what's using the most memory",

            "how about memory":
                "what's using the most memory",

            "memory":
                "what's using the most memory",

            "what about storage":
                "storage status",

            "and storage":
                "storage status",

            "how about storage":
                "storage status",

            "what about my drives":
                "show my drives",

            "and my drives":
                "show my drives",

            "what about the network":
                "network status",

            "and the network":
                "network status",

            "how about the network":
                "network status",

            "what about battery":
                "battery status",

            "and battery":
                "battery status",

            "how about battery":
                "battery status",

            "what about uptime":
                "system uptime",

            "and uptime":
                "system uptime",

            "how about uptime":
                "system uptime",

            "what's eating my cpu":
                "what's using the most cpu",

            "what's hogging my cpu":
                "what's using the most cpu",

            "what's hogging my memory":
                "what's using the most memory",

            "what's hogging my ram":
                "what's using the most ram",

            "how's my battery":
                "battery status",

            "how's the network":
                "network status",

            "how long have i been on":
                "system uptime",
        }

        if command in system_followups:

            return (
                system_followups[
                    command
                ]
            )

        if (
            command
            in [
                "what about the other one",
                "what about the other",
                "and the other one",
            ]
        ):

            if self.last_system_topic == "TOP_CPU":
                return "what's using the most memory"

            if self.last_system_topic == "TOP_MEMORY":
                return "what's using the most cpu"

        if (
            command in [
                "close it",
                "close that",
                "close the app",
                "kill it",
                "shut it",
                "close it down",
                "get rid of it",
            ]
            and self.last_app_target
        ):

            return (
                f"close {self.last_app_target}"
            )

        if (
            command in [
                "open it",
                "open that",
                "open the app",
                "open it again",
                "open it back up",
                "bring it back",
                "reopen it",
            ]
            and self.last_app_target
        ):

            return (
                f"open {self.last_app_target}"
            )

        return command

    # ---------------------------------------------------------
    # AI CONTEXT
    # ---------------------------------------------------------

    def build_ai_context(
        self,
        command
    ):

        lowered = (
            command
            .strip()
            .lower()
        )

        context_sections = []


        if self.adaptive_context_service is not None:

            adaptive_block = (
                self.adaptive_context_service
                .build_context_block()
            )

            if adaptive_block:

                context_sections.append(
                    adaptive_block
                )


        if self.career_service is not None:

            try:

                career_block = (
                    self.career_service
                    .context_for(
                        command
                    )
                )

            except Exception:

                career_block = ""

            if career_block:

                context_sections.append(
                    career_block
                )


        if self.sports_service is not None:

            try:

                sports_block = (
                    self.sports_service
                    .context_for(
                        command
                    )
                )

            except Exception:

                sports_block = ""

            if sports_block:

                context_sections.append(
                    sports_block
                )


        process_followup = any(
            phrase in lowered
            for phrase in [
                "why is it using",
                "why is that using",
                "why so much",
                "is that normal",
                "is it normal",
                "what is it",
                "what's it",
                "what is that process",
                "should i close it",
                "should i stop it",
                "what about it",
                "why is it doing that",
                "why does it do that",
                "why is that happening",
            ]
        )


        if (
            process_followup
            and self.last_process_name
        ):

            facts = [
                (
                    "The current ambiguous reference 'it/that' most likely "
                    f"refers to process {self.last_process_name}."
                )
            ]

            if (
                self.last_process_cpu
                is not None
            ):

                facts.append(
                    (
                        "Its last observed CPU usage was "
                        f"{self.last_process_cpu:.1f}%."
                    )
                )

            if (
                self.last_process_memory_mb
                is not None
            ):

                facts.append(
                    (
                        "Its last observed memory usage was "
                        f"{self.last_process_memory_mb:.0f} MB."
                    )
                )

            facts.append(
                (
                    "Use this context naturally. Do not claim the old telemetry "
                    "value is still current unless fresh telemetry was requested."
                )
            )

            context_sections.append(
                (
                    "LOCAL SYSTEM REFERENCE:\n"
                    + " ".join(
                        facts
                    )
                )
            )


        if not context_sections:

            return command


        return (
            "\n\n".join(
                context_sections
            )
            + "\n\nUSER MESSAGE:\n"
            + command
        )