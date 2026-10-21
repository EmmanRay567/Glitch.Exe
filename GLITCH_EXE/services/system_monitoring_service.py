import platform
import socket
import time

import psutil

from services.base_service import BaseService
from models.events import TelemetryEvent
from models.hardware_state import HardwareState


class SystemMonitoringService(BaseService):
    """
    Collects live workstation telemetry.

    Phase 2:
    This service now owns GLITCH's live HardwareState
    Digital Twin while preserving the original snapshot
    dictionary used by the existing UI.
    """

    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        self.current_state = HardwareState()

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
            return float(frequency.current)
        except Exception:
            return 0.0

    def get_physical_core_count(self):
        return psutil.cpu_count(logical=False) or 0

    def get_logical_core_count(self):
        return psutil.cpu_count(logical=True) or 0

    # ---------------------------------------------------------
    # MEMORY
    # ---------------------------------------------------------

    def get_memory_info(self):
        memory = psutil.virtual_memory()
        gb = 1024 ** 3

        return {
            "percent": float(memory.percent),
            "used_gb": memory.used / gb,
            "total_gb": memory.total / gb,
        }

    def get_memory_percent(self):
        return self.get_memory_info()["percent"]

    # ---------------------------------------------------------
    # STORAGE
    # ---------------------------------------------------------

    def get_disk_info(self):
        try:
            root_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(root_path)
            gb = 1024 ** 3

            return {
                "percent": float(disk.percent),
                "used_gb": disk.used / gb,
                "total_gb": disk.total / gb,
            }
        except Exception:
            return {
                "percent": 0.0,
                "used_gb": 0.0,
                "total_gb": 0.0,
            }

    # ---------------------------------------------------------
    # BATTERY
    # ---------------------------------------------------------

    def get_battery_status(self):
        battery = psutil.sensors_battery()

        if battery is None:
            return {
                "available": False,
                "percent": None,
                "charging": False,
                "display": "DESKTOP / N/A",
            }

        display = f"{battery.percent:.0f}%"

        if battery.power_plugged:
            display += " // CHARGING"

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
            interfaces = psutil.net_if_stats()

            for name, stats in interfaces.items():
                lower_name = name.lower()

                if (
                    stats.isup
                    and "loopback" not in lower_name
                    and "pseudo" not in lower_name
                ):
                    return True
        except Exception:
            return False

        return False

    def get_network_status(self):
        return "ONLINE" if self.is_network_connected() else "OFFLINE"

    def get_network_totals_mb(self):
        try:
            counters = psutil.net_io_counters()
            mb = 1024 ** 2

            return {
                "sent_mb": counters.bytes_sent / mb,
                "received_mb": counters.bytes_recv / mb,
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
        return socket.gethostname()

    def get_operating_system(self):
        try:
            return f"{platform.system()} {platform.release()}"
        except Exception:
            return "UNKNOWN"

    def get_architecture(self):
        try:
            return platform.machine() or "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    # ---------------------------------------------------------
    # OPERATING STATE
    # ---------------------------------------------------------

    def get_uptime_seconds(self):
        try:
            return max(time.time() - psutil.boot_time(), 0.0)
        except Exception:
            return 0.0

    def get_process_count(self):
        try:
            return len(psutil.pids())
        except Exception:
            return 0

    # ---------------------------------------------------------
    # HARDWARE DIGITAL TWIN
    # ---------------------------------------------------------

    def build_hardware_state(self):
        memory = self.get_memory_info()
        disk = self.get_disk_info()
        battery = self.get_battery_status()
        network = self.get_network_totals_mb()

        state = HardwareState(
            hostname=self.get_hostname(),
            operating_system=self.get_operating_system(),
            architecture=self.get_architecture(),
            cpu_percent=self.get_cpu_percent(),
            cpu_frequency_mhz=self.get_cpu_frequency_mhz(),
            physical_cores=self.get_physical_core_count(),
            logical_cores=self.get_logical_core_count(),
            memory_percent=memory["percent"],
            memory_used_gb=memory["used_gb"],
            memory_total_gb=memory["total_gb"],
            disk_percent=disk["percent"],
            disk_used_gb=disk["used_gb"],
            disk_total_gb=disk["total_gb"],
            battery_percent=battery["percent"],
            battery_plugged_in=(
                battery["charging"]
                if battery["available"]
                else None
            ),
            network_status=self.get_network_status(),
            network_sent_mb=network["sent_mb"],
            network_received_mb=network["received_mb"],
            uptime_seconds=self.get_uptime_seconds(),
            process_count=self.get_process_count(),
            extra={
                "battery_display": battery["display"],
                "battery_available": battery["available"],
            },
        )

        self.current_state = state
        return state

    def get_current_state(self):
        return self.current_state

    # ---------------------------------------------------------
    # TELEMETRY EVENT
    # ---------------------------------------------------------

    def publish_telemetry_event(self, state):
        event = TelemetryEvent(
            name="SYSTEM_STATUS_UPDATED",
            source="SystemMonitoringService",
            cpu_percent=state.cpu_percent,
            memory_percent=state.memory_percent,
            network_status=state.network_status,
            hostname=state.hostname,
            data=state.to_dict(),
        )

        self.publish(event)

    # ---------------------------------------------------------
    # COMPLETE SNAPSHOT
    # ---------------------------------------------------------

    def get_snapshot(self):
        """
        Build the live HardwareState Digital Twin, publish it,
        then return the original UI-compatible dictionary.
        """

        state = self.build_hardware_state()

        self.publish_telemetry_event(state)

        battery_available = state.extra.get(
            "battery_available",
            False,
        )

        battery_display = state.extra.get(
            "battery_display",
            "DESKTOP / N/A",
        )

        return {
            # Original UI-compatible keys.
            "cpu_percent": state.cpu_percent,
            "memory_percent": state.memory_percent,
            "battery": {
                "available": battery_available,
                "percent": state.battery_percent,
                "charging": (
                    state.battery_plugged_in
                    if state.battery_plugged_in is not None
                    else False
                ),
                "display": battery_display,
            },
            "network": state.network_status,
            "hostname": state.hostname,

            # Phase 2 additions.
            "digital_twin": state,
            "health_status": state.health_status(),
            "disk_percent": state.disk_percent,
            "process_count": state.process_count,
            "uptime_seconds": state.uptime_seconds,
        }
