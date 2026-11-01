from pathlib import Path


class SecurityQueryController:
    """
    Parses deterministic Security Engine commands.

    Heavy scans are not executed here. The controller only
    decides what action is requested and which target to use.
    """

    def __init__(
        self,
        security_engine
    ):

        self.security_engine = (
            security_engine
        )


    def parse(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
        )


        if command in {
            "scan my downloads",
            "scan downloads",
            "scan my downloads folder",
            "scan downloads folder",
            "scan the downloads folder",
        }:

            return {
                "handled": True,
                "action": "SCAN_DIRECTORY",
                "target": str(
                    Path.home()
                    / "Downloads"
                ),
                "message": (
                    "Scanning your Downloads folder."
                ),
            }


        if command in {
            "security status",
            "what is my security status",
            "what's my security status",
            "is my computer secure",
            "is my pc secure",
            "show security status",
        }:

            state = (
                self.security_engine
                .state
            )

            return {
                "handled": True,
                "action": "STATUS",
                "target": None,
                "message": (
                    f"Security state is {state.security_status}. "
                    f"I have scanned {state.files_scanned} files, "
                    f"flagged {state.suspicious_files} suspicious files, "
                    f"and there are {state.quarantined_files} items "
                    "in quarantine."
                ),
            }


        if command in {
            "show suspicious files",
            "show me suspicious files",
            "what suspicious files did you find",
            "what threats did you find",
            "show threats",
        }:

            suspicious = [
                result
                for result
                in self.security_engine.state.recent_results
                if result.suspicious
            ]


            if not suspicious:

                message = (
                    "I do not have any suspicious files "
                    "in the recent scan results."
                )

            else:

                preview = ", ".join(
                    (
                        f"{result.file_name} "
                        f"({result.risk_level}, "
                        f"score {result.risk_score})"
                    )
                    for result
                    in suspicious[:5]
                )

                message = (
                    "Recent suspicious files: "
                    + preview
                )


            return {
                "handled": True,
                "action": "LIST_SUSPICIOUS",
                "target": None,
                "message": message,
            }


        if command in {
            "show quarantine",
            "show quarantined files",
            "what is in quarantine",
            "what's in quarantine",
        }:

            items = (
                self.security_engine
                .list_quarantine()
            )


            if not items:

                message = (
                    "GLITCH quarantine is empty."
                )

            else:

                preview = ", ".join(
                    item.get(
                        "file_name",
                        "unknown file"
                    )
                    for item
                    in items[:5]
                )

                message = (
                    f"There are {len(items)} items in quarantine: "
                    + preview
                )


            return {
                "handled": True,
                "action": "LIST_QUARANTINE",
                "target": None,
                "message": message,
            }


        return {
            "handled": False,
            "action": None,
            "target": None,
            "message": None,
        }
