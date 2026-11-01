from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScanIndicator:
    code: str
    message: str
    score: int = 0
    severity: str = "INFO"


@dataclass
class FileScanResult:
    path: str
    file_name: str
    size_bytes: int = 0
    sha256: str | None = None
    extension: str = ""
    risk_score: int = 0
    risk_level: str = "LOW"
    indicators: list[ScanIndicator] = field(
        default_factory=list
    )
    error: str | None = None
    scanned_at: datetime = field(
        default_factory=datetime.now
    )

    @property
    def suspicious(
        self
    ):

        return self.risk_level in {
            "WARNING",
            "CRITICAL",
        }

    def to_dict(
        self
    ):

        return {
            "path":
                self.path,

            "file_name":
                self.file_name,

            "size_bytes":
                self.size_bytes,

            "sha256":
                self.sha256,

            "extension":
                self.extension,

            "risk_score":
                self.risk_score,

            "risk_level":
                self.risk_level,

            "indicators": [
                {
                    "code":
                        indicator.code,

                    "message":
                        indicator.message,

                    "score":
                        indicator.score,

                    "severity":
                        indicator.severity,
                }
                for indicator
                in self.indicators
            ],

            "error":
                self.error,

            "scanned_at":
                self.scanned_at.isoformat(),
        }

