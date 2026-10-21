import time


class PowerController:
    """
    Safety layer for high-impact system power actions.

    A shutdown or restart request NEVER executes immediately.
    The user must confirm while a matching request is pending.
    """

    CONFIRMATION_TIMEOUT_SECONDS = 30.0


    def __init__(
        self,
        system_power_service
    ):

        self.system_power_service = (
            system_power_service
        )

        self.pending_action = None
        self.pending_source = None
        self.pending_at = None


    # ---------------------------------------------------------
    # PENDING STATE
    # ---------------------------------------------------------

    def clear_pending(self):

        self.pending_action = None
        self.pending_source = None
        self.pending_at = None


    def has_pending_action(self):

        if self.pending_action is None:
            return False


        if self.pending_at is None:
            self.clear_pending()
            return False


        age = (
            time.time()
            - self.pending_at
        )


        if (
            age
            > self.CONFIRMATION_TIMEOUT_SECONDS
        ):

            self.clear_pending()

            return False


        return True


    def pending_description(self):

        if not self.has_pending_action():
            return None


        return (
            self.pending_action
            .replace(
                "_",
                " "
            )
            .lower()
        )


    # ---------------------------------------------------------
    # REQUESTS
    # ---------------------------------------------------------

    def request_action(
        self,
        action,
        source="UNKNOWN"
    ):

        action = (
            action
            .strip()
            .upper()
        )


        if action not in [
            "SHUTDOWN",
            "RESTART",
        ]:

            return {
                "handled": False,
                "executed": False,
                "message":
                    "Unsupported power action.",
            }


        self.pending_action = (
            action
        )

        self.pending_source = (
            source
        )

        self.pending_at = (
            time.time()
        )


        readable_action = (
            action.lower()
        )


        return {
            "handled": True,
            "executed": False,
            "requires_confirmation": True,
            "action": action,
            "message": (
                f"{readable_action.capitalize()} requested. "
                f"Say or type 'confirm' within "
                f"{int(self.CONFIRMATION_TIMEOUT_SECONDS)} seconds "
                f"to continue, or 'cancel' to abort."
            ),
        }


    # ---------------------------------------------------------
    # CONFIRM / CANCEL
    # ---------------------------------------------------------

    def confirm(
        self,
        source="UNKNOWN"
    ):

        if not self.has_pending_action():

            return {
                "handled": True,
                "executed": False,
                "message":
                    "There is no pending power action to confirm.",
            }


        action = (
            self.pending_action
        )


        # Clear BEFORE executing so a duplicate transcript or
        # keypress cannot execute the action twice.
        self.clear_pending()


        if action == "SHUTDOWN":

            self.system_power_service.shutdown()

            return {
                "handled": True,
                "executed": True,
                "action": action,
                "message":
                    "Shutdown confirmed. Powering off the computer.",
            }


        if action == "RESTART":

            self.system_power_service.restart()

            return {
                "handled": True,
                "executed": True,
                "action": action,
                "message":
                    "Restart confirmed. Restarting the computer.",
            }


        return {
            "handled": True,
            "executed": False,
            "message":
                "The pending power action could not be executed.",
        }


    def cancel(
        self,
        source="UNKNOWN"
    ):

        if not self.has_pending_action():

            return {
                "handled": True,
                "executed": False,
                "message":
                    "There is no pending power action to cancel.",
            }


        action = (
            self.pending_description()
        )


        self.clear_pending()


        return {
            "handled": True,
            "executed": False,
            "message":
                f"Pending {action} cancelled.",
        }


    # ---------------------------------------------------------
    # COMMAND ROUTING
    # ---------------------------------------------------------

    def handle_command(
        self,
        command,
        source="UNKNOWN"
    ):

        command = (
            command
            .strip()
            .lower()
        )


        shutdown_commands = [
            "shutdown",
            "shut down",
            "shut down computer",
            "shut down my computer",
            "shutdown computer",
            "shutdown my computer",
            "power off",
            "power off computer",
            "power off my computer",
            "turn off computer",
            "turn off my computer",
        ]


        restart_commands = [
            "restart",
            "restart computer",
            "restart my computer",
            "reboot",
            "reboot computer",
            "reboot my computer",
        ]


        confirm_commands = [
            "confirm",
            "confirm shutdown",
            "confirm restart",
            "yes confirm",
            "yes do it",
            "proceed",
        ]


        cancel_commands = [
            "cancel",
            "cancel shutdown",
            "cancel restart",
            "abort",
            "never mind",
            "nevermind",
        ]


        if command in shutdown_commands:

            return self.request_action(
                "SHUTDOWN",
                source
            )


        if command in restart_commands:

            return self.request_action(
                "RESTART",
                source
            )


        if command in confirm_commands:

            return self.confirm(
                source
            )


        if command in cancel_commands:

            return self.cancel(
                source
            )


        return {
            "handled": False,
            "executed": False,
            "message": None,
        }

