import socket
import psutil

from services.base_service import BaseService
from models.events import TelemetryEvent


class SystemMonitoringService(BaseService):
    """
    Collects live workstation telemetry.

    This service keeps system-monitoring logic
    out of the UI layer and publishes telemetry
    snapshots through the shared EventBus.
    """

    def __init__(
        self,
        event_bus=None
    ):
        super().__init__(
            event_bus
        )


    # ---------------------------------------------------------
    # CPU
    # ---------------------------------------------------------

    def get_cpu_percent(self):
        """
        Return current CPU usage percentage.
        """

        return psutil.cpu_percent()


    # ---------------------------------------------------------
    # MEMORY
    # ---------------------------------------------------------

    def get_memory_percent(self):
        """
        Return current RAM usage percentage.
        """

        return (
            psutil
            .virtual_memory()
            .percent
        )


    # ---------------------------------------------------------
    # BATTERY
    # ---------------------------------------------------------

    def get_battery_status(self):
        """
        Return battery information.

        Returns:
            dict
        """

        battery = (
            psutil
            .sensors_battery()
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
        """
        Check whether at least one useful network
        interface is currently active.
        """

        try:

            interfaces = (
                psutil
                .net_if_stats()
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
        """
        Return a human-readable network state.
        """

        return (
            "ONLINE"
            if self.is_network_connected()
            else "OFFLINE"
        )


    # ---------------------------------------------------------
    # HOST
    # ---------------------------------------------------------

    def get_hostname(self):
        """
        Return the computer hostname.
        """

        return (
            socket
            .gethostname()
        )


    # ---------------------------------------------------------
    # TELEMETRY EVENT
    # ---------------------------------------------------------

    def publish_telemetry_event(
        self,
        snapshot
    ):
        """
        Broadcast the latest workstation telemetry
        snapshot through GLITCH's shared EventBus.
        """

        event = TelemetryEvent(

            name="SYSTEM_STATUS_UPDATED",

            source="SystemMonitoringService",

            cpu_percent=(
                snapshot[
                    "cpu_percent"
                ]
            ),

            memory_percent=(
                snapshot[
                    "memory_percent"
                ]
            ),

            network_status=(
                snapshot[
                    "network"
                ]
            ),

            hostname=(
                snapshot[
                    "hostname"
                ]
            ),

            data={
                "cpu_percent":
                    snapshot[
                        "cpu_percent"
                    ],

                "memory_percent":
                    snapshot[
                        "memory_percent"
                    ],

                "battery":
                    snapshot[
                        "battery"
                    ],

                "network":
                    snapshot[
                        "network"
                    ],

                "hostname":
                    snapshot[
                        "hostname"
                    ],
            }
        )


        self.publish(
            event
        )


    # ---------------------------------------------------------
    # COMPLETE SNAPSHOT
    # ---------------------------------------------------------

    def get_snapshot(self):
        """
        Return all HOME telemetry in one dictionary
        and publish the snapshot through EventBus.
        """

        battery = (
            self.get_battery_status()
        )


        snapshot = {

            "cpu_percent":
                self.get_cpu_percent(),

            "memory_percent":
                self.get_memory_percent(),

            "battery":
                battery,

            "network":
                self.get_network_status(),

            "hostname":
                self.get_hostname(),
        }


        self.publish_telemetry_event(
            snapshot
        )


        return snapshot