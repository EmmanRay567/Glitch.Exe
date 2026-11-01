import math
import random


from PySide6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QRectF,
)

from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QPolygonF,
)

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QProgressBar,
)


# =========================================================
# HACKER BACKGROUND
# =========================================================

from services.security_anomaly_service import SecurityAnomalyService
from services.security_history_service import SecurityHistoryService

class HackerBackground(QWidget):
    """
    Lightweight animated cyber-security background.

    Draws:
    - falling hexadecimal / binary fragments
    - subtle scanlines
    - faint node-link network
    - terminal activity
    - state-reactive accent intensity

    This widget is purely visual. Real security telemetry will
    be connected later through SecurityMonitoringService.
    """

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )

        self.columns = []
        self.network_nodes = []

        self.frame = 0
        self.threat_state = "SECURE"

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.animate
        )

        self.timer.start(
            55
        )


    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        self._rebuild_scene()


    def _rebuild_scene(
        self
    ):

        width = max(
            self.width(),
            1
        )

        height = max(
            self.height(),
            1
        )


        self.columns = []

        spacing = 38

        for x in range(
            12,
            width,
            spacing
        ):

            self.columns.append(
                {
                    "x":
                        x,

                    "y":
                        random.randint(
                            -height,
                            height
                        ),

                    "speed":
                        random.uniform(
                            0.7,
                            2.2
                        ),

                    "length":
                        random.randint(
                            3,
                            9
                        ),
                }
            )


        self.network_nodes = []

        for _ in range(
            14
        ):

            self.network_nodes.append(
                QPointF(
                    random.randint(
                        40,
                        max(
                            41,
                            width - 40
                        )
                    ),
                    random.randint(
                        80,
                        max(
                            81,
                            height - 60
                        )
                    )
                )
            )


    def set_threat_state(
        self,
        state
    ):

        state = (
            str(state)
            .strip()
            .upper()
        )

        if state in {
            "SECURE",
            "CAUTION",
            "WARNING",
            "CRITICAL",
        }:

            self.threat_state = (
                state
            )

            self.update()


    def _accent(
        self,
        alpha=255
    ):

        if self.threat_state == "CRITICAL":

            return QColor(
                255,
                60,
                60,
                alpha
            )

        if self.threat_state in {
            "CAUTION",
            "WARNING",
        }:

            return QColor(
                255,
                195,
                70,
                alpha
            )

        return QColor(
            57,
            255,
            120,
            alpha
        )


    def animate(
        self
    ):

        self.frame += 1

        height = max(
            self.height(),
            1
        )


        for column in self.columns:

            column["y"] += (
                column["speed"]
            )

            if (
                column["y"]
                > height + 100
            ):

                column["y"] = (
                    random.randint(
                        -260,
                        -40
                    )
                )


        self.update()


    def paintEvent(
        self,
        event
    ):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        width = self.width()
        height = self.height()


        # -------------------------------------------------
        # BASE
        # -------------------------------------------------

        painter.fillRect(
            self.rect(),
            QColor(
                0,
                5,
                3,
                255
            )
        )


        # -------------------------------------------------
        # CYBER GRID
        # -------------------------------------------------

        grid_pen = QPen(
            QColor(
                57,
                255,
                120,
                12
            ),
            1
        )

        painter.setPen(
            grid_pen
        )


        for x in range(
            0,
            width,
            48
        ):

            painter.drawLine(
                x,
                0,
                x,
                height
            )


        for y in range(
            0,
            height,
            48
        ):

            painter.drawLine(
                0,
                y,
                width,
                y
            )


        # -------------------------------------------------
        # NETWORK NODE MAP
        # -------------------------------------------------

        accent = (
            self._accent(
                24
            )
        )

        painter.setPen(
            QPen(
                accent,
                1
            )
        )


        for index in range(
            len(
                self.network_nodes
            ) - 1
        ):

            a = (
                self.network_nodes[
                    index
                ]
            )

            b = (
                self.network_nodes[
                    index + 1
                ]
            )

            painter.drawLine(
                a,
                b
            )


        painter.setBrush(
            self._accent(
                38
            )
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )


        for node in self.network_nodes:

            painter.drawEllipse(
                node,
                3.0,
                3.0
            )


        # -------------------------------------------------
        # FALLING CODE
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Consolas",
                8
            )
        )


        glyphs = (
            "01ABCDEF"
        )


        for column in self.columns:

            x = (
                column["x"]
            )

            y = (
                column["y"]
            )

            length = (
                column["length"]
            )


            for offset in range(
                length
            ):

                alpha = max(
                    8,
                    50 - offset * 6
                )

                painter.setPen(
                    self._accent(
                        alpha
                    )
                )

                char = random.choice(
                    glyphs
                )

                painter.drawText(
                    int(
                        x
                    ),
                    int(
                        y - offset * 14
                    ),
                    char
                )


        # -------------------------------------------------
        # TERMINAL GHOST TEXT
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Consolas",
                8
            )
        )

        painter.setPen(
            self._accent(
                32
            )
        )


        terminal_lines = [
            "> defensive grid online",
            "> firewall handshake verified",
            "> monitoring active connections",
            "> scanning local process signatures",
            "> encrypted channel established",
        ]


        terminal_y = (
            height - 120
        )


        for index, line in enumerate(
            terminal_lines
        ):

            reveal = (
                self.frame
                + index * 17
            ) % 180

            if reveal > 28:

                painter.drawText(
                    28,
                    terminal_y
                    + index * 16,
                    line
                )


        # -------------------------------------------------
        # CRT SCANLINES
        # -------------------------------------------------

        painter.setPen(
            QPen(
                QColor(
                    255,
                    255,
                    255,
                    7
                ),
                1
            )
        )


        for y in range(
            0,
            height,
            4
        ):

            painter.drawLine(
                0,
                y,
                width,
                y
            )


        # Moving scanner
        scan_y = (
            self.frame * 3
        ) % max(
            height,
            1
        )

        painter.setPen(
            QPen(
                self._accent(
                    26
                ),
                1
            )
        )

        painter.drawLine(
            0,
            scan_y,
            width,
            scan_y
        )

        painter.end()


