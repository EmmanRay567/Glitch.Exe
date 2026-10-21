from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# =========================================================
# DRIVE STATE
# =========================================================

@dataclass
class DriveState:
    """
    Represents one mounted storage device in GLITCH's
    Hardware Digital Twin.
    """

    device: str = "UNKNOWN"
    mountpoint: str = "UNKNOWN"
    filesystem: str = "UNKNOWN"

    percent_used: float = 0.0

    used_gb: float = 0.0
    free_gb: float = 0.0
    total_gb: float = 0.0


    def health_status(self) -> str:
        """
        Simple storage-capacity health classification.
        """

        if self.percent_used >= 98:
            return "CRITICAL"

        if self.percent_used >= 90:
            return "WARNING"

        return "OPTIMAL"


    def to_dict(self) -> dict[str, Any]:

        return {
            "device":
                self.device,

            "mountpoint":
                self.mountpoint,

            "filesystem":
                self.filesystem,

            "percent_used":
                self.percent_used,

            "used_gb":
                self.used_gb,

            "free_gb":
                self.free_gb,

            "total_gb":
                self.total_gb,

            "health_status":
                self.health_status(),
        }


# =========================================================
# PROCESS STATE
# =========================================================

@dataclass
class ProcessState:
    """
    Represents one running operating-system process.

    Phase 2 will use this model for process intelligence,
    top CPU usage, and top memory usage.
    """

    pid: int = 0
    name: str = "UNKNOWN"

    cpu_percent: float = 0.0

    memory_percent: float = 0.0
    memory_mb: float = 0.0

    status: str = "UNKNOWN"


    def to_dict(self) -> dict[str, Any]:

        return {
            "pid":
                self.pid,

            "name":
                self.name,

            "cpu_percent":
                self.cpu_percent,

            "memory_percent":
                self.memory_percent,

            "memory_mb":
                self.memory_mb,

            "status":
                self.status,
        }


# =========================================================
# HARDWARE STATE
# =========================================================

@dataclass
class HardwareState:
    """
    Represents one live snapshot of the computer running
    GLITCH.EXE.

    This is the central Phase 2 Hardware Digital Twin.

    Existing Phase 2 fields remain intact while richer
    DriveState and ProcessState collections are added.
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
    # PRIMARY STORAGE
    #
    # These original fields stay here because the existing
    # System Matrix currently depends on them.
    # -----------------------------------------------------

    disk_percent: float = 0.0

    disk_used_gb: float = 0.0

    disk_total_gb: float = 0.0


    # -----------------------------------------------------
    # MULTI-DRIVE STORAGE
    # -----------------------------------------------------

    drives: list[DriveState] = field(
        default_factory=list
    )


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
    # PROCESS INTELLIGENCE
    # -----------------------------------------------------

    processes: list[ProcessState] = field(
        default_factory=list
    )

    top_cpu_processes: list[ProcessState] = field(
        default_factory=list
    )

    top_memory_processes: list[ProcessState] = field(
        default_factory=list
    )


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
    # MEMORY HELPERS
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


    # -----------------------------------------------------
    # PRIMARY DISK HELPERS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # UPTIME HELPERS
    # -----------------------------------------------------

    def uptime_hours(
        self
    ) -> float:

        return (
            self.uptime_seconds
            / 3600
        )


    # -----------------------------------------------------
    # PROCESS HELPERS
    # -----------------------------------------------------

    def highest_cpu_process(
        self
    ) -> ProcessState | None:

        if not self.top_cpu_processes:
            return None


        return (
            self.top_cpu_processes[0]
        )


    def highest_memory_process(
        self
    ) -> ProcessState | None:

        if not self.top_memory_processes:
            return None


        return (
            self.top_memory_processes[0]
        )


    # -----------------------------------------------------
    # DRIVE HELPERS
    # -----------------------------------------------------

    def primary_drive(
        self
    ) -> DriveState | None:

        if not self.drives:
            return None


        return (
            self.drives[0]
        )


    # -----------------------------------------------------
    # SYSTEM HEALTH
    # -----------------------------------------------------

    def health_status(
        self
    ) -> str:
        """
        Basic Phase 2 health assessment.

        Later this can move into a dedicated
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


    # -----------------------------------------------------
    # SERIALIZATION
    # -----------------------------------------------------

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

            "drives": [
                drive.to_dict()
                for drive in self.drives
            ],

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

            "processes": [
                process.to_dict()
                for process in self.processes
            ],

            "top_cpu_processes": [
                process.to_dict()
                for process in self.top_cpu_processes
            ],

            "top_memory_processes": [
                process.to_dict()
                for process in self.top_memory_processes
            ],

            "health_status":
                self.health_status(),

            "extra":
                self.extra,

            "timestamp":
                self.timestamp,
        }
