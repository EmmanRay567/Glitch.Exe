"""
core/perf_monitor.py

Finds what makes GLITCH stutter.

A heartbeat timer ticks on the Qt (UI) thread every 50 ms. A watchdog
thread checks it; when the UI thread hasn't ticked for longer than the
threshold, the watchdog grabs the UI thread's current Python stack and
prints where it is stuck, e.g.

    GLITCH PERF // UI froze 340 ms in
        ui/main_window.py:4211 update_system_stats
        services/weather_service.py:88 fetch

If the stack is only Qt's own event loop, the time went into painting
(usually a big animated widget repainting the whole window).

Every 60 s it prints a short summary of the worst offenders, so you can
send me the console output and I can fix exactly those spots.

Enable/disable with GLITCH_PERF=1/0 in .env (on by default, it costs
almost nothing). GLITCH_PERF_THRESHOLD_MS sets the threshold (150).
"""

import os
import sys
import threading
import time
import traceback
from collections import Counter

from PySide6.QtCore import QObject, QTimer


class PerfMonitor(QObject):

    def __init__(self, parent=None, threshold_ms=None):

        super().__init__(parent)

        self.enabled = os.getenv("GLITCH_PERF", "1") != "0"

        self.threshold = (
            float(threshold_ms or os.getenv("GLITCH_PERF_THRESHOLD_MS", "150")) / 1000.0
        )

        self._main_id = threading.get_ident()

        self._beat = time.perf_counter()

        self._stall_reported = False

        self._stall_start = 0.0

        self._stall_where = ""

        self._worst = Counter()

        self._totals = Counter()

        self._timer = QTimer(self)

        self._timer.setInterval(50)

        self._timer.timeout.connect(self._heartbeat)

        if self.enabled:

            self._timer.start()

            threading.Thread(target=self._watch, daemon=True).start()

            threading.Thread(target=self._summaries, daemon=True).start()

            print(
                f"GLITCH PERF // watching for UI freezes > {int(self.threshold * 1000)} ms"
            )

    # -----------------------------------------------------

    def _heartbeat(self):

        now = time.perf_counter()

        if self._stall_reported:

            duration = (now - self._stall_start) * 1000

            print(f"GLITCH PERF //   ...recovered after {int(duration)} ms")

            self._totals[self._stall_where] += duration

            self._worst[self._stall_where] = max(self._worst[self._stall_where], duration)

            self._stall_reported = False

        self._beat = now

    # -----------------------------------------------------

    def _where(self):

        frame = sys._current_frames().get(self._main_id)

        if frame is None:

            return "unknown"

        stack = traceback.extract_stack(frame)

        project = [
            entry
            for entry in stack
            if "site-packages" not in entry.filename
            and "lib" + os.sep + "python" not in entry.filename.lower()
            and not entry.filename.endswith("perf_monitor.py")
        ]

        if not project or (len(project) == 1 and project[-1].name in ("<module>", "main")):

            return "Qt painting / event loop (no Python code running)"

        lines = []

        for entry in project[-4:]:

            short = os.sep.join(entry.filename.split(os.sep)[-2:])

            lines.append(f"{short}:{entry.lineno} {entry.name}")

        return "\n        ".join(reversed(lines))

    def _watch(self):

        while True:

            time.sleep(0.03)

            lag = time.perf_counter() - self._beat - 0.05

            if lag > self.threshold and not self._stall_reported:

                self._stall_reported = True

                self._stall_start = self._beat + 0.05

                self._stall_where = self._where()

                print(
                    f"GLITCH PERF // UI froze {int(lag * 1000)} ms in\n"
                    f"        {self._stall_where}"
                )

    def _summaries(self):

        while True:

            time.sleep(60)

            if not self._totals:

                continue

            print("GLITCH PERF // worst UI freezes in the last minute:")

            for where, total in self._totals.most_common(3):

                first = where.split("\n")[0].strip()

                print(
                    f"        {int(total)} ms total, worst {int(self._worst[where])} ms: {first}"
                )

            self._totals.clear()

            self._worst.clear()
