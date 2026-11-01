from __future__ import annotations

import re
import subprocess
from pathlib import Path

import psutil


class SecurityActionService:
    """
    Executes explicitly confirmed Phase 3 security actions.

    IMPORTANT:
    - No method is called automatically by anomaly detection.
    - MainWindow must obtain explicit user confirmation first.
    - Process termination is graceful only.
    """

    def __init__(
        self,
        security_engine
    ):

        self.security_engine = (
            security_engine
        )

    @staticmethod
    def _path_from_finding(
        finding
    ):

        value = str(
            finding.get(
                "process_path"
            )
            or ""
        ).strip()

        return (
            Path(
                value
            )
            if value
            else None
        )

    def quarantine_finding(
        self,
        finding
    ):

        path = self._path_from_finding(
            finding
        )

        if path is None:

            return self._fail(
                "No executable path is available for this finding."
            )

        if (
            not path.exists()
            or not path.is_file()
        ):

            return self._fail(
                f"The executable is no longer present at {path}."
            )

        try:

            scan_result = (
                self.security_engine
                .scan_file(
                    path
                )
            )

            metadata = (
                self.security_engine
                .quarantine(
                    scan_result
                )
            )

            return {
                "success": True,
                "message":
                    f"Quarantined {path.name}.",
                "details":
                    metadata,
            }

        except Exception as error:

            return self._fail(
                "Quarantine failed. "
                "If the process is still running, "
                "terminate it first and try again. "
                f"Details: {error}"
            )

    def terminate_finding(
        self,
        finding
    ):

        pid = finding.get(
            "pid"
        )

        expected_path = str(
            finding.get(
                "process_path"
            )
            or ""
        ).strip()

        expected_name = str(
            finding.get(
                "process_name"
            )
            or ""
        ).strip()

        if pid is None:

            return self._fail(
                "No live PID is recorded for this finding. "
                "Wait for the next security telemetry refresh "
                "and try again."
            )

        try:

            process = (
                psutil.Process(
                    int(
                        pid
                    )
                )
            )

        except (
            psutil.NoSuchProcess,
            ValueError,
            TypeError
        ):

            return self._fail(
                "That process is no longer running."
            )

        except psutil.AccessDenied:

            return self._fail(
                "Windows denied access to that process."
            )

        try:

            live_name = (
                process.name()
                or ""
            )

        except Exception:

            live_name = ""

        try:

            live_path = (
                process.exe()
                or ""
            )

        except Exception:

            live_path = ""

        # Protect against PID reuse.
        # Before terminating a process,
        # make sure PID still belongs
        # to the expected executable.

        if (
            expected_path
            and live_path
        ):

            if (
                Path(
                    expected_path
                ).resolve()
                !=
                Path(
                    live_path
                ).resolve()
            ):

                return self._fail(
                    "The PID now belongs to a different executable, "
                    "so GLITCH refused to terminate it."
                )

        elif (
            expected_name
            and live_name
        ):

            if (
                expected_name.lower()
                !=
                live_name.lower()
            ):

                return self._fail(
                    "The PID now belongs to a different process, "
                    "so GLITCH refused to terminate it."
                )

        try:

            process.terminate()

            try:

                process.wait(
                    timeout=3
                )

                return {
                    "success": True,
                    "message":
                        (
                            "Terminated "
                            f"{live_name or expected_name or pid}."
                        ),
                    "details": {
                        "pid":
                            int(
                                pid
                            )
                    },
                }

            except psutil.TimeoutExpired:

                return self._fail(
                    "The process did not exit after a graceful "
                    "terminate request. GLITCH did not force-kill it."
                )

        except psutil.AccessDenied:

            return self._fail(
                "Windows denied permission to terminate that process."
            )

        except psutil.NoSuchProcess:

            return self._fail(
                "The process exited before the action completed."
            )

        except Exception as error:

            return self._fail(
                f"Process termination failed: {error}"
            )

    def block_finding(
        self,
        finding
    ):

        path = self._path_from_finding(
            finding
        )

        if path is None:

            return self._fail(
                "No executable path is available for a firewall rule."
            )

        if not path.exists():

            return self._fail(
                f"The executable is no longer present at {path}."
            )

        safe_name = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            path.name
        )[:50]

        rule_name = (
            f"GLITCH_BLOCK_{safe_name}"
        )

        command = [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={rule_name}",
            "dir=out",
            "action=block",
            f"program={str(path)}",
            "enable=yes",
            "profile=any",
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0
                ),
            )

        except FileNotFoundError:

            return self._fail(
                "Windows netsh is unavailable."
            )

        except Exception as error:

            return self._fail(
                f"Firewall command failed: {error}"
            )

        output = (
            result.stdout
            or result.stderr
            or ""
        ).strip()

        if result.returncode != 0:

            return self._fail(
                "Windows did not create the firewall rule. "
                "GLITCH may need to be run as Administrator. "
                f"Details: {output or 'unknown error'}"
            )

        return {
            "success": True,
            "message":
                (
                    "Blocked outbound network access for "
                    f"{path.name}."
                ),
            "details": {
                "rule_name":
                    rule_name,
                "path":
                    str(
                        path
                    ),
            },
        }

    @staticmethod
    def _fail(
        message
    ):

        return {
            "success": False,
            "message":
                str(
                    message
                ),
            "details":
                None,
        }
