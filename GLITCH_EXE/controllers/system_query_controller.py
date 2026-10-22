class SystemQueryController:
    """
    Interprets deterministic questions about the local computer
    and answers them from GLITCH's HardwareState Digital Twin.

    This keeps machine-awareness separate from the general AI.
    """

    def __init__(
        self,
        system_monitoring_service
    ):

        self.system_monitoring_service = (
            system_monitoring_service
        )


    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------

    def get_state(self):
        """
        Build a fresh lightweight snapshot.

        Expensive process/drive intelligence remains cached and
        background-refreshed by SystemMonitoringService.
        """

        snapshot = (
            self.system_monitoring_service
            .get_snapshot()
        )

        return (
            snapshot[
                "digital_twin"
            ]
        )


    # ---------------------------------------------------------
    # FORMAT HELPERS
    # ---------------------------------------------------------

    def format_top_cpu(self, state):

        process = (
            state.highest_cpu_process()
        )


        if process is None:

            return (
                "Process intelligence is still warming up. "
                "Try again in a few seconds."
            )


        return (
            f"{process.name} is currently using the most CPU "
            f"at about {process.cpu_percent:.1f} percent."
        )


    def format_top_memory(self, state):

        process = (
            state.highest_memory_process()
        )


        if process is None:

            return (
                "Process intelligence is still warming up. "
                "Try again in a few seconds."
            )


        if process.memory_mb >= 1024:

            memory_text = (
                f"{process.memory_mb / 1024:.1f} gigabytes"
            )

        else:

            memory_text = (
                f"{process.memory_mb:.0f} megabytes"
            )


        return (
            f"{process.name} is currently using the most memory "
            f"at about {memory_text}."
        )


    def format_system_health(self, state):

        return (
            f"System health is {state.health_status().lower()}. "
            f"CPU usage is {state.cpu_percent:.0f} percent. "
            f"Memory usage is {state.memory_percent:.0f} percent. "
            f"Your primary drive is {state.disk_percent:.0f} percent full."
        )


    def format_storage(self, state):

        drive = (
            state.primary_drive()
        )


        if drive is None:

            free_gb = (
                state.disk_available_gb()
            )

            return (
                f"Your primary drive is {state.disk_percent:.0f} percent full "
                f"with about {free_gb:.0f} gigabytes available."
            )


        return (
            f"{drive.device} is {drive.percent_used:.0f} percent full "
            f"with about {drive.free_gb:.0f} gigabytes free "
            f"out of {drive.total_gb:.0f} gigabytes."
        )


    def format_drives(self, state):

        if not state.drives:

            return (
                "Drive intelligence is still warming up. "
                "Try again in a few seconds."
            )


        parts = []

        for drive in state.drives[:4]:

            name = (
                drive.device
                or drive.mountpoint
            )

            parts.append(
                (
                    f"{name} is {drive.percent_used:.0f} percent full "
                    f"with {drive.free_gb:.0f} gigabytes free"
                )
            )


        return (
            "Detected drives: "
            + "; ".join(parts)
            + "."
        )


    def format_process_count(self, state):

        return (
            f"There are currently {state.process_count} processes running."
        )


    def format_top_processes(self, state):

        if not state.top_cpu_processes:

            return (
                "Process intelligence is still warming up. "
                "Try again in a few seconds."
            )


        names = []

        for process in state.top_cpu_processes[:3]:

            names.append(
                (
                    f"{process.name} at "
                    f"{process.cpu_percent:.1f} percent CPU"
                )
            )


        return (
            "The top CPU processes are "
            + ", ".join(names)
            + "."
        )


    def format_network(self, state):

        return (
            f"Network status is {state.network_status.lower()}. "
            f"Total received since startup is about "
            f"{state.network_received_mb:.0f} megabytes, "
            f"and total sent is about "
            f"{state.network_sent_mb:.0f} megabytes."
        )


    def format_battery(self, state):

        if state.battery_percent is None:

            return (
                "No battery is detected. This appears to be a desktop system "
                "or a device without battery telemetry."
            )


        charging_text = (
            " and it is plugged in"
            if state.battery_plugged_in
            else ""
        )


        return (
            f"Battery level is {state.battery_percent:.0f} percent"
            f"{charging_text}."
        )


    def format_uptime(self, state):

        total_minutes = int(
            state.uptime_seconds
            // 60
        )

        hours = (
            total_minutes
            // 60
        )

        minutes = (
            total_minutes
            % 60
        )


        return (
            f"The computer has been running for "
            f"{hours} hours and {minutes} minutes."
        )


    # ---------------------------------------------------------
    # ROUTER
    # ---------------------------------------------------------

    def handle_query(
        self,
        command
    ):

        command = (
            command
            .strip()
            .lower()
        )


        query_type = None


        top_memory_phrases = [
            "what's using the most ram",
            "what is using the most ram",
            "what's using the most memory",
            "what is using the most memory",
            "highest memory process",
            "top memory process",
            "top ram process",
            "what is eating my ram",
            "what's eating my ram",
            "what is using all my memory",
            "what's using all my memory",
            "which process uses the most ram",
            "which app is using the most memory",
        ]


        top_cpu_phrases = [
            "what's using the most cpu",
            "what is using the most cpu",
            "highest cpu process",
            "top cpu process",
            "what's hitting my cpu",
            "what is hitting my cpu",
            "what is eating my cpu",
            "what's eating my cpu",
            "which process uses the most cpu",
            "which app is using the most cpu",
            "what is using all my cpu",
            "what's using all my cpu",
        ]


        health_phrases = [
            "how's my system doing",
            "how is my system doing",
            "how's my computer doing",
            "how is my computer doing",
            "system health",
            "what's my system health",
            "what is my system health",
            "is my computer okay",
            "is my pc okay",
            "is my system okay",
            "how are my resources",
            "give me a system status",
            "give me a system summary",
        ]


        storage_phrases = [
            "how much storage do i have left",
            "how much storage is left",
            "storage status",
            "show storage status",
            "how full is my drive",
            "how full is my disk",
            "how much disk space is left",
            "how much space do i have left",
            "how much free space do i have",
            "check my storage",
        ]


        drives_phrases = [
            "show my drives",
            "show drives",
            "what drives do i have",
            "list my drives",
            "what storage drives do i have",
        ]


        process_count_phrases = [
            "how many processes are running",
            "process count",
            "how many processes do i have running",
        ]


        top_processes_phrases = [
            "what processes are running",
            "show top processes",
            "show me top processes",
            "what are my top processes",
        ]


        network_phrases = [
            "network status",
            "how's my network",
            "how is my network",
            "am i online",
            "is my internet connected",
            "is my network connected",
            "check my network",
            "how is my internet",
        ]


        battery_phrases = [
            "battery status",
            "what's my battery",
            "what is my battery",
            "how much battery do i have",
            "how much battery is left",
            "what percent is my battery",
            "am i charging",
            "is my laptop charging",
        ]


        uptime_phrases = [
            "system uptime",
            "computer uptime",
            "how long has my computer been on",
            "how long has my system been running",
        ]


        if command in top_memory_phrases:
            query_type = "TOP_MEMORY"

        elif command in top_cpu_phrases:
            query_type = "TOP_CPU"

        elif command in health_phrases:
            query_type = "HEALTH"

        elif command in storage_phrases:
            query_type = "STORAGE"

        elif command in drives_phrases:
            query_type = "DRIVES"

        elif command in process_count_phrases:
            query_type = "PROCESS_COUNT"

        elif command in top_processes_phrases:
            query_type = "TOP_PROCESSES"

        elif command in network_phrases:
            query_type = "NETWORK"

        elif command in battery_phrases:
            query_type = "BATTERY"

        elif command in uptime_phrases:
            query_type = "UPTIME"


        if query_type is None:

            return {
                "handled": False,
                "type": None,
                "message": None,
            }


        state = (
            self.get_state()
        )


        formatters = {
            "TOP_MEMORY":
                self.format_top_memory,

            "TOP_CPU":
                self.format_top_cpu,

            "HEALTH":
                self.format_system_health,

            "STORAGE":
                self.format_storage,

            "DRIVES":
                self.format_drives,

            "PROCESS_COUNT":
                self.format_process_count,

            "TOP_PROCESSES":
                self.format_top_processes,

            "NETWORK":
                self.format_network,

            "BATTERY":
                self.format_battery,

            "UPTIME":
                self.format_uptime,
        }


        message = (
            formatters[
                query_type
            ](
                state
            )
        )


        result = {
            "handled": True,
            "type": query_type,
            "message": message,
            "process_name": None,
            "process_cpu_percent": None,
            "process_memory_mb": None,
        }


        if query_type == "TOP_CPU":

            process = (
                state.highest_cpu_process()
            )

            if process is not None:

                result[
                    "process_name"
                ] = process.name

                result[
                    "process_cpu_percent"
                ] = process.cpu_percent

                result[
                    "process_memory_mb"
                ] = process.memory_mb


        elif query_type == "TOP_MEMORY":

            process = (
                state.highest_memory_process()
            )

            if process is not None:

                result[
                    "process_name"
                ] = process.name

                result[
                    "process_cpu_percent"
                ] = process.cpu_percent

                result[
                    "process_memory_mb"
                ] = process.memory_mb


        return result
