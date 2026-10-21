import platform
import socket
import time
import threading

import psutil

from services.base_service import BaseService
from models.events import TelemetryEvent
from models.hardware_state import (
    DriveState,
    HardwareState,
    ProcessState,
)


class SystemMonitoringService(BaseService):
    """
    Collects live workstation telemetry.

    Phase 2:
    This service owns GLITCH's HardwareState Digital Twin and
    now also collects structured drive and process intelligence.
    """

    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        self.current_state = HardwareState()

        # Expensive telemetry is cached so the 1-second UI refresh
        # does not rescan every process and drive on every tick.
        self._cached_drives = []
        self._cached_processes = []
        self._cached_top_cpu_processes = []
        self._cached_top_memory_processes = []

        self._last_drive_scan_time = 0.0
        self._last_process_scan_time = 0.0

        self._drive_scan_interval = 30.0
        self._process_scan_interval = 10.0

        self._intelligence_lock = threading.Lock()
        self._intelligence_thread = None
        self._intelligence_scan_running = False

    # ---------------------------------------------------------
    # CPU
    # ---------------------------------------------------------

    def get_cpu_percent(self):
        return psutil.cpu_percent()

    def get_cpu_frequency_mhz(self):
        try:
            frequency = psutil.cpu_freq()

            if frequency is None:
                return 0.0

            return float(
                frequency.current
            )

        except Exception:
            return 0.0

    def get_physical_core_count(self):
        return (
            psutil.cpu_count(
                logical=False
            )
            or 0
        )

    def get_logical_core_count(self):
        return (
            psutil.cpu_count(
                logical=True
            )
            or 0
        )

    # ---------------------------------------------------------
    # MEMORY
    # ---------------------------------------------------------

    def get_memory_info(self):
        memory = (
            psutil.virtual_memory()
        )

        gb = (
            1024 ** 3
        )

        return {
            "percent":
                float(
                    memory.percent
                ),

            "used_gb":
                memory.used / gb,

            "total_gb":
                memory.total / gb,
        }

    def get_memory_percent(self):
        return (
            self.get_memory_info()[
                "percent"
            ]
        )

    # ---------------------------------------------------------
    # PRIMARY STORAGE
    # ---------------------------------------------------------

    def get_disk_info(self):
        """
        Preserve the original primary-drive snapshot used by
        the existing System Matrix.
        """

        try:
            root_path = (
                "C:\\"
                if platform.system() == "Windows"
                else "/"
            )

            disk = (
                psutil.disk_usage(
                    root_path
                )
            )

            gb = (
                1024 ** 3
            )

            return {
                "percent":
                    float(
                        disk.percent
                    ),

                "used_gb":
                    disk.used / gb,

                "total_gb":
                    disk.total / gb,
            }

        except Exception:
            return {
                "percent": 0.0,
                "used_gb": 0.0,
                "total_gb": 0.0,
            }

    # ---------------------------------------------------------
    # MULTI-DRIVE STORAGE INTELLIGENCE
    # ---------------------------------------------------------

    def get_drive_states(self):
        """
        Return structured information for mounted storage
        volumes that psutil can read.

        Unreadable/removable volumes are skipped safely.
        """

        drives = []
        seen_mountpoints = set()

        gb = (
            1024 ** 3
        )

        try:
            partitions = (
                psutil.disk_partitions(
                    all=False
                )
            )

        except Exception:
            partitions = []

        for partition in partitions:

            mountpoint = (
                partition.mountpoint
            )

            if (
                not mountpoint
                or mountpoint
                in seen_mountpoints
            ):
                continue

            seen_mountpoints.add(
                mountpoint
            )

            try:
                usage = (
                    psutil.disk_usage(
                        mountpoint
                    )
                )

            except (
                PermissionError,
                OSError,
            ):
                continue

            except Exception:
                continue

            drives.append(
                DriveState(
                    device=(
                        partition.device
                        or mountpoint
                        or "UNKNOWN"
                    ),

                    mountpoint=(
                        mountpoint
                    ),

                    filesystem=(
                        partition.fstype
                        or "UNKNOWN"
                    ),

                    percent_used=(
                        float(
                            usage.percent
                        )
                    ),

                    used_gb=(
                        usage.used / gb
                    ),

                    free_gb=(
                        usage.free / gb
                    ),

                    total_gb=(
                        usage.total / gb
                    ),
                )
            )

        # Fallback so the Digital Twin still has the system
        # drive even if disk_partitions() returns nothing useful.
        if not drives:

            try:
                root_path = (
                    "C:\\"
                    if platform.system() == "Windows"
                    else "/"
                )

                usage = (
                    psutil.disk_usage(
                        root_path
                    )
                )

                drives.append(
                    DriveState(
                        device=root_path,
                        mountpoint=root_path,
                        filesystem="UNKNOWN",
                        percent_used=float(
                            usage.percent
                        ),
                        used_gb=(
                            usage.used / gb
                        ),
                        free_gb=(
                            usage.free / gb
                        ),
                        total_gb=(
                            usage.total / gb
                        ),
                    )
                )

            except Exception:
                pass

        return drives

    # ---------------------------------------------------------
    # BATTERY
    # ---------------------------------------------------------

    def get_battery_status(self):
        battery = (
            psutil.sensors_battery()
        )

        if battery is None:

            return {
                "available": False,
                "percent": None,
                "charging": False,
                "display": "DESKTOP / N/A",
            }

        display = (
            f"{battery.percent:.0f}%"
        )

        if battery.power_plugged:
            display += (
                " // CHARGING"
            )

        return {
            "available": True,
            "percent": battery.percent,
            "charging": battery.power_plugged,
            "display": display,
        }

    # ---------------------------------------------------------
    # NETWORK
    # ---------------------------------------------------------

    def is_network_connected(self):
        try:
            interfaces = (
                psutil.net_if_stats()
            )

            for (
                name,
                stats
            ) in interfaces.items():

                lower_name = (
                    name.lower()
                )

                if (
                    stats.isup
                    and "loopback"
                    not in lower_name
                    and "pseudo"
                    not in lower_name
                ):
                    return True

        except Exception:
            return False

        return False

    def get_network_status(self):
        return (
            "ONLINE"
            if self.is_network_connected()
            else "OFFLINE"
        )

    def get_network_totals_mb(self):
        try:
            counters = (
                psutil.net_io_counters()
            )

            mb = (
                1024 ** 2
            )

            return {
                "sent_mb":
                    counters.bytes_sent
                    / mb,

                "received_mb":
                    counters.bytes_recv
                    / mb,
            }

        except Exception:
            return {
                "sent_mb": 0.0,
                "received_mb": 0.0,
            }

    # ---------------------------------------------------------
    # HOST / OS
    # ---------------------------------------------------------

    def get_hostname(self):
        return (
            socket.gethostname()
        )

    def get_operating_system(self):
        try:
            return (
                f"{platform.system()} "
                f"{platform.release()}"
            )

        except Exception:
            return "UNKNOWN"

    def get_architecture(self):
        try:
            return (
                platform.machine()
                or "UNKNOWN"
            )

        except Exception:
            return "UNKNOWN"

    def get_local_ip(self):
        """
        Best-effort local IPv4 address for display purposes.
        """

        try:
            hostname = (
                socket.gethostname()
            )

            return (
                socket.gethostbyname(
                    hostname
                )
            )

        except Exception:
            return None

    # ---------------------------------------------------------
    # PROCESS INTELLIGENCE
    # ---------------------------------------------------------

    def get_process_states(self):
        """
        Build ProcessState objects for currently visible
        processes.

        Some protected Windows processes cannot be inspected.
        Those are skipped rather than failing the snapshot.
        """

        processes = []

        mb = (
            1024 ** 2
        )

        attrs = [
            "pid",
            "name",
            "status",
            "memory_percent",
            "memory_info",
        ]

        try:
            iterator = (
                psutil.process_iter(
                    attrs=attrs
                )
            )

        except Exception:
            return []

        for process in iterator:

            try:
                info = (
                    process.info
                )

                memory_info = (
                    info.get(
                        "memory_info"
                    )
                )

                memory_mb = 0.0

                if memory_info is not None:
                    memory_mb = (
                        memory_info.rss
                        / mb
                    )

                # psutil caches Process instances used by
                # process_iter(), so CPU percentages become
                # meaningful across successive snapshots.
                cpu_percent = (
                    process.cpu_percent(
                        interval=None
                    )
                )

                processes.append(
                    ProcessState(
                        pid=(
                            int(
                                info.get(
                                    "pid"
                                )
                                or 0
                            )
                        ),

                        name=(
                            info.get(
                                "name"
                            )
                            or "UNKNOWN"
                        ),

                        cpu_percent=(
                            float(
                                cpu_percent
                                or 0.0
                            )
                        ),

                        memory_percent=(
                            float(
                                info.get(
                                    "memory_percent"
                                )
                                or 0.0
                            )
                        ),

                        memory_mb=(
                            float(
                                memory_mb
                            )
                        ),

                        status=(
                            info.get(
                                "status"
                            )
                            or "UNKNOWN"
                        ),
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):
                continue

            except Exception:
                continue

        return processes

    def get_top_cpu_processes(
        self,
        processes,
        limit=5
    ):
        """
        Return highest CPU-using visible processes.
        """

        return sorted(
            processes,
            key=lambda process:
                process.cpu_percent,
            reverse=True
        )[:limit]

    def get_top_memory_processes(
        self,
        processes,
        limit=5
    ):
        """
        Return highest RAM-using visible processes.
        """

        return sorted(
            processes,
            key=lambda process:
                process.memory_mb,
            reverse=True
        )[:limit]

    # ---------------------------------------------------------
    # OPERATING STATE
    # ---------------------------------------------------------

    def get_uptime_seconds(self):
        try:
            return max(
                time.time()
                - psutil.boot_time(),
                0.0
            )

        except Exception:
            return 0.0

    def get_process_count(self):
        try:
            return len(
                psutil.pids()
            )

        except Exception:
            return 0

    # ---------------------------------------------------------
    # BACKGROUND INTELLIGENCE CACHE
    # ---------------------------------------------------------

    def _background_intelligence_scan(self):
        """
        Refresh expensive drive/process intelligence away from
        the UI thread.

        The HUD continues using the last completed cache while
        this work runs.
        """

        try:
            now = time.time()

            refresh_drives = (
                not self._cached_drives
                or (
                    now
                    - self._last_drive_scan_time
                ) >= self._drive_scan_interval
            )

            refresh_processes = (
                not self._cached_processes
                or (
                    now
                    - self._last_process_scan_time
                ) >= self._process_scan_interval
            )


            new_drives = None
            new_processes = None
            new_top_cpu = None
            new_top_memory = None


            if refresh_drives:
                new_drives = (
                    self.get_drive_states()
                )


            if refresh_processes:
                new_processes = (
                    self.get_process_states()
                )

                new_top_cpu = (
                    self.get_top_cpu_processes(
                        new_processes
                    )
                )

                new_top_memory = (
                    self.get_top_memory_processes(
                        new_processes
                    )
                )


            with self._intelligence_lock:

                if new_drives is not None:
                    self._cached_drives = (
                        new_drives
                    )

                    self._last_drive_scan_time = (
                        time.time()
                    )


                if new_processes is not None:
                    self._cached_processes = (
                        new_processes
                    )

                    self._cached_top_cpu_processes = (
                        new_top_cpu
                    )

                    self._cached_top_memory_processes = (
                        new_top_memory
                    )

                    self._last_process_scan_time = (
                        time.time()
                    )


        finally:
            with self._intelligence_lock:
                self._intelligence_scan_running = (
                    False
                )


    def request_intelligence_refresh(self):
        """
        Start a background intelligence refresh when needed.

        This method never waits for the scan to finish.
        """

        now = time.time()

        needs_drive_refresh = (
            not self._cached_drives
            or (
                now
                - self._last_drive_scan_time
            ) >= self._drive_scan_interval
        )

        needs_process_refresh = (
            not self._cached_processes
            or (
                now
                - self._last_process_scan_time
            ) >= self._process_scan_interval
        )


        if (
            not needs_drive_refresh
            and not needs_process_refresh
        ):
            return


        with self._intelligence_lock:

            if self._intelligence_scan_running:
                return


            self._intelligence_scan_running = (
                True
            )


            self._intelligence_thread = (
                threading.Thread(
                    target=
                        self._background_intelligence_scan,

                    name=
                        "GLITCH-SystemIntelligence",

                    daemon=True,
                )
            )


            self._intelligence_thread.start()


    def get_cached_intelligence(self):
        """
        Return the last completed intelligence snapshot
        immediately without blocking the UI.
        """

        with self._intelligence_lock:

            return (
                list(
                    self._cached_drives
                ),

                list(
                    self._cached_processes
                ),

                list(
                    self._cached_top_cpu_processes
                ),

                list(
                    self._cached_top_memory_processes
                ),
            )


    # ---------------------------------------------------------
    # HARDWARE DIGITAL TWIN
    # ---------------------------------------------------------

    def build_hardware_state(self):
        memory = (
            self.get_memory_info()
        )

        disk = (
            self.get_disk_info()
        )

        # Ask for expensive intelligence asynchronously.
        # The current snapshot uses the last completed cache.
        self.request_intelligence_refresh()

        (
            drives,
            processes,
            top_cpu_processes,
            top_memory_processes,
        ) = (
            self.get_cached_intelligence()
        )

        battery = (
            self.get_battery_status()
        )

        network = (
            self.get_network_totals_mb()
        )

        state = HardwareState(
            hostname=
                self.get_hostname(),

            operating_system=
                self.get_operating_system(),

            architecture=
                self.get_architecture(),

            cpu_percent=
                self.get_cpu_percent(),

            cpu_frequency_mhz=
                self.get_cpu_frequency_mhz(),

            physical_cores=
                self.get_physical_core_count(),

            logical_cores=
                self.get_logical_core_count(),

            memory_percent=
                memory[
                    "percent"
                ],

            memory_used_gb=
                memory[
                    "used_gb"
                ],

            memory_total_gb=
                memory[
                    "total_gb"
                ],

            disk_percent=
                disk[
                    "percent"
                ],

            disk_used_gb=
                disk[
                    "used_gb"
                ],

            disk_total_gb=
                disk[
                    "total_gb"
                ],

            drives=
                drives,

            battery_percent=
                battery[
                    "percent"
                ],

            battery_plugged_in=(
                battery[
                    "charging"
                ]
                if battery[
                    "available"
                ]
                else None
            ),

            network_status=
                self.get_network_status(),

            network_sent_mb=
                network[
                    "sent_mb"
                ],

            network_received_mb=
                network[
                    "received_mb"
                ],

            uptime_seconds=
                self.get_uptime_seconds(),

            process_count=
                self.get_process_count(),

            processes=
                processes,

            top_cpu_processes=
                top_cpu_processes,

            top_memory_processes=
                top_memory_processes,

            extra={
                "battery_display":
                    battery[
                        "display"
                    ],

                "battery_available":
                    battery[
                        "available"
                    ],

                "local_ip":
                    self.get_local_ip(),
            },
        )

        self.current_state = (
            state
        )

        return state

    def get_current_state(self):
        return (
            self.current_state
        )

    # ---------------------------------------------------------
    # TELEMETRY EVENT
    # ---------------------------------------------------------

    def publish_telemetry_event(
        self,
        state
    ):
        """
        Publish lightweight live telemetry.

        The full process list stays inside current_state instead
        of being serialized and broadcast every second.
        """

        event = TelemetryEvent(
            name=
                "SYSTEM_STATUS_UPDATED",

            source=
                "SystemMonitoringService",

            cpu_percent=
                state.cpu_percent,

            memory_percent=
                state.memory_percent,

            network_status=
                state.network_status,

            hostname=
                state.hostname,

            data={
                "cpu_percent":
                    state.cpu_percent,

                "memory_percent":
                    state.memory_percent,

                "disk_percent":
                    state.disk_percent,

                "network_status":
                    state.network_status,

                "hostname":
                    state.hostname,

                "process_count":
                    state.process_count,

                "health_status":
                    state.health_status(),

                "top_cpu_processes": [
                    process.to_dict()
                    for process
                    in state.top_cpu_processes
                ],

                "top_memory_processes": [
                    process.to_dict()
                    for process
                    in state.top_memory_processes
                ],

                "drives": [
                    drive.to_dict()
                    for drive
                    in state.drives
                ],
            },
        )

        self.publish(
            event
        )

    # ---------------------------------------------------------
    # COMPLETE SNAPSHOT
    # ---------------------------------------------------------

    def get_snapshot(self):
        """
        Build the live HardwareState Digital Twin, publish it,
        then return the original UI-compatible dictionary.
        """

        state = (
            self.build_hardware_state()
        )

        self.publish_telemetry_event(
            state
        )

        battery_available = (
            state.extra.get(
                "battery_available",
                False,
            )
        )

        battery_display = (
            state.extra.get(
                "battery_display",
                "DESKTOP / N/A",
            )
        )

        return {
            # Original UI-compatible keys.
            "cpu_percent":
                state.cpu_percent,

            "memory_percent":
                state.memory_percent,

            "battery": {
                "available":
                    battery_available,

                "percent":
                    state.battery_percent,

                "charging": (
                    state.battery_plugged_in
                    if state.battery_plugged_in
                    is not None
                    else False
                ),

                "display":
                    battery_display,
            },

            "network":
                state.network_status,

            "hostname":
                state.hostname,

            # Phase 2 Digital Twin.
            "digital_twin":
                state,

            "health_status":
                state.health_status(),

            "disk_percent":
                state.disk_percent,

            "process_count":
                state.process_count,

            "uptime_seconds":
                state.uptime_seconds,

            # Phase 2 Step 3 intelligence.
            "drives":
                state.drives,

            "top_cpu_processes":
                state.top_cpu_processes,

            "top_memory_processes":
                state.top_memory_processes,
        }
