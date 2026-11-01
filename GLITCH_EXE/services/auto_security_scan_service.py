import ctypes
import threading
import time
from pathlib import Path


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class AutoSecurityScanService:
    """
    Background / idle scanner for GLITCH.

    Behavior:
    - Runs only while Windows is awake.
    - Waits until the user has been idle for a configured period.
    - Avoids scanning while GLITCH is actively busy.
    - Uses incremental file metadata so unchanged files are skipped.
    - Never quarantines or deletes automatically.
    """

    def __init__(
        self,
        security_engine,
        scan_targets=None,
        idle_seconds=120,
        poll_seconds=15,
        max_files_per_pass=250,
        is_glitch_busy=None,
        on_scan_complete=None,
        on_scan_error=None,
    ):

        self.security_engine = security_engine

        self.scan_targets = [
            Path(target).expanduser()
            for target in (
                scan_targets
                or [
                    Path.home() / "Downloads",
                ]
            )
        ]

        self.idle_seconds = int(idle_seconds)
        self.poll_seconds = int(poll_seconds)
        self.max_files_per_pass = int(
            max_files_per_pass
        )

        self.is_glitch_busy = (
            is_glitch_busy
            or (lambda: False)
        )

        self._last_glitch_activity = (
            time.monotonic()
        )

        self.on_scan_complete = on_scan_complete
        self.on_scan_error = on_scan_error

        self._stop_event = threading.Event()
        self._thread = None

        # path -> (size, modified_ns)
        self._fingerprints = {}

        self.enabled = True


    # ---------------------------------------------------------
    # GLITCH ACTIVITY
    # ---------------------------------------------------------

    def notify_glitch_activity(
        self
    ):

        self._last_glitch_activity = (
            time.monotonic()
        )


    def glitch_idle_seconds(
        self
    ):

        return max(
            0.0,
            time.monotonic()
            - self._last_glitch_activity
        )


    # ---------------------------------------------------------
    # WINDOWS IDLE TIME
    # ---------------------------------------------------------

    def get_idle_seconds(
        self
    ):

        try:

            last_input = LASTINPUTINFO()

            last_input.cbSize = (
                ctypes.sizeof(
                    LASTINPUTINFO
                )
            )

            if not ctypes.windll.user32.GetLastInputInfo(
                ctypes.byref(
                    last_input
                )
            ):

                return 0.0


            tick_count = (
                ctypes.windll.kernel32
                .GetTickCount()
            )


            elapsed_ms = (
                tick_count
                - last_input.dwTime
            )


            return max(
                0.0,
                elapsed_ms / 1000.0
            )

        except Exception:

            return 0.0


    # ---------------------------------------------------------
    # START / STOP
    # ---------------------------------------------------------

    def start(
        self
    ):

        if (
            self._thread is not None
            and self._thread.is_alive()
        ):

            return


        self._stop_event.clear()


        self._thread = threading.Thread(
            target=self._run_loop,
            name="GLITCH-AutoSecurityScan",
            daemon=True,
        )


        self._thread.start()


    def stop(
        self
    ):

        self._stop_event.set()


    # ---------------------------------------------------------
    # SCAN LOOP
    # ---------------------------------------------------------

    def _run_loop(
        self
    ):

        while not self._stop_event.is_set():

            try:

                if not self.enabled:

                    self._sleep()
                    continue


                if self.is_glitch_busy():

                    self._sleep()
                    continue


                if (
                    self.glitch_idle_seconds()
                    < self.idle_seconds
                ):

                    self._sleep()
                    continue


                if (
                    self.get_idle_seconds()
                    < self.idle_seconds
                ):

                    self._sleep()
                    continue


                for target in self.scan_targets:

                    if self._stop_event.is_set():
                        return


                    if self.is_glitch_busy():
                        break


                    if not target.exists():
                        continue


                    results = (
                        self.scan_incremental_target(
                            target
                        )
                    )


                    if (
                        results
                        and self.on_scan_complete
                        is not None
                    ):

                        try:

                            self.on_scan_complete(
                                str(target),
                                results
                            )

                        except Exception:

                            pass


            except Exception as error:

                if (
                    self.on_scan_error
                    is not None
                ):

                    try:

                        self.on_scan_error(
                            str(error)
                        )

                    except Exception:

                        pass


            self._sleep()


    def _sleep(
        self
    ):

        self._stop_event.wait(
            self.poll_seconds
        )


    # ---------------------------------------------------------
    # INCREMENTAL SCAN
    # ---------------------------------------------------------

    def scan_incremental_target(
        self,
        target
    ):

        target = (
            Path(target)
            .expanduser()
        )


        results = []
        scanned_this_pass = 0


        try:

            iterator = (
                target.rglob("*")
            )

        except Exception:

            return results


        for path in iterator:

            if (
                scanned_this_pass
                >= self.max_files_per_pass
            ):

                break


            if self._stop_event.is_set():
                break


            if self.is_glitch_busy():
                break


            try:

                if not path.is_file():
                    continue


                stat = path.stat()


                fingerprint = (
                    stat.st_size,
                    stat.st_mtime_ns,
                )


                key = str(
                    path.resolve()
                )


                if (
                    self._fingerprints.get(
                        key
                    )
                    == fingerprint
                ):

                    continue


                # Scan without mutating the shared SecurityState
                # for every individual file. The full idle batch
                # is committed once at the end of the pass.
                result = (
                    self.security_engine
                    .scan_file(
                        path,
                        update_state=False
                    )
                )


                self._fingerprints[
                    key
                ] = fingerprint


                results.append(
                    result
                )


                scanned_this_pass += 1


            except (
                PermissionError,
                OSError
            ):

                continue


        if results:

            self.security_engine.record_background_results(
                target,
                results
            )


        return results
