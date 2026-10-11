class VoiceController:
    """
    Interprets recognized voice commands and routes
    deterministic actions through GLITCH architecture.

    VoiceListener = hears/transcribes
    VoiceController = interprets
    Services/commands = perform the action
    """

    def __init__(
        self,
        command_router,
        application_service,
        event_bus=None
    ):
        self.command_router = command_router
        self.application_service = application_service
        self.event_bus = event_bus

    # ---------------------------------------------------------
    # NAVIGATION
    # ---------------------------------------------------------

    def handle_navigation(self, command):
        command = command.strip().lower()

        navigation_commands = {
            "home": "HOME",
            "go home": "HOME",
            "open home": "HOME",

            "chat": "CHAT",
            "open chat": "CHAT",
            "go to chat": "CHAT",

            "create": "CREATE",
            "open create": "CREATE",
            "go to create": "CREATE",

            "search": "SEARCH",
            "open search": "SEARCH",

            "code": "CODE",
            "open code": "CODE",

            "apps": "APPS",
            "open apps": "APPS",

            "settings": "SETTINGS",
            "open settings": "SETTINGS",

            "system matrix": "SYSTEM_MATRIX",
            "open system matrix": "SYSTEM_MATRIX",
            "open diagnostics": "SYSTEM_MATRIX",
            "show diagnostics": "SYSTEM_MATRIX",
            "show system stats": "SYSTEM_MATRIX",
        }

        destination = navigation_commands.get(
            command
        )

        if destination is None:
            return False

        return self.command_router.execute(
            "NAVIGATE",
            destination
        )

    # ---------------------------------------------------------
    # MEDIA
    # ---------------------------------------------------------

    def handle_media(self, command):
        command = command.strip().lower()

        if command in [
            "play music",
            "pause music",
            "play",
            "pause",
            "resume music",
        ]:
            self.application_service.media_play_pause()
            return True, "Media control activated."

        if command in [
            "next track",
            "next song",
            "skip song",
        ]:
            self.application_service.media_next()
            return True, "Next track."

        if command in [
            "previous track",
            "previous song",
            "go back a song",
        ]:
            self.application_service.media_previous()
            return True, "Previous track."

        if command in [
            "stop music",
            "stop playback",
        ]:
            self.application_service.media_stop()
            return True, "Playback stopped."

        return False, None

    # ---------------------------------------------------------
    # OPEN APPLICATION
    # ---------------------------------------------------------

    def handle_open_app(self, command):
        command = command.strip().lower()

        if not command.startswith("open "):
            return False, None

        target = command[
            len("open "):
        ].strip(
            " ,.!?:;-"
        )

        app_map = [
            ("serato studio", "seratostudio", "Opening Serato Studio."),
            ("serato dj", "seratodj", "Opening Serato DJ."),
            ("visual studio", "visualstudio", "Opening Visual Studio."),
            ("android studio", "androidstudio", "Opening Android Studio."),
            ("file explorer", "explorer", "Opening File Explorer."),
            ("chrome", "chrome", "Opening Chrome."),
            ("spotify", "spotify", "Opening Spotify."),
            ("notepad", "notepad", "Opening Notepad."),
            ("calculator", "calculator", "Opening Calculator."),
        ]

        for phrase, app_key, confirmation in app_map:

            if phrase in target:

                success, message = (
                    self.application_service
                    .launch_app(
                        app_key
                    )
                )

                if success:
                    return True, confirmation

                return True, message

        return False, None

    # ---------------------------------------------------------
    # CLOSE APPLICATION
    # ---------------------------------------------------------

    def handle_close_app(self, command):
        command = command.strip().lower()

        if not command.startswith("close "):
            return False, None

        target = command[
            len("close "):
        ].strip()

        app_map = [
            ("serato studio", "seratostudio", "Serato Studio"),
            ("serato dj", "seratodj", "Serato DJ"),
            ("visual studio", "visualstudio", "Visual Studio"),
            ("android studio", "androidstudio", "Android Studio"),
            ("spotify", "spotify", "Spotify"),
            ("chrome", "chrome", "Chrome"),
            ("notepad", "notepad", "Notepad"),
            ("calculator", "calculator", "Calculator"),
        ]

        for phrase, app_key, display_name in app_map:

            if phrase in target:

                success, message = (
                    self.application_service
                    .close_app(
                        app_key
                    )
                )

                if success:
                    return (
                        True,
                        f"Closing {display_name}."
                    )

                return (
                    True,
                    f"{display_name} does not appear "
                    f"to be running."
                )

        return False, None

    # ---------------------------------------------------------
    # MAIN ROUTER
    # ---------------------------------------------------------

    def handle_command(self, command):
        command = command.strip().lower()

        if self.handle_navigation(
            command
        ):
            return {
                "handled": True,
                "type": "navigation",
                "message": None,
            }

        handled, message = (
            self.handle_media(
                command
            )
        )

        if handled:
            return {
                "handled": True,
                "type": "media",
                "message": message,
            }

        handled, message = (
            self.handle_close_app(
                command
            )
        )

        if handled:
            return {
                "handled": True,
                "type": "close_app",
                "message": message,
            }

        handled, message = (
            self.handle_open_app(
                command
            )
        )

        if handled:
            return {
                "handled": True,
                "type": "open_app",
                "message": message,
            }

        return {
            "handled": False,
            "type": None,
            "message": None,
        }
