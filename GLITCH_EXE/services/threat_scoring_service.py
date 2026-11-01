from models.scan_result import ScanIndicator


class ThreatScoringService:
    """
    Deterministic threat scoring with trust-aware suppression.

    Trust can suppress low-confidence heuristic flags.
    Known malicious hashes and executable-content mismatches
    are never suppressed by extension/folder trust.
    """

    EXECUTABLE_EXTENSIONS = {
        ".exe",
        ".dll",
        ".scr",
        ".com",
        ".msi",
    }

    SCRIPT_EXTENSIONS = {
        ".ps1",
        ".bat",
        ".cmd",
        ".vbs",
        ".js",
        ".jse",
        ".wsf",
        ".hta",
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
    }

    def score(
        self,
        facts
    ):

        indicators = []

        trusted_extension = bool(
            facts.get(
                "trusted_extension"
            )
        )

        trusted_directory = bool(
            facts.get(
                "trusted_directory"
            )
        )

        trusted_hash = bool(
            facts.get(
                "trusted_hash"
            )
        )

        strong_trust = (
            trusted_hash
            or trusted_directory
        )


        # -------------------------------------------------
        # TRUST INFORMATION
        # -------------------------------------------------

        for (
            code,
            message
        ) in facts.get(
            "trust_reasons",
            []
        ):

            indicators.append(
                ScanIndicator(
                    code=code,
                    message=message,
                    score=0,
                    severity="INFO",
                )
            )


        # -------------------------------------------------
        # DOUBLE EXTENSION
        # -------------------------------------------------

        if facts.get(
            "double_extension"
        ):

            indicators.append(
                ScanIndicator(
                    code="DOUBLE_EXTENSION",
                    message=(
                        "File uses a deceptive-looking "
                        "double extension."
                    ),
                    score=30,
                    severity="WARNING",
                )
            )


        # -------------------------------------------------
        # SCRIPT FILE
        # -------------------------------------------------

        extension = (
            facts.get(
                "extension",
                ""
            )
            .lower()
        )

        if (
            extension
            in self.SCRIPT_EXTENSIONS
            and not trusted_extension
            and not strong_trust
        ):

            indicators.append(
                ScanIndicator(
                    code="SCRIPT_FILE",
                    message=(
                        "Executable script file detected."
                    ),
                    score=8,
                    severity="INFO",
                )
            )


        # -------------------------------------------------
        # EXECUTABLE FROM USER DOWNLOAD/TEMP LOCATION
        # -------------------------------------------------

        if (
            extension
            in self.EXECUTABLE_EXTENSIONS
            and facts.get(
                "user_download_location"
            )
            and not strong_trust
        ):

            indicators.append(
                ScanIndicator(
                    code="EXECUTABLE_IN_DOWNLOADS",
                    message=(
                        "Executable is located in a "
                        "user Downloads directory."
                    ),
                    score=8,
                    severity="INFO",
                )
            )


        if (
            extension
            in (
                self.EXECUTABLE_EXTENSIONS
                | self.SCRIPT_EXTENSIONS
            )
            and facts.get(
                "temp_location"
            )
            and not strong_trust
        ):

            indicators.append(
                ScanIndicator(
                    code="EXECUTION_CAPABLE_IN_TEMP",
                    message=(
                        "Execution-capable file is located "
                        "inside a temporary directory."
                    ),
                    score=18,
                    severity="CAUTION",
                )
            )


        # -------------------------------------------------
        # HIDDEN FILE
        # -------------------------------------------------

        if (
            facts.get(
                "hidden_name"
            )
            and not strong_trust
        ):

            indicators.append(
                ScanIndicator(
                    code="HIDDEN_FILE",
                    message=(
                        "File name begins with a hidden-file marker."
                    ),
                    score=4,
                    severity="INFO",
                )
            )


        # -------------------------------------------------
        # EXECUTABLE CONTENT / EXTENSION MISMATCH
        # -------------------------------------------------

        if (
            facts.get(
                "mz_header"
            )
            and extension
            not in self.EXECUTABLE_EXTENSIONS
        ):

            indicators.append(
                ScanIndicator(
                    code="PE_EXTENSION_MISMATCH",
                    message=(
                        "File contains a Windows executable "
                        "header but does not use a normal "
                        "executable extension."
                    ),
                    score=45,
                    severity="WARNING",
                )
            )


        # -------------------------------------------------
        # KNOWN MALICIOUS HASH
        # -------------------------------------------------

        if facts.get(
            "known_bad_hash"
        ):

            indicators.append(
                ScanIndicator(
                    code="KNOWN_MALICIOUS_HASH",
                    message=(
                        "SHA-256 hash matches the local "
                        "known-malicious signature database."
                    ),
                    score=100,
                    severity="CRITICAL",
                )
            )


        score = sum(
            indicator.score
            for indicator in indicators
        )

        score = min(
            score,
            100
        )


        if score >= 70:

            level = "CRITICAL"

        elif score >= 40:

            level = "WARNING"

        elif score >= 20:

            level = "CAUTION"

        else:

            level = "LOW"


        return (
            score,
            level,
            indicators
        )
