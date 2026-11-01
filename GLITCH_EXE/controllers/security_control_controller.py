import re


class SecurityControlController:
    """
    Deterministic parser for Phase 3 security-control commands.

    This controller never performs destructive actions. It only
    translates user language into an action request. MainWindow and
    SecurityActionService own confirmation and execution.
    """

    def parse(self, command):
        command = str(command or "").strip().lower()

        if not command:
            return self._result(False)

        if command in {
            "show active findings",
            "show security findings",
            "open security findings",
            "list active findings",
            "list security findings",
            "what are the active findings",
            "what security findings do you have",
        }:
            return self._result(True, "SHOW_FINDINGS")

        if command in {
            "show security history",
            "show recent security events",
            "show security events",
            "security history",
            "recent security history",
        }:
            return self._result(True, "SHOW_HISTORY")

        if command in {
            "what process is suspicious",
            "which process is suspicious",
            "what is the most suspicious process",
            "show the most suspicious process",
            "most suspicious process",
        }:
            return self._result(
                True,
                "MOST_SUSPICIOUS"
            )

        if command in {
            "close security findings",
            "close findings",
            "hide security findings",
            "hide findings",
        }:
            return self._result(
                True,
                "CLOSE_FINDINGS"
            )

        if command in {
            "confirm",
            "confirm security action",
            "yes confirm",
            "do it",
            "proceed",
        }:
            return self._result(
                True,
                "CONFIRM"
            )

        if command in {
            "cancel",
            "cancel security action",
            "never mind",
            "nevermind",
            "abort",
        }:
            return self._result(
                True,
                "CANCEL"
            )

        indexed_patterns = [
            (
                r"^(?:show|explain|open) finding\s+(\d+)$",
                "SHOW_FINDING"
            ),
            (
                r"^(?:show|give me) details (?:for|on) finding\s+(\d+)$",
                "SHOW_FINDING"
            ),
            (
                r"^resolve finding\s+(\d+)$",
                "RESOLVE_FINDING"
            ),
            (
                r"^mark finding\s+(\d+) resolved$",
                "RESOLVE_FINDING"
            ),
            (
                r"^quarantine finding\s+(\d+)$",
                "REQUEST_QUARANTINE"
            ),
            (
                r"^(?:terminate|stop|end) finding\s+(\d+)$",
                "REQUEST_TERMINATE"
            ),
            (
                r"^(?:terminate|stop|end) process (?:for )?finding\s+(\d+)$",
                "REQUEST_TERMINATE"
            ),
            (
                r"^block finding\s+(\d+)$",
                "REQUEST_BLOCK"
            ),
            (
                r"^block network (?:for|on) finding\s+(\d+)$",
                "REQUEST_BLOCK"
            ),
        ]

        for pattern, action in indexed_patterns:

            match = re.match(
                pattern,
                command
            )

            if match:

                return self._result(
                    True,
                    action,
                    index=int(
                        match.group(
                            1
                        )
                    ),
                )

        # If there is only one active finding,
        # MainWindow can infer the finding number.

        if command in {
            "resolve this finding",
            "resolve the finding",
        }:

            return self._result(
                True,
                "RESOLVE_FINDING",
                index=None
            )

        if command in {
            "quarantine this finding",
            "quarantine the finding",
        }:

            return self._result(
                True,
                "REQUEST_QUARANTINE",
                index=None
            )

        if command in {
            "terminate this process",
            "terminate the process",
            "stop this process",
        }:

            return self._result(
                True,
                "REQUEST_TERMINATE",
                index=None
            )

        if command in {
            "block this process",
            "block the process",
            "block its network access",
        }:

            return self._result(
                True,
                "REQUEST_BLOCK",
                index=None
            )

        return self._result(
            False
        )

    @staticmethod
    def _result(
        handled,
        action=None,
        index=None
    ):

        return {
            "handled": bool(
                handled
            ),
            "action": action,
            "index": index,
        }
