import ipaddress
import json
import socket
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field

import psutil


@dataclass
class WindowsSecurityTelemetry:
    firewall_profiles: dict = field(default_factory=dict)
    firewall_enabled: bool | None = None

    defender_available: bool = False
    defender_active: bool | None = None
    realtime_protection: bool | None = None
    antivirus_enabled: bool | None = None
    antispyware_enabled: bool | None = None
    signatures_out_of_date: bool | None = None

    network_name: str | None = None
    network_category: str | None = None
    network_interface: str | None = None

    active_connections: int = 0
    listening_ports: int = 0
    external_connections: int = 0

    # Top processes owning TCP connections.
    # Each item:
    # {
    #   "pid": int,
    #   "name": str,
    #   "connections": int,
    #   "external": int,
    #   "listening": int,
    #   "exe": str | None,
    # }
    process_connections: list = field(default_factory=list)

    error: str | None = None


class WindowsSecurityTelemetryService:
    """
    Read-only Windows security telemetry.

    PowerShell:
    - Microsoft Defender status
    - Firewall profiles
    - Network profile/category

    psutil:
    - TCP connection totals
    - process-to-connection ownership
    - listening sockets
    - external connection counts

    No security settings are modified.
    """

    def __init__(self, timeout_seconds=12):
        self.timeout_seconds = timeout_seconds


    # =====================================================
    # POWERSHELL
    # =====================================================

    def _run_powershell_json(self, command):
        wrapped = (
            "$ProgressPreference='SilentlyContinue';"
            "$ErrorActionPreference='Stop';"
            + command
            + " | ConvertTo-Json -Depth 6 -Compress"
        )

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                wrapped,
            ],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            ),
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or "PowerShell command failed."
            )

        output = result.stdout.strip()

        if not output:
            return None

        return json.loads(output)


    # =====================================================
    # DEFENDER
    # =====================================================

    def get_defender_status(self):
        try:
            data = self._run_powershell_json(
                "Get-MpComputerStatus | "
                "Select-Object "
                "AMRunningMode,"
                "AntivirusEnabled,"
                "AntispywareEnabled,"
                "RealTimeProtectionEnabled,"
                "OnAccessProtectionEnabled,"
                "DefenderSignaturesOutOfDate"
            )

            if not data:
                return {
                    "available": False
                }

            running_mode = str(
                data.get(
                    "AMRunningMode",
                    ""
                )
            ).strip().lower()

            defender_active = (
                running_mode
                not in {
                    "",
                    "not running",
                    "disabled",
                    "passive",
                }
            )

            return {
                "available": True,
                "active": defender_active,
                "realtime": bool(
                    data.get(
                        "RealTimeProtectionEnabled"
                    )
                ),
                "antivirus": bool(
                    data.get(
                        "AntivirusEnabled"
                    )
                ),
                "antispyware": bool(
                    data.get(
                        "AntispywareEnabled"
                    )
                ),
                "signatures_out_of_date": bool(
                    data.get(
                        "DefenderSignaturesOutOfDate"
                    )
                ),
                "running_mode": data.get(
                    "AMRunningMode"
                ),
            }

        except Exception as error:
            return {
                "available": False,
                "error": str(error),
            }


    # =====================================================
    # FIREWALL
    # =====================================================

    def get_firewall_status(self):
        try:
            data = self._run_powershell_json(
                "Get-NetFirewallProfile -PolicyStore ActiveStore | "
                "Select-Object Name,Enabled"
            )

            if data is None:
                profiles = []

            elif isinstance(
                data,
                list
            ):
                profiles = data

            else:
                profiles = [
                    data
                ]

            profile_map = {
                str(
                    item.get(
                        "Name",
                        "UNKNOWN"
                    )
                ):
                    bool(
                        item.get(
                            "Enabled"
                        )
                    )
                for item
                in profiles
            }

            enabled = (
                bool(
                    profile_map
                )
                and all(
                    profile_map.values()
                )
            )

            return {
                "profiles": profile_map,
                "enabled": enabled,
            }

        except Exception as error:
            return {
                "profiles": {},
                "enabled": None,
                "error": str(error),
            }


    # =====================================================
    # NETWORK PROFILE
    # =====================================================

    @staticmethod
    def _normalize_category(value):
        if value is None:
            return None

        text = (
            str(
                value
            )
            .strip()
        )

        if not text:
            return None

        aliases = {
            "0": "Public",
            "1": "Private",
            "2": "DomainAuthenticated",
            "public": "Public",
            "private": "Private",
            "domain": "DomainAuthenticated",
            "domainauthenticated": "DomainAuthenticated",
        }

        return aliases.get(
            text.lower(),
            text
        )


    def _get_active_interface_alias(self):
        """
        Find the adapter that currently owns a default IPv4 gateway.
        """
        try:
            data = self._run_powershell_json(
                "Get-NetIPConfiguration | "
                "Where-Object { $_.IPv4DefaultGateway -ne $null } | "
                "Select-Object "
                "InterfaceAlias,InterfaceIndex,"
                "@{N='Gateway';E={$_.IPv4DefaultGateway.NextHop}}"
            )

            if not data:
                return None

            if isinstance(
                data,
                list
            ):
                item = data[0]

            else:
                item = data

            return {
                "interface": item.get(
                    "InterfaceAlias"
                ),
                "index": item.get(
                    "InterfaceIndex"
                ),
                "gateway": item.get(
                    "Gateway"
                ),
            }

        except Exception:
            return None


    def _registry_network_profile(
        self,
        preferred_name=None
    ):
        """
        Final fallback for Windows systems where
        Get-NetConnectionProfile returns an empty/unknown category.

        Registry Category:
            0 = Public
            1 = Private
            2 = Domain
        """
        try:
            data = self._run_powershell_json(
                "Get-ChildItem "
                "'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\NetworkList\\Profiles' "
                "| ForEach-Object { "
                "$p=Get-ItemProperty $_.PSPath; "
                "[PSCustomObject]@{"
                "ProfileName=$p.ProfileName;"
                "Category=$p.Category;"
                "DateLastConnected=$p.DateLastConnected"
                "} "
                "} | Select-Object ProfileName,Category,DateLastConnected"
            )

            if not data:
                return {}

            items = (
                data
                if isinstance(
                    data,
                    list
                )
                else [
                    data
                ]
            )

            selected = None

            if preferred_name:

                for item in items:

                    if (
                        str(
                            item.get(
                                "ProfileName",
                                ""
                            )
                        ).strip().lower()
                        ==
                        str(
                            preferred_name
                        ).strip().lower()
                    ):

                        selected = item
                        break

            if selected is None:

                # PowerShell usually returns registry enumeration
                # newest-ish last; when no exact name exists we
                # simply use the final populated profile.
                populated = [
                    item
                    for item
                    in items
                    if item.get(
                        "ProfileName"
                    )
                ]

                if populated:
                    selected = populated[-1]

            if not selected:
                return {}

            return {
                "name": selected.get(
                    "ProfileName"
                ),
                "category": self._normalize_category(
                    selected.get(
                        "Category"
                    )
                ),
                "source": "REGISTRY",
            }

        except Exception:
            return {}


    def get_network_profile(self):
        """
        Resolution order:

        1. Get-NetConnectionProfile
        2. Active default-gateway interface + explicit profile lookup
        3. Windows NetworkList registry profile

        UNKNOWN is returned only after all three methods fail.
        """
        errors = []

        # -------------------------------------------------
        # 1. NORMAL PROFILE QUERY
        # -------------------------------------------------

        try:
            data = self._run_powershell_json(
                "Get-NetConnectionProfile | "
                "Select-Object "
                "Name,InterfaceAlias,InterfaceIndex,"
                "NetworkCategory,"
                "IPv4Connectivity,IPv6Connectivity"
            )

            if data is None:
                profiles = []

            elif isinstance(
                data,
                list
            ):
                profiles = data

            else:
                profiles = [
                    data
                ]

            selected = None

            # Prefer a profile with real IPv4 connectivity.
            for item in profiles:

                connectivity = (
                    str(
                        item.get(
                            "IPv4Connectivity",
                            ""
                        )
                    )
                    .strip()
                    .lower()
                )

                if connectivity in {
                    "internet",
                    "localnetwork",
                    "subnet",
                }:

                    selected = item
                    break

            if selected is None and profiles:
                selected = profiles[0]

            if selected:

                category = self._normalize_category(
                    selected.get(
                        "NetworkCategory"
                    )
                )

                if category:

                    return {
                        "name": selected.get(
                            "Name"
                        ),
                        "category": category,
                        "interface": selected.get(
                            "InterfaceAlias"
                        ),
                        "source": "NET_CONNECTION_PROFILE",
                    }

                preferred_name = selected.get(
                    "Name"
                )

            else:
                preferred_name = None

        except Exception as error:
            errors.append(
                str(
                    error
                )
            )
            preferred_name = None

        # -------------------------------------------------
        # 2. ACTIVE INTERFACE LOOKUP
        # -------------------------------------------------

        active = (
            self._get_active_interface_alias()
        )

        if active:

            alias = active.get(
                "interface"
            )

            if alias:

                try:
                    data = self._run_powershell_json(
                        "Get-NetConnectionProfile "
                        f"-InterfaceAlias '{str(alias).replace(chr(39), chr(39) * 2)}' "
                        "| Select-Object "
                        "Name,InterfaceAlias,NetworkCategory"
                    )

                    if data:

                        category = self._normalize_category(
                            data.get(
                                "NetworkCategory"
                            )
                        )

                        if category:

                            return {
                                "name": data.get(
                                    "Name"
                                ),
                                "category": category,
                                "interface": data.get(
                                    "InterfaceAlias"
                                )
                                or alias,
                                "source": "ACTIVE_INTERFACE",
                            }

                        preferred_name = (
                            data.get(
                                "Name"
                            )
                            or preferred_name
                        )

                except Exception as error:
                    errors.append(
                        str(
                            error
                        )
                    )

        # -------------------------------------------------
        # 3. REGISTRY FALLBACK
        # -------------------------------------------------

        registry = self._registry_network_profile(
            preferred_name=preferred_name
        )

        if registry:

            if active:

                registry[
                    "interface"
                ] = active.get(
                    "interface"
                )

            return registry

        result = {
            "name": preferred_name,
            "category": None,
            "interface": (
                active.get(
                    "interface"
                )
                if active
                else None
            ),
        }

        if errors:
            result[
                "error"
            ] = " | ".join(
                errors
            )

        return result


    # =====================================================
    # PROCESS / NETWORK CONNECTION MAPPING
    # =====================================================

    @staticmethod
    def _address_value(address):
        if not address:
            return ""

        if hasattr(
            address,
            "ip"
        ):
            return str(
                address.ip
            )

        if isinstance(
            address,
            tuple
        ) and address:
            return str(
                address[0]
            )

        return str(
            address
        )


    @staticmethod
    def _port_value(address):
        if not address:
            return None

        if hasattr(
            address,
            "port"
        ):
            return int(
                address.port
            )

        if (
            isinstance(
                address,
                tuple
            )
            and len(
                address
            ) > 1
        ):
            return int(
                address[1]
            )

        return None


    @staticmethod
    def _is_external_address(address):
        address = (
            str(
                address
                or ""
            )
            .strip()
        )

        if not address:
            return False

        try:
            ip = ipaddress.ip_address(
                address.split(
                    "%"
                )[0]
            )

            return not (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_unspecified
                or ip.is_reserved
            )

        except ValueError:
            return False


    def get_tcp_summary(self):
        """
        Builds one read-only connection snapshot using psutil and
        groups sockets by owning process.
        """
        process_map = defaultdict(
            lambda: {
                "pid": None,
                "name": "UNKNOWN",
                "connections": 0,
                "external": 0,
                "listening": 0,
                "exe": None,
            }
        )

        active = 0
        external = 0
        listening_ports = set()

        errors = []

        try:
            connections = psutil.net_connections(
                kind="tcp"
            )

        except Exception as error:
            return {
                "active": 0,
                "listening_ports": 0,
                "external": 0,
                "processes": [],
                "error": str(
                    error
                ),
            }

        process_cache = {}

        for connection in connections:

            status = (
                str(
                    connection.status
                    or ""
                )
                .upper()
            )

            pid = (
                connection.pid
            )

            local_port = self._port_value(
                connection.laddr
            )

            remote_ip = self._address_value(
                connection.raddr
            )

            if status == "ESTABLISHED":
                active += 1

            if status == "LISTEN":

                if local_port is not None:

                    listening_ports.add(
                        local_port
                    )

            is_external = (
                status == "ESTABLISHED"
                and self._is_external_address(
                    remote_ip
                )
            )

            if is_external:
                external += 1

            if pid is None:
                key = (
                    "SYSTEM",
                    0
                )

            else:
                key = (
                    "PID",
                    int(
                        pid
                    )
                )

            record = process_map[
                key
            ]

            record[
                "pid"
            ] = (
                int(
                    pid
                )
                if pid is not None
                else None
            )

            # Count established sockets as connections.
            if status == "ESTABLISHED":

                record[
                    "connections"
                ] += 1

            if is_external:

                record[
                    "external"
                ] += 1

            if status == "LISTEN":

                record[
                    "listening"
                ] += 1

            if pid is not None:

                if pid not in process_cache:

                    try:
                        process = psutil.Process(
                            pid
                        )

                        process_cache[
                            pid
                        ] = {
                            "name": (
                                process.name()
                                or f"PID {pid}"
                            ),
                            "exe": (
                                process.exe()
                                or None
                            ),
                        }

                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                    ):

                        process_cache[
                            pid
                        ] = {
                            "name": f"PID {pid}",
                            "exe": None,
                        }

                    except Exception as error:
                        errors.append(
                            str(
                                error
                            )
                        )

                        process_cache[
                            pid
                        ] = {
                            "name": f"PID {pid}",
                            "exe": None,
                        }

                process_info = (
                    process_cache[
                        pid
                    ]
                )

                record[
                    "name"
                ] = process_info[
                    "name"
                ]

                record[
                    "exe"
                ] = process_info[
                    "exe"
                ]

            else:
                record[
                    "name"
                ] = "SYSTEM"


        process_rows = [
            value
            for value
            in process_map.values()
            if (
                value[
                    "connections"
                ] > 0
                or value[
                    "listening"
                ] > 0
            )
        ]

        # External connections first, then overall connection count.
        process_rows.sort(
            key=lambda item: (
                item.get(
                    "external",
                    0
                ),
                item.get(
                    "connections",
                    0
                ),
                item.get(
                    "listening",
                    0
                ),
            ),
            reverse=True
        )

        result = {
            "active": active,
            "listening_ports": len(
                listening_ports
            ),
            "external": external,
            "processes": process_rows[
                :12
            ],
        }

        if errors:
            result[
                "process_error"
            ] = (
                errors[0]
            )

        return result


    # =====================================================
    # FULL SNAPSHOT
    # =====================================================

    def collect_snapshot(self):
        snapshot = (
            WindowsSecurityTelemetry()
        )

        defender = (
            self.get_defender_status()
        )

        firewall = (
            self.get_firewall_status()
        )

        profile = (
            self.get_network_profile()
        )

        tcp = (
            self.get_tcp_summary()
        )


        snapshot.defender_available = (
            defender.get(
                "available",
                False
            )
        )

        snapshot.defender_active = (
            defender.get(
                "active"
            )
        )

        snapshot.realtime_protection = (
            defender.get(
                "realtime"
            )
        )

        snapshot.antivirus_enabled = (
            defender.get(
                "antivirus"
            )
        )

        snapshot.antispyware_enabled = (
            defender.get(
                "antispyware"
            )
        )

        snapshot.signatures_out_of_date = (
            defender.get(
                "signatures_out_of_date"
            )
        )


        snapshot.firewall_profiles = (
            firewall.get(
                "profiles",
                {}
            )
        )

        snapshot.firewall_enabled = (
            firewall.get(
                "enabled"
            )
        )


        snapshot.network_name = (
            profile.get(
                "name"
            )
        )

        snapshot.network_category = (
            profile.get(
                "category"
            )
        )

        snapshot.network_interface = (
            profile.get(
                "interface"
            )
        )


        snapshot.active_connections = (
            tcp.get(
                "active",
                0
            )
        )

        snapshot.listening_ports = (
            tcp.get(
                "listening_ports",
                0
            )
        )

        snapshot.external_connections = (
            tcp.get(
                "external",
                0
            )
        )

        snapshot.process_connections = (
            tcp.get(
                "processes",
                []
            )
        )


        errors = [
            value.get(
                "error"
            )
            for value in [
                defender,
                firewall,
                profile,
                tcp,
            ]
            if value.get(
                "error"
            )
        ]

        if errors:

            snapshot.error = (
                " | ".join(
                    errors
                )
            )

        return snapshot
