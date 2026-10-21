import math


from PySide6.QtCore import (
    Qt,
    QTimer,
    QPointF,
)

from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
)

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QProgressBar,
)


# =========================================================
# HOLOGRAPHIC COMPUTER
# =========================================================

class HologramComputer(QWidget):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.rotation = 0.0
        self.float_phase = 0.0
        self.scan_position = 0.0

        self.cpu = 0
        self.ram = 0
        self.disk = 0

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.animate_hologram
        )

        self.timer.start(
            30
        )


    def set_stats(
        self,
        cpu,
        ram,
        disk
    ):

        self.cpu = cpu
        self.ram = ram
        self.disk = disk

        self.update()


    def animate_hologram(self):

        self.rotation += 0.8

        if self.rotation >= 360:
            self.rotation = 0

        self.float_phase += 0.05

        self.scan_position += 3

        if self.scan_position > self.height():
            self.scan_position = 0

        self.update()


    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        w = self.width()
        h = self.height()

        center_x = w / 2

        float_offset = (
            math.sin(
                self.float_phase
            )
            * 7
        )

        center_y = (
            h / 2
            + float_offset
        )


        # =================================================
        # AMBIENT GLOW
        # =================================================

        for radius, alpha in [

            (150, 15),
            (120, 22),
            (90, 30),

        ]:

            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(
                QColor(
                    57,
                    255,
                    120,
                    alpha
                )
            )

            painter.drawEllipse(
                QPointF(
                    center_x,
                    center_y
                ),
                radius,
                radius * 0.45
            )


        # =================================================
        # ROTATING HUD RINGS
        # =================================================

        painter.save()

        painter.translate(
            center_x,
            center_y
        )

        painter.rotate(
            self.rotation
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    100
                ),
                2
            )
        )

        painter.drawEllipse(
            QPointF(0, 0),
            125,
            55
        )

        painter.drawArc(
            -145,
            -65,
            290,
            130,
            20 * 16,
            80 * 16
        )

        painter.drawArc(
            -145,
            -65,
            290,
            130,
            200 * 16,
            70 * 16
        )

        painter.restore()


        # =================================================
        # COMPUTER DISPLAY
        # =================================================

        screen_width = 180
        screen_height = 110

        screen_left = (
            center_x
            - screen_width / 2
        )

        screen_top = (
            center_y
            - 95
        )


        painter.setBrush(
            QColor(
                0,
                20,
                12,
                55
            )
        )

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    210
                ),
                2
            )
        )

        painter.drawRoundedRect(
            int(screen_left),
            int(screen_top),
            screen_width,
            screen_height,
            8,
            8
        )


        # Internal circuit grid
        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    55
                ),
                1
            )
        )


        for x in range(
            int(screen_left) + 15,
            int(screen_left + screen_width),
            20
        ):

            painter.drawLine(
                x,
                int(screen_top + 10),
                x,
                int(
                    screen_top
                    + screen_height
                    - 10
                )
            )


        for y in range(
            int(screen_top) + 15,
            int(screen_top + screen_height),
            18
        ):

            painter.drawLine(
                int(screen_left + 10),
                y,
                int(
                    screen_left
                    + screen_width
                    - 10
                ),
                y
            )


        # =================================================
        # CENTER CHIP
        # =================================================

        painter.setBrush(
            QColor(
                57,
                255,
                120,
                45
            )
        )

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    190
                ),
                1
            )
        )

        painter.drawRect(
            int(center_x - 25),
            int(screen_top + 30),
            50,
            40
        )


        painter.setFont(
            QFont(
                "Consolas",
                8
            )
        )

        painter.setPen(
            QColor(
                100,
                255,
                150
            )
        )

        painter.drawText(
            int(center_x - 18),
            int(screen_top + 55),
            "CORE"
        )


        # =================================================
        # BASE / KEYBOARD
        # =================================================

        base_y = (
            screen_top
            + screen_height
            + 8
        )


        base_points = [

            QPointF(
                center_x - 90,
                base_y
            ),

            QPointF(
                center_x + 90,
                base_y
            ),

            QPointF(
                center_x + 125,
                base_y + 45
            ),

            QPointF(
                center_x - 125,
                base_y + 45
            ),
        ]


        painter.setBrush(
            QColor(
                0,
                30,
                15,
                45
            )
        )

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    185
                ),
                2
            )
        )


        painter.drawPolygon(
            base_points
        )


        # Keyboard grid
        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    60
                ),
                1
            )
        )


        for i in range(7):

            y = (
                base_y
                + 8
                + i * 5
            )

            painter.drawLine(
                int(center_x - 90),
                int(y),
                int(center_x + 90),
                int(y)
            )


        # =================================================
        # SUPPORT STAND
        # =================================================

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    140
                ),
                2
            )
        )

        painter.drawLine(
            int(center_x),
            int(base_y + 45),
            int(center_x),
            int(base_y + 75)
        )


        painter.drawEllipse(
            QPointF(
                center_x,
                base_y + 82
            ),
            55,
            12
        )


        # =================================================
        # SCAN LINE
        # =================================================

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    70
                ),
                1
            )
        )

        painter.drawLine(
            20,
            int(self.scan_position),
            w - 20,
            int(self.scan_position)
        )


        # =================================================
        # DIAGNOSTIC CALLOUTS
        # =================================================

        painter.setFont(
            QFont(
                "Consolas",
                9
            )
        )


        self.draw_callout(
            painter,
            center_x - 200,
            center_y - 80,
            center_x - 90,
            center_y - 55,
            f"CPU // {self.cpu:.0f}%"
        )


        self.draw_callout(
            painter,
            center_x + 200,
            center_y - 40,
            center_x + 90,
            center_y - 30,
            f"RAM // {self.ram:.0f}%"
        )


        self.draw_callout(
            painter,
            center_x - 190,
            center_y + 90,
            center_x - 105,
            center_y + 60,
            f"SSD // {self.disk:.0f}%"
        )


        painter.end()


    def draw_callout(
        self,
        painter,
        text_x,
        text_y,
        target_x,
        target_y,
        text
    ):

        painter.setPen(
            QPen(
                QColor(
                    57,
                    255,
                    120,
                    130
                ),
                1
            )
        )


        painter.drawLine(
            int(text_x),
            int(text_y + 4),
            int(target_x),
            int(target_y)
        )


        painter.setPen(
            QColor(
                125,
                255,
                165,
                220
            )
        )


        painter.drawText(
            int(text_x),
            int(text_y),
            text
        )