# =========================================================
# SECURITY CORE HOLOGRAM
# =========================================================

class SecurityCoreHologram(QWidget):

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.rotation = 0.0
        self.pulse = 0.0
        self.scan_angle = 0.0

        self.security_state = (
            "SECURE"
        )

        self.monitoring_state = (
            "ACTIVE"
        )

        self.setMinimumHeight(
            330
        )


        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.animate
        )

        self.timer.start(
            32
        )


    def set_security_state(
        self,
        state
    ):

        state = (
            str(state)
            .strip()
            .upper()
        )

        if state in {
            "SECURE",
            "CAUTION",
            "WARNING",
            "CRITICAL",
        }:

            self.security_state = (
                state
            )

            self.update()


    def _accent(
        self,
        alpha=255
    ):

        if self.security_state == "CRITICAL":

            return QColor(
                255,
                65,
                65,
                alpha
            )

        if self.security_state in {
            "CAUTION",
            "WARNING",
        }:

            return QColor(
                255,
                200,
                75,
                alpha
            )

        return QColor(
            57,
            255,
            120,
            alpha
        )


    def animate(
        self
    ):

        self.rotation += 0.7

        if self.rotation >= 360:

            self.rotation = 0


        self.scan_angle += 2.2

        if self.scan_angle >= 360:

            self.scan_angle = 0


        self.pulse += 0.055

        self.update()


    def paintEvent(
        self,
        event
    ):

        painter = QPainter(
            self
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )


        width = self.width()
        height = self.height()

        cx = (
            width / 2
        )

        cy = (
            height / 2
            - 12
        )


        pulse_scale = (
            1.0
            + math.sin(
                self.pulse
            ) * 0.035
        )


        # -------------------------------------------------
        # AMBIENT CORE GLOW
        # -------------------------------------------------

        for radius, alpha in [
            (155, 10),
            (125, 18),
            (95, 28),
        ]:

            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(
                self._accent(
                    alpha
                )
            )

            painter.drawEllipse(
                QPointF(
                    cx,
                    cy
                ),
                radius,
                radius
            )


        # -------------------------------------------------
        # ROTATING SECURITY RINGS
        # -------------------------------------------------

        painter.save()

        painter.translate(
            cx,
            cy
        )

        painter.rotate(
            self.rotation
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        painter.setPen(
            QPen(
                self._accent(
                    100
                ),
                2
            )
        )

        painter.drawEllipse(
            QPointF(
                0,
                0
            ),
            125,
            125
        )

        painter.drawArc(
            QRectF(
                -145,
                -145,
                290,
                290
            ),
            18 * 16,
            72 * 16
        )

        painter.drawArc(
            QRectF(
                -145,
                -145,
                290,
                290
            ),
            198 * 16,
            64 * 16
        )

        painter.restore()


        painter.save()

        painter.translate(
            cx,
            cy
        )

        painter.rotate(
            -self.rotation * 0.65
        )

        painter.setPen(
            QPen(
                self._accent(
                    55
                ),
                1
            )
        )

        painter.drawEllipse(
            QPointF(
                0,
                0
            ),
            100,
            100
        )

        painter.restore()


        # -------------------------------------------------
        # SHIELD
        # -------------------------------------------------

        shield_width = (
            105 * pulse_scale
        )

        shield_height = (
            130 * pulse_scale
        )


        shield = QPolygonF(
            [
                QPointF(
                    cx,
                    cy - shield_height / 2
                ),

                QPointF(
                    cx + shield_width / 2,
                    cy - shield_height / 3
                ),

                QPointF(
                    cx + shield_width * 0.42,
                    cy + shield_height * 0.22
                ),

                QPointF(
                    cx,
                    cy + shield_height / 2
                ),

                QPointF(
                    cx - shield_width * 0.42,
                    cy + shield_height * 0.22
                ),

                QPointF(
                    cx - shield_width / 2,
                    cy - shield_height / 3
                ),
            ]
        )


        painter.setBrush(
            self._accent(
                24
            )
        )

        painter.setPen(
            QPen(
                self._accent(
                    220
                ),
                2
            )
        )

        painter.drawPolygon(
            shield
        )


        # Shield internal circuit lines.
        painter.setPen(
            QPen(
                self._accent(
                    70
                ),
                1
            )
        )

        painter.drawLine(
            QPointF(
                cx,
                cy - 47
            ),
            QPointF(
                cx,
                cy + 45
            )
        )

        painter.drawLine(
            QPointF(
                cx - 32,
                cy - 10
            ),
            QPointF(
                cx + 32,
                cy - 10
            )
        )

        painter.drawEllipse(
            QPointF(
                cx,
                cy - 10
            ),
            9,
            9
        )


        # -------------------------------------------------
        # STATUS TEXT
        # -------------------------------------------------

        painter.setFont(
            QFont(
                "Consolas",
                10,
                QFont.Weight.Bold
            )
        )

        painter.setPen(
            self._accent(
                230
            )
        )

        state_text = (
            f"SECURITY // {self.security_state}"
        )

        state_rect = (
            painter.fontMetrics()
            .boundingRect(
                state_text
            )
        )

        painter.drawText(
            int(
                cx
                - state_rect.width() / 2
            ),
            int(
                cy + 102
            ),
            state_text
        )


        painter.setFont(
            QFont(
                "Consolas",
                8
            )
        )

        painter.setPen(
            self._accent(
                125
            )
        )

        monitoring_text = (
            f"MONITORING // {self.monitoring_state}"
        )

        monitor_rect = (
            painter.fontMetrics()
            .boundingRect(
                monitoring_text
            )
        )

        painter.drawText(
            int(
                cx
                - monitor_rect.width() / 2
            ),
            int(
                cy + 124
            ),
            monitoring_text
        )


        # -------------------------------------------------
        # RADAR SWEEP
        # -------------------------------------------------

        painter.save()

        painter.translate(
            cx,
            cy
        )

        painter.rotate(
            self.scan_angle
        )

        painter.setPen(
            QPen(
                self._accent(
                    65
                ),
                1
            )
        )

        painter.drawLine(
            QPointF(
                0,
                0
            ),
            QPointF(
                0,
                -145
            )
        )

        painter.restore()

        painter.end()


# =========================================================
# SECURITY STATUS CARD
# =========================================================

class SecurityStatCard(QFrame):

    def __init__(
        self,
        title,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setMinimumHeight(
            64
        )

        self.setStyleSheet(
            """
            QFrame {
                background: rgba(0, 16, 9, 165);
                border: 1px solid rgba(57,255,120,62);
                border-radius: 8px;
            }
            """
        )


        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            12,
            8,
            12,
            8
        )

        layout.setSpacing(
            3
        )


        self.title_label = QLabel(
            title
        )

        self.title_label.setStyleSheet(
            """
            color: rgba(170,255,195,150);
            font-family: Consolas;
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 1px;
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
            4
        )

        self.bar.hide()


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
        state="SECURE",
        percent=None
    ):

        state = (
            str(state)
            .strip()
            .upper()
        )


        if state == "CRITICAL":

            accent = (
                "#ff4b4b"
            )

        elif state in {
            "WARNING",
            "CAUTION",
        }:

            accent = (
                "#ffc34d"
            )

        else:

            accent = (
                "#39ff78"
            )


        self.value_label.setText(
            str(text)
        )

        self.value_label.setStyleSheet(
            f"""
            color: {accent};
            font-family: Consolas;
            font-size: 14px;
            font-weight: bold;
            """
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

            self.bar.setStyleSheet(
                f"""
                QProgressBar {{
                    background: rgba(255,255,255,12);
                    border: none;
                }}

                QProgressBar::chunk {{
                    background: {accent};
                }}
                """
            )


# =========================================================
# INTELLIGENCE PANEL
# =========================================================

class SecurityIntelPanel(QFrame):

    def __init__(
        self,
        title,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setMinimumHeight(
            100
        )

        self.setMaximumHeight(
            116
        )

        self.setStyleSheet(
            """
            QFrame {
                background: rgba(0, 14, 8, 175);
                border: 1px solid rgba(57,255,120,55);
                border-radius: 8px;
            }
            """
        )


        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            11,
            8,
            11,
            8
        )

        layout.setSpacing(
            4
        )


        self.title_label = QLabel(
            title
        )

        self.title_label.setStyleSheet(
            """
            color: rgba(170,255,195,165);
            font-family: Consolas;
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 1px;
            """
        )


        self.content_label = QLabel(
            "AWAITING SECURITY TELEMETRY..."
        )

        self.content_label.setWordWrap(
            True
        )

        self.content_label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        self.content_label.setStyleSheet(
            """
            color: #8dffb1;
            font-family: Consolas;
            font-size: 10px;
            font-weight: bold;
            """
        )


        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.content_label,
            1
        )


    def set_text(
        self,
        text
    ):

        self.content_label.setText(
            str(text)
        )


# =========================================================
# SECURITY MATRIX PAGE
# =========================================================

class SecurityMatrixWidget(QWidget):
    """
    Phase 3 Security Matrix visual shell.

    V1 intentionally uses placeholder security values.
    Live Windows security data will be connected next through
    SecurityState + SecurityMonitoringService.
    """

    def __init__(
        self,
        security_engine=None,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.security_engine = (
            security_engine
        )

        self.anomaly_service = (
            SecurityAnomalyService()
        )

        self.history_service = (
            SecurityHistoryService()
        )

        self._last_persisted_scan_signature = None

        self.windows_security_telemetry = None

        self.security_state = (
            "SECURE"
        )


        # -------------------------------------------------
        # BACKGROUND STACK
        # -------------------------------------------------

        self.background = (
            HackerBackground(
                self
            )
        )

        self.background.lower()


        self.build_ui()


        # Demo pulse lets the interface feel alive before
        # real telemetry arrives.
        self.activity_phase = 0

        self.demo_timer = QTimer(
            self
        )

        self.demo_timer.timeout.connect(
            self.animate_placeholder_activity
        )

        self.demo_timer.start(
            1600
        )


        self.security_refresh_timer = QTimer(
            self
        )

        self.security_refresh_timer.timeout.connect(
            self.refresh_security_state
        )

        self.security_refresh_timer.start(
            1000
        )


        self.refresh_security_state()


    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        self.background.setGeometry(
            self.rect()
        )


    def build_ui(
        self
    ):

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            24,
            16,
            24,
            18
        )

        root.setSpacing(
            9
        )


        # =================================================
        # HEADER
        # =================================================

        title = QLabel(
            "SECURITY MATRIX"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet(
            """
            color: #39ff78;
            font-family: Consolas;
            font-size: 23px;
            font-weight: bold;
            letter-spacing: 5px;
            background: transparent;
            """
        )


        subtitle = QLabel(
            "CYBER DEFENSE // LIVE SECURITY INTELLIGENCE"
        )

        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        subtitle.setStyleSheet(
            """
            color: rgba(57,255,120,125);
            font-family: Consolas;
            font-size: 9px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
            """
        )


        self.security_state_label = QLabel(
            "SECURITY STATE // SECURE // MONITORING ACTIVE"
        )

        self.security_state_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.security_state_label.setStyleSheet(
            """
            color: rgba(57,255,120,225);
            font-family: Consolas;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            background: rgba(0,10,5,110);
            border: 1px solid rgba(57,255,120,35);
            border-radius: 6px;
            padding: 4px;
            """
        )


        root.addWidget(
            title
        )

        root.addWidget(
            subtitle
        )

        root.addWidget(
            self.security_state_label
        )


        # =================================================
        # BODY
        # =================================================

        body = QHBoxLayout()

        body.setSpacing(
            13
        )


        # -------------------------------------------------
        # HOST PROTECTION
        # -------------------------------------------------

        left = QVBoxLayout()

        left.setSpacing(
            7
        )


        self.firewall_card = (
            SecurityStatCard(
                "FIREWALL"
            )
        )

        self.antivirus_card = (
            SecurityStatCard(
                "ANTIVIRUS / DEFENDER"
            )
        )

        self.threat_card = (
            SecurityStatCard(
                "THREAT LEVEL"
            )
        )

        self.update_card = (
            SecurityStatCard(
                "WINDOWS UPDATE"
            )
        )

        self.event_card = (
            SecurityStatCard(
                "ACTIVE SECURITY EVENTS"
            )
        )


        left.addWidget(
            self.firewall_card
        )

        left.addWidget(
            self.antivirus_card
        )

        left.addWidget(
            self.threat_card
        )

        left.addWidget(
            self.update_card
        )

        left.addWidget(
            self.event_card
        )

        left.addStretch()


        # -------------------------------------------------
        # SECURITY CORE
        # -------------------------------------------------

        center_frame = QFrame()

        center_frame.setMinimumWidth(
            330
        )

        center_frame.setStyleSheet(
            """
            QFrame {
                background: rgba(0, 14, 8, 95);
                border: 1px solid rgba(57,255,120,45);
                border-radius: 12px;
            }
            """
        )


        center_layout = QVBoxLayout(
            center_frame
        )

        center_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )


        core_title = QLabel(
            "GLITCH SECURITY CORE"
        )

        core_title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        core_title.setStyleSheet(
            """
            color: rgba(57,255,120,205);
            font-family: Consolas;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
            """
        )


        self.security_core = (
            SecurityCoreHologram()
        )


        self.core_status = QLabel(
            "DEFENSIVE GRID // ONLINE"
        )

        self.core_status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.core_status.setStyleSheet(
            """
            color: rgba(180,255,205,150);
            font-family: Consolas;
            font-size: 8px;
            font-weight: bold;
            letter-spacing: 1px;
            background: transparent;
            """
        )


        center_layout.addWidget(
            core_title
        )

        center_layout.addWidget(
            self.security_core,
            1
        )

        center_layout.addWidget(
            self.core_status
        )


        # -------------------------------------------------
        # NETWORK DEFENSE
        # -------------------------------------------------

        right = QVBoxLayout()

        right.setSpacing(
            7
        )


        self.network_profile_card = (
            SecurityStatCard(
                "NETWORK PROFILE"
            )
        )

        self.connections_card = (
            SecurityStatCard(
                "ACTIVE CONNECTIONS"
            )
        )

        self.ports_card = (
            SecurityStatCard(
                "LISTENING PORTS"
            )
        )

        self.external_card = (
            SecurityStatCard(
                "EXTERNAL CONNECTIONS"
            )
        )

        self.network_state_card = (
            SecurityStatCard(
                "NETWORK SECURITY"
            )
        )


        right.addWidget(
            self.network_profile_card
        )

        right.addWidget(
            self.connections_card
        )

        right.addWidget(
            self.ports_card
        )

        right.addWidget(
            self.external_card
        )

        right.addWidget(
            self.network_state_card
        )

        right.addStretch()


        body.addLayout(
            left,
            1
        )

        body.addWidget(
            center_frame,
            1
        )

        body.addLayout(
            right,
            1
        )


        root.addLayout(
            body,
            1
        )


        # =================================================
        # SECURITY INTELLIGENCE STRIP
        # =================================================

        intelligence = QHBoxLayout()

        intelligence.setSpacing(
            10
        )


        self.events_panel = (
            SecurityIntelPanel(
                "SECURITY EVENTS"
            )
        )

        self.process_panel = (
            SecurityIntelPanel(
                "PROCESS WATCH"
            )
        )

        self.network_panel = (
            SecurityIntelPanel(
                "NETWORK WATCH"
            )
        )


        intelligence.addWidget(
            self.events_panel
        )

        intelligence.addWidget(
            self.process_panel
        )

        intelligence.addWidget(
            self.network_panel
        )


        root.addLayout(
            intelligence
        )


        self.load_placeholder_state()


    # =====================================================
    # WINDOWS SECURITY TELEMETRY
    # =====================================================

    def set_windows_security_telemetry(
        self,
        telemetry
    ):

        self.windows_security_telemetry = (
            telemetry
        )

        self._persist_security_telemetry(
            telemetry
        )

        self.refresh_security_state()


    def _persist_security_telemetry(
        self,
        telemetry
    ):

        if telemetry is None:
            return

        try:
            processes = (
                getattr(
                    telemetry,
                    "process_connections",
                    []
                )
                or []
            )

            anomaly = (
                self.anomaly_service
                .analyze_processes(
                    processes
                )
            )

            self.history_service.record_process_snapshot(
                anomaly.get(
                    "processes",
                    []
                )
            )

            self.history_service.record_anomaly_findings(
                anomaly.get(
                    "findings",
                    []
                )
            )

        except Exception as error:
            print(
                "SECURITY HISTORY TELEMETRY ERROR:",
                error
            )


    def _persist_scan_history(
        self,
        state
    ):

        try:
            results = (
                state.recent_results
                or []
            )

            if not results:
                return

            signature = tuple(
                (
                    str(
                        getattr(
                            result,
                            "path",
                            ""
                        )
                    ),
                    str(
                        getattr(
                            result,
                            "risk_level",
                            ""
                        )
                    ),
                    int(
                        getattr(
                            result,
                            "risk_score",
                            0
                        )
                        or 0
                    ),
                )
                for result in results
            )

            if signature == self._last_persisted_scan_signature:
                return

            self.history_service.record_scan_results(
                state.last_scan_target,
                results
            )

            self._last_persisted_scan_signature = signature

        except Exception as error:
            print(
                "SECURITY SCAN HISTORY ERROR:",
                error
            )


    def get_active_security_findings(
        self
    ):

        try:
            return self.history_service.get_active_findings(
                limit=20
            )

        except Exception:
            return []


    def get_security_finding(
        self,
        index
    ):
        findings = self.get_active_security_findings()

        try:
            index = int(index)
        except (TypeError, ValueError):
            return None

        if index < 1 or index > len(findings):
            return None

        return findings[index - 1]


    def resolve_security_finding(
        self,
        finding_key,
        note="Resolved by 404."
    ):
        changed = self.history_service.resolve_finding(
            finding_key,
            note=note
        )

        self.refresh_security_state()

        return bool(changed)


    def recent_security_events(
        self,
        limit=25
    ):
        try:
            return self.history_service.recent_events(
                limit=limit
            )
        except Exception:
            return []


    def record_security_control_event(
        self,
        action,
        finding,
        success,
        details=""
    ):
        try:
            self.history_service.record_control_event(
                action,
                finding,
                success,
                details
            )
        except Exception as error:
            print(
                "SECURITY CONTROL HISTORY ERROR:",
                error
            )


    # =====================================================
    # LIVE SECURITY ENGINE STATE
    # =====================================================

    def refresh_security_state(
        self
    ):

        if self.security_engine is None:

            return


        state = (
            self.security_engine
            .state
        )

        self._persist_scan_history(
            state
        )


        self.set_security_state(
            state.security_status
        )


        self.antivirus_card.set_value(
            (
                "ACTIVE"
                if state.antivirus_engine_active
                else "OFFLINE"
            ),
            (
                "SECURE"
                if state.antivirus_engine_active
                else "WARNING"
            )
        )


        self.threat_card.set_value(
            state.security_status,
            state.security_status,
            (
                min(
                    100,
                    max(
                        0,
                        state.suspicious_files
                        * 20
                    )
                )
            )
        )


        self.update_card.set_value(
            (
                f"{state.files_scanned} FILES"
            ),
            "SECURE"
        )


        persistent_findings = (
            self.get_active_security_findings()
        )

        active_finding_count = len(
            persistent_findings
        )

        combined_flagged = max(
            int(
                state.suspicious_files
                or 0
            ),
            active_finding_count
        )


        self.event_card.set_value(
            (
                f"{combined_flagged} FLAGGED"
            ),
            (
                "WARNING"
                if combined_flagged
                else "SECURE"
            )
        )


        telemetry = (
            self.windows_security_telemetry
        )


        if telemetry is None:

            self.firewall_card.set_value(
                "TELEMETRY PENDING",
                "SECURE"
            )

            self.network_profile_card.set_value(
                "TELEMETRY PENDING",
                "SECURE"
            )

            self.connections_card.set_value(
                "--",
                "SECURE"
            )

            self.ports_card.set_value(
                "--",
                "SECURE"
            )

            self.external_card.set_value(
                "--",
                "SECURE"
            )

            self.network_state_card.set_value(
                "PENDING",
                "SECURE"
            )

        else:

            firewall_state = (
                "ON"
                if telemetry.firewall_enabled is True
                else (
                    "OFF"
                    if telemetry.firewall_enabled is False
                    else "UNKNOWN"
                )
            )

            firewall_severity = (
                "SECURE"
                if telemetry.firewall_enabled is True
                else "WARNING"
            )

            self.firewall_card.set_value(
                firewall_state,
                firewall_severity
            )


            defender_active = (
                telemetry.defender_active is True
                and telemetry.realtime_protection is True
            )

            defender_text = (
                "GLITCH + DEFENDER"
                if defender_active
                else (
                    "GLITCH ACTIVE"
                    if telemetry.defender_available
                    else "GLITCH ACTIVE"
                )
            )

            self.antivirus_card.set_value(
                defender_text,
                (
                    "SECURE"
                    if defender_active
                    else "CAUTION"
                )
            )


            network_category = (
                telemetry.network_category
                or "UNKNOWN"
            )

            self.network_profile_card.set_value(
                str(
                    network_category
                ).upper(),
                (
                    "SECURE"
                    if str(
                        network_category
                    ).lower()
                    in {
                        "private",
                        "domainauthenticated",
                    }
                    else "CAUTION"
                )
            )


            self.connections_card.set_value(
                str(
                    telemetry.active_connections
                ),
                "SECURE"
            )

            self.ports_card.set_value(
                str(
                    telemetry.listening_ports
                ),
                (
                    "CAUTION"
                    if telemetry.listening_ports > 25
                    else "SECURE"
                )
            )

            self.external_card.set_value(
                str(
                    telemetry.external_connections
                ),
                "SECURE"
            )


            windows_network_secure = (
                telemetry.firewall_enabled is True
                and str(
                    network_category
                ).lower()
                in {
                    "private",
                    "domainauthenticated",
                }
            )

            self.network_state_card.set_value(
                (
                    "SECURE"
                    if windows_network_secure
                    else "REVIEW"
                ),
                (
                    "SECURE"
                    if windows_network_secure
                    else "CAUTION"
                )
            )


        recent_results = (
            state.recent_results
        )


        if persistent_findings:

            lines = []

            for finding in persistent_findings[:3]:

                severity = str(
                    finding.get(
                        "severity",
                        "REVIEW"
                    )
                ).upper()

                process_name = str(
                    finding.get(
                        "process_name",
                        "UNKNOWN"
                    )
                )

                risk_score = int(
                    finding.get(
                        "risk_score",
                        0
                    )
                    or 0
                )

                lines.append(
                    (
                        f"{severity:<10} "
                        f"{process_name[:15]} "
                        f"{risk_score}"
                    )
                )

            self.events_panel.set_text(
                "\n".join(
                    lines
                )
            )

        elif not recent_results:

            self.events_panel.set_text(
                "ANTIVIRUS ENGINE // ACTIVE\n"
                "PERSISTENT FINDINGS // 0\n"
                "MONITORING // ACTIVE"
            )

        else:

            lines = []

            for result in recent_results[-4:]:

                lines.append(
                    (
                        f"{result.risk_level:<8} "
                        f"{result.file_name}"
                    )
                )

            self.events_panel.set_text(
                "\n".join(
                    lines
                )
            )


        quarantine_items = (
            self.security_engine
            .list_quarantine()
        )


        # =================================================
        # LIVE PROCESS -> NETWORK OWNERSHIP
        # =================================================

        if (
            telemetry is not None
            and getattr(
                telemetry,
                "process_connections",
                None
            )
        ):

            anomaly = (
                self.anomaly_service
                .analyze_processes(
                    telemetry.process_connections
                )
            )

            analyzed_processes = (
                anomaly.get(
                    "processes",
                    []
                )
            )

            process_lines = []

            for item in (
                analyzed_processes[:4]
            ):

                name = str(
                    item.get(
                        "name",
                        "UNKNOWN"
                    )
                )

                connections = int(
                    item.get(
                        "connections",
                        0
                    )
                    or 0
                )

                external = int(
                    item.get(
                        "external",
                        0
                    )
                    or 0
                )

                listening = int(
                    item.get(
                        "listening",
                        0
                    )
                    or 0
                )

                risk_level = str(
                    item.get(
                        "risk_level",
                        "NORMAL"
                    )
                ).upper()

                risk_score = int(
                    item.get(
                        "risk_score",
                        0
                    )
                    or 0
                )

                detail = (
                    f"{connections}C/"
                    f"{external}E "
                    f"{risk_level}"
                )

                if risk_level != "NORMAL":

                    detail += (
                        f" {risk_score}"
                    )


                process_lines.append(
                    f"{name[:15]:<15} {detail}"
                )


            self.process_panel.set_text(
                "\n".join(
                    process_lines
                )
            )

        else:

            self.process_panel.set_text(
                "PROCESS MAP // WAITING\n"
                "TCP OWNER LOOKUP // READY\n"
                "NO PROCESS DATA YET"
            )


        # =================================================
        # NETWORK WATCH DETAILS
        # =================================================

        target = (
            state.last_scan_target
            or "NONE"
        )


        if telemetry is not None:

            interface = (
                getattr(
                    telemetry,
                    "network_interface",
                    None
                )
                or "UNKNOWN"
            )

            category = (
                telemetry.network_category
                or "UNKNOWN"
            )

            quarantine_count = len(
                quarantine_items
            )


            self.network_panel.set_text(
                (
                    f"ADAPTER // {interface}\n"
                    f"PROFILE // {str(category).upper()}\n"
                    f"QUARANTINE // {quarantine_count} ITEMS"
                )
            )

        else:

            self.network_panel.set_text(
                (
                    f"LAST SCAN // {target}\n"
                    f"FILES SCANNED // {state.files_scanned}\n"
                    f"SUSPICIOUS // {state.suspicious_files}"
                )
            )

    # =====================================================
    # PLACEHOLDER STATE
    # =====================================================

    def load_placeholder_state(
        self
    ):

        self.firewall_card.set_value(
            "ONLINE",
            "SECURE"
        )

        self.antivirus_card.set_value(
            "ACTIVE",
            "SECURE"
        )

        self.threat_card.set_value(
            "LOW",
            "SECURE",
            10
        )

        self.update_card.set_value(
            "CHECK PENDING",
            "SECURE"
        )

        self.event_card.set_value(
            "0 ACTIVE",
            "SECURE"
        )


        self.network_profile_card.set_value(
            "PRIVATE",
            "SECURE"
        )

        self.connections_card.set_value(
            "--",
            "SECURE"
        )

        self.ports_card.set_value(
            "--",
            "SECURE"
        )

        self.external_card.set_value(
            "--",
            "SECURE"
        )

        self.network_state_card.set_value(
            "MONITORING",
            "SECURE"
        )


        self.events_panel.set_text(
            "NO ACTIVE THREATS\n"
            "DEFENSIVE GRID ONLINE\n"
            "AWAITING LIVE EVENT FEED"
        )

        self.process_panel.set_text(
            "PROCESS ANALYSIS // PENDING\n"
            "SIGNATURE WATCH // READY\n"
            "ANOMALY ENGINE // STANDBY"
        )

        self.network_panel.set_text(
            "CONNECTION MAP // PENDING\n"
            "PORT WATCH // READY\n"
            "REMOTE ANALYSIS // STANDBY"
        )


    # =====================================================
    # STATE REACTION
    # =====================================================

    def set_security_state(
        self,
        state
    ):

        state = (
            str(state)
            .strip()
            .upper()
        )


        if state not in {
            "SECURE",
            "CAUTION",
            "WARNING",
            "CRITICAL",
        }:

            return


        self.security_state = (
            state
        )

        self.background.set_threat_state(
            state
        )

        self.security_core.set_security_state(
            state
        )


        if state == "CRITICAL":

            color = (
                "#ff4b4b"
            )

        elif state in {
            "CAUTION",
            "WARNING",
        }:

            color = (
                "#ffc34d"
            )

        else:

            color = (
                "#39ff78"
            )


        self.security_state_label.setText(
            (
                f"SECURITY STATE // {state} // "
                "MONITORING ACTIVE"
            )
        )

        self.security_state_label.setStyleSheet(
            f"""
            color: {color};
            font-family: Consolas;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            background: rgba(0,10,5,125);
            border: 1px solid {color};
            border-radius: 6px;
            padding: 4px;
            """
        )


    # =====================================================
    # VISUAL ACTIVITY ONLY
    # =====================================================

    def animate_placeholder_activity(
        self
    ):

        self.activity_phase = (
            self.activity_phase
            + 1
        ) % 4


        dots = (
            "."
            * self.activity_phase
        )


        self.core_status.setText(
            (
                "DEFENSIVE GRID // ONLINE"
                + dots
            )
        )
