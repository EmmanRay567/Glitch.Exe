class SecurityAlertService:
    """
    In-memory alert deduplication for GLITCH.EXE.

    Persistent findings live in SecurityHistoryService.
    This service decides whether something should create
    a NEW user-facing warning during the current runtime.
    """

    SEVERITY_RANK = {
        "NORMAL": 0,
        "SECURE": 0,

        "REVIEW": 1,
        "CAUTION": 1,

        "SUSPICIOUS": 2,
        "WARNING": 2,

        "HIGH": 3,
        "CRITICAL": 3,
    }

    def __init__(
        self
    ):

        self._seen = {}

    @staticmethod
    def _key(
        finding
    ):

        return str(
            finding.get(
                "finding_key",
                ""
            )
            or ""
        ).strip()

    @classmethod
    def _severity(
        cls,
        finding
    ):

        return str(
            finding.get(
                "severity",
                finding.get(
                    "risk_level",
                    "REVIEW"
                )
            )
            or "REVIEW"
        ).strip().upper()

    @classmethod
    def _rank(
        cls,
        finding
    ):

        return cls.SEVERITY_RANK.get(
            cls._severity(
                finding
            ),
            1
        )

    def prime(
        self,
        findings
    ):
        """
        Mark existing unresolved findings as already known
        without creating HUD or voice alerts.
        """

        for finding in findings or []:

            key = self._key(
                finding
            )

            if not key:
                continue

            self._seen[
                key
            ] = self._rank(
                finding
            )

    def forget(
        self,
        finding_key
    ):

        key = str(
            finding_key
            or ""
        ).strip()

        if key:

            self._seen.pop(
                key,
                None
            )

    def collect_new_alerts(
        self,
        findings
    ):

        alerts = []

        for finding in findings or []:

            key = self._key(
                finding
            )

            if not key:
                continue

            rank = self._rank(
                finding
            )

            previous_rank = (
                self._seen.get(
                    key
                )
            )

            if (
                previous_rank is None
                or
                rank > previous_rank
            ):

                alerts.append(
                    finding
                )

            self._seen[
                key
            ] = max(
                rank,
                (
                    previous_rank
                    if previous_rank is not None
                    else 0
                )
            )

        alerts.sort(
            key=lambda item:
                (
                    self._rank(
                        item
                    ),
                    int(
                        item.get(
                            "risk_score",
                            0
                        )
                        or 0
                    ),
                ),
            reverse=True
        )

        return alerts