# =========================================================
# STAT BLOCK
# =========================================================

class MatrixStat(QFrame):

    def __init__(
        self,
        title,
        parent=None
    ):

        super().__init__(
            parent
        )


        self.setStyleSheet(
            """
            QFrame {
                background: rgba(0, 20, 12, 115);
                border: 1px solid rgba(57, 255, 120, 70);
                border-radius: 7px;
            }
            """
        )


        layout = QVBoxLayout(
            self
        )


        self.title_label = QLabel(
            title
        )

        self.title_label.setStyleSheet(
            """
            color: rgba(170,255,195,150);
            font-family: Consolas;
            font-size: 9px;
            """
        )


        self.value_label = QLabel(
            "---"
        )

        self.value_label.setStyleSheet(
            """
            color: #39ff78;
            font-family: Consolas;
            font-size: 14px;
            font-weight: bold;
            """
        )


        self.bar = QProgressBar()

        self.bar.setRange(
            0,
            100
        )

        self.bar.setTextVisible(
            False
        )

        self.bar.setFixedHeight(
            5
        )

        self.bar.setStyleSheet(
            """
            QProgressBar {
                background: rgba(57,255,120,20);
                border: none;
            }

            QProgressBar::chunk {
                background: #39ff78;
            }
            """
        )


        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.value_label
        )

        layout.addWidget(
            self.bar
        )


    def set_value(
        self,
        text,
        percent=None
    ):

        self.value_label.setText(
            text
        )


        if percent is None:

            self.bar.hide()

        else:

            self.bar.show()

            self.bar.setValue(
                int(
                    max(
                        0,
                        min(
                            100,
                            percent
                        )
                    )
                )
            )


# =========================================================
# SYSTEM MATRIX PAGE
# =========================================================

