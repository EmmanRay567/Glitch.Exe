from dataclasses import dataclass, field
from datetime import datetime

from models.scan_result import FileScanResult


@dataclass
class SecurityState:
    """
    Shared Phase 3 Digital Security Twin.

    Current scan status is kept separate from lifetime totals so
    old false positives do not remain shown as active threats.
    """

    security_status: str = "SECURE"

    antivirus_engine_active: bool = True

    # Lifetime total across this GLITCH session.
    files_scanned: int = 0

    # Current/latest batch only.
    suspicious_files: int = 0

    quarantined_files: int = 0

    last_scan_target: str | None = None

    last_scan_time: datetime | None = None

    recent_results: list[FileScanResult] = field(
        default_factory=list
    )

    updated_at: datetime = field(
        default_factory=datetime.now
    )


    def update_from_results(
        self,
        target,
        results
    ):

        results = list(
            results
        )

        self.last_scan_target = (
            str(target)
        )

        self.last_scan_time = (
            datetime.now()
        )

        # Lifetime count is cumulative.
        self.files_scanned += len(
            results
        )

        # Active suspicious count is for the newest batch only.
        self.suspicious_files = sum(
            1
            for result in results
            if result.suspicious
        )

        self.recent_results = (
            results[-20:]
        )


        levels = {
            result.risk_level
            for result in results
            if result.error is None
        }


        if "CRITICAL" in levels:

            self.security_status = (
                "CRITICAL"
            )

        elif "WARNING" in levels:

            self.security_status = (
                "WARNING"
            )

        elif "CAUTION" in levels:

            self.security_status = (
                "CAUTION"
            )

        else:

            self.security_status = (
                "SECURE"
            )


        self.updated_at = (
            datetime.now()
        )
