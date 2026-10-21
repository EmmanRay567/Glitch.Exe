from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HardwareState:
    """
    Represents one live snapshot of the computer running
    GLITCH.EXE.

    This becomes the foundation of the Phase 2 hardware
    digital twin.
    """

    # -----------------------------------------------------
    # SYSTEM IDENTITY
    # -----------------------------------------------------

    hostname: str = "UNKNOWN"

    operating_system: str = "UNKNOWN"

    architecture: str = "UNKNOWN"


    # -----------------------------------------------------
    # CPU
    # -----------------------------------------------------

    cpu_percent: float = 0.0

    cpu_frequency_mhz: float = 0.0

    physical_cores: int = 0

    logical_cores: int = 0


    # -----------------------------------------------------
    # MEMORY
    # -----------------------------------------------------

    memory_percent: float = 0.0

    memory_used_gb: float = 0.0

    memory_total_gb: float = 0.0


    # -----------------------------------------------------
    # STORAGE
    # -----------------------------------------------------

    disk_percent: float = 0.0

    disk_used_gb: float = 0.0

    disk_total_gb: float = 0.0


    # -----------------------------------------------------
    # BATTERY
    # -----------------------------------------------------

    battery_percent: float | None = None

    battery_plugged_in: bool | None = None


    # -----------------------------------------------------
    # NETWORK
    # -----------------------------------------------------

    network_status: str = "UNKNOWN"

    network_sent_mb: float = 0.0

    network_received_mb: float = 0.0


    # -----------------------------------------------------
    # OPERATING STATE
    # -----------------------------------------------------

    uptime_seconds: float = 0.0

    process_count: int = 0


    # -----------------------------------------------------
    # EXTENSIBLE HARDWARE DATA
    # -----------------------------------------------------

    extra: dict[str, Any] = field(
        default_factory=dict
    )


    # -----------------------------------------------------
    # SNAPSHOT TIME
    # -----------------------------------------------------

    timestamp: datetime = field(
        default_factory=datetime.now
    )


    # -----------------------------------------------------
    # HELPERS
    # -----------------------------------------------------

    def memory_available_gb(
        self
    ) -> float:

        available = (
            self.memory_total_gb
            - self.memory_used_gb
        )


        return max(
            available,
            0.0
        )


    def disk_available_gb(
        self
    ) -> float:

        available = (
            self.disk_total_gb
            - self.disk_used_gb
        )


        return max(
            available,
            0.0
        )


    def uptime_hours(
        self
    ) -> float:

        return (
            self.uptime_seconds
            / 3600
        )


    def health_status(
        self
    ) -> str:
        """
        Basic Phase 2 health assessment.

        Later we can replace this with a dedicated
        SystemHealthService.
        """

        if (
            self.cpu_percent >= 95
            or self.memory_percent >= 95
            or self.disk_percent >= 98
        ):

            return "CRITICAL"


        if (
            self.cpu_percent >= 80
            or self.memory_percent >= 85
            or self.disk_percent >= 90
        ):

            return "WARNING"


        return "OPTIMAL"


    def to_dict(
        self
    ) -> dict[str, Any]:
        """
        Convert the Digital Twin snapshot into a dictionary
        for UI widgets, events, APIs, logging, or future agents.
        """

        return {

            "hostname":
                self.hostname,

            "operating_system":
                self.operating_system,

            "architecture":
                self.architecture,

            "cpu_percent":
                self.cpu_percent,

            "cpu_frequency_mhz":
                self.cpu_frequency_mhz,

            "physical_cores":
                self.physical_cores,

            "logical_cores":
                self.logical_cores,

            "memory_percent":
                self.memory_percent,

            "memory_used_gb":
                self.memory_used_gb,

            "memory_total_gb":
                self.memory_total_gb,

            "memory_available_gb":
                self.memory_available_gb(),

            "disk_percent":
                self.disk_percent,

            "disk_used_gb":
                self.disk_used_gb,

            "disk_total_gb":
                self.disk_total_gb,

            "disk_available_gb":
                self.disk_available_gb(),

            "battery_percent":
                self.battery_percent,

            "battery_plugged_in":
                self.battery_plugged_in,

            "network_status":
                self.network_status,

            "network_sent_mb":
                self.network_sent_mb,

            "network_received_mb":
                self.network_received_mb,

            "uptime_seconds":
                self.uptime_seconds,

            "uptime_hours":
                self.uptime_hours(),

            "process_count":
                self.process_count,

            "health_status":
                self.health_status(),

            "extra":
                self.extra,

            "timestamp":
                self.timestamp,
        }