class SystemMatrixWidget(QWidget):

    def __init__(
        self,
        system_monitoring_service,
        parent=None
    ):

        super().__init__(
            parent
        )


        # Phase 2:
        # The System Matrix no longer collects operating-system
        # telemetry directly. It reads from the shared Digital Twin.
        self.system_monitoring_service = (
            system_monitoring_service
        )


        self.previous_network_sent_mb = None
        self.previous_network_received_mb = None
        self.previous_network_timestamp = None


        self.build_ui()


        self.update_timer = QTimer(
            self
        )

        self.update_timer.timeout.connect(
            self.update_stats
        )

        self.update_timer.start(
            1000
        )


        self.update_stats()


    # =====================================================
    # BUILD UI
    # =====================================================

    def build_ui(self):

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            5,
            5,
            5,
            5
        )


        # Header
        header = QLabel(
            "// SYSTEM MATRIX\n"
            "GLITCH.EXE HARDWARE DIAGNOSTICS"
        )

        header.setStyleSheet(
            """
            color: #39ff78;
            font-family: Consolas;
            font-size: 18px;
            font-weight: bold;
            """
        )


        subtitle = QLabel(
            "LIVE HARDWARE // NETWORK // PROCESS TELEMETRY"
        )

        subtitle.setStyleSheet(
            """
            color: rgba(170,255,195,150);
            font-family: Consolas;
            font-size: 9px;
            """
        )


        root.addWidget(
            header
        )

        root.addWidget(
            subtitle
        )


        body = QHBoxLayout()


        # =================================================
        # LEFT TELEMETRY
        # =================================================

        left = QVBoxLayout()


        self.cpu_stat = MatrixStat(
            "CPU UTILIZATION"
        )

        self.ram_stat = MatrixStat(
            "MEMORY UTILIZATION"
        )

        self.disk_stat = MatrixStat(
            "SYSTEM DRIVE"
        )

        self.process_stat = MatrixStat(
            "PROCESSES"
        )

        self.uptime_stat = MatrixStat(
            "SYSTEM UPTIME"
        )


        left.addWidget(
            self.cpu_stat
        )

        left.addWidget(
            self.ram_stat
        )

        left.addWidget(
            self.disk_stat
        )

        left.addWidget(
            self.process_stat
        )

        left.addWidget(
            self.uptime_stat
        )

        left.addStretch()


        # =================================================
        # CENTER HOLOGRAM
        # =================================================

        self.hologram = (
            HologramComputer()
        )

        self.hologram.setMinimumWidth(
            400
        )


        # =================================================
        # RIGHT TELEMETRY
        # =================================================

        right = QVBoxLayout()


        self.cpu_frequency_stat = MatrixStat(
            "CPU FREQUENCY"
        )

        self.core_stat = MatrixStat(
            "CPU CORES"
        )

        self.network_down_stat = MatrixStat(
            "NETWORK DOWN"
        )

        self.network_up_stat = MatrixStat(
            "NETWORK UP"
        )

        self.os_stat = MatrixStat(
            "OPERATING SYSTEM"
        )

        self.ip_stat = MatrixStat(
            "LOCAL NETWORK"
        )


        right.addWidget(
            self.cpu_frequency_stat
        )

        right.addWidget(
            self.core_stat
        )

        right.addWidget(
            self.network_down_stat
        )

        right.addWidget(
            self.network_up_stat
        )

        right.addWidget(
            self.os_stat
        )

        right.addWidget(
            self.ip_stat
        )

        right.addStretch()


        body.addLayout(
            left,
            1
        )

        body.addWidget(
            self.hologram,
            2
        )

        body.addLayout(
            right,
            1
        )


        root.addLayout(
            body,
            1
        )


        footer = QLabel(
            "☝ SWIPE RIGHT // RETURN TO HOME"
        )

        footer.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        footer.setStyleSheet(
            """
            color: rgba(57,255,120,130);
            font-family: Consolas;
            font-size: 9px;
            """
        )


        root.addWidget(
            footer
        )


    # =====================================================
    # LIVE STATS
    # =====================================================

    def update_stats(self):

        # =================================================
        # DIGITAL TWIN SNAPSHOT
        # =================================================

        try:

            snapshot = (
                self.system_monitoring_service
                .get_snapshot()
            )


            state = (
                snapshot[
                    "digital_twin"
                ]
            )


        except Exception:

            return


        # =================================================
        # CPU
        # =================================================

        cpu = (
            state.cpu_percent
        )


        self.cpu_stat.set_value(
            f"{cpu:.0f}%",
            cpu
        )


        # =================================================
        # MEMORY
        # =================================================

        self.ram_stat.set_value(
            (
                f"{state.memory_percent:.0f}% // "
                f"{state.memory_used_gb:.1f} GB"
            ),
            state.memory_percent
        )


        # =================================================
        # STORAGE
        # =================================================

        self.disk_stat.set_value(
            (
                f"{state.disk_percent:.0f}% // "
                f"{state.disk_available_gb():.0f} GB FREE"
            ),
            state.disk_percent
        )


        # =================================================
        # CPU FREQUENCY
        # =================================================

        if state.cpu_frequency_mhz > 0:

            self.cpu_frequency_stat.set_value(
                f"{state.cpu_frequency_mhz / 1000:.2f} GHz"
            )

        else:

            self.cpu_frequency_stat.set_value(
                "N/A"
            )


        # =================================================
        # CORES
        # =================================================

        self.core_stat.set_value(
            (
                f"{state.physical_cores} PHYSICAL // "
                f"{state.logical_cores} LOGICAL"
            )
        )


        # =================================================
        # PROCESSES
        # =================================================

        self.process_stat.set_value(
            str(
                state.process_count
            )
        )


        # =================================================
        # UPTIME
        # =================================================

        hours = int(
            state.uptime_seconds
            // 3600
        )


        minutes = int(
            (
                state.uptime_seconds
                % 3600
            )
            // 60
        )


        self.uptime_stat.set_value(
            f"{hours}H {minutes}M"
        )


        # =================================================
        # NETWORK RATE FROM DIGITAL TWIN COUNTERS
        # =================================================

        current_time = (
            state.timestamp.timestamp()
        )


        if (
            self.previous_network_timestamp
            is None
        ):

            download_rate = 0.0
            upload_rate = 0.0


        else:

            elapsed = max(
                0.1,
                current_time
                - self.previous_network_timestamp
            )


            received_delta_mb = max(
                0.0,
                state.network_received_mb
                - self.previous_network_received_mb
            )


            sent_delta_mb = max(
                0.0,
                state.network_sent_mb
                - self.previous_network_sent_mb
            )


            download_rate = (
                received_delta_mb
                * (1024 ** 2)
                / elapsed
            )


            upload_rate = (
                sent_delta_mb
                * (1024 ** 2)
                / elapsed
            )


        self.previous_network_received_mb = (
            state.network_received_mb
        )


        self.previous_network_sent_mb = (
            state.network_sent_mb
        )


        self.previous_network_timestamp = (
            current_time
        )


        self.network_down_stat.set_value(
            self.format_speed(
                download_rate
            )
        )


        self.network_up_stat.set_value(
            self.format_speed(
                upload_rate
            )
        )


        # =================================================
        # OPERATING SYSTEM
        # =================================================

        self.os_stat.set_value(
            state.operating_system
        )


        # =================================================
        # LOCAL NETWORK
        # =================================================

        local_ip = (
            state.extra.get(
                "local_ip"
            )
        )


        if local_ip:

            self.ip_stat.set_value(
                local_ip
            )

        else:

            self.ip_stat.set_value(
                state.network_status
            )


        # =================================================
        # HOLOGRAM
        # =================================================

        self.hologram.set_stats(
            state.cpu_percent,
            state.memory_percent,
            state.disk_percent
        )


    # =====================================================
    # NETWORK FORMAT
    # =====================================================

    def format_speed(
        self,
        bytes_per_second
    ):

        if (
            bytes_per_second
            < 1024
        ):

            return (
                f"{bytes_per_second:.0f} B/s"
            )


        if (
            bytes_per_second
            < 1024 ** 2
        ):

            return (
                f"{bytes_per_second / 1024:.1f} KB/s"
            )


        return (
            f"{bytes_per_second / (1024 ** 2):.2f} MB/s"
        )
