import math
import random

from PySide6.QtWidgets import QWidget

from PySide6.QtCore import (
    Qt,
    QTimer,
    QEvent,
    QPointF,
)

from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QRadialGradient,
    QLinearGradient,
    QFont,
)


class ReactorWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        # ==================================================
        # INPUT SUPPORT
        # ==================================================

        self.setAttribute(
            Qt.WidgetAttribute.WA_AcceptTouchEvents,
            True
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False
        )

        self.setMouseTracking(
            True
        )

        # ==================================================
        # ANIMATION STATE
        # ==================================================

        self.angle = 0.0
        self.secondary_angle = 0.0
        self.pulse = 0.0

        self.glitch_frames = 0
        self.glitch_strength = 0.0

        # ==================================================
        # TOUCH / CLICK RIPPLE
        # ==================================================

        self.ripples = []

        # ==================================================
        # PARTICLES
        # ==================================================

        self.particles = []

        for _ in range(28):

            self.particles.append(
                {
                    "angle": random.uniform(
                        0,
                        math.tau
                    ),

                    "distance": random.uniform(
                        0.28,
                        0.47
                    ),

                    "size": random.uniform(
                        1.0,
                        2.5
                    ),

                    "speed": random.uniform(
                        0.001,
                        0.004
                    ),
                }
            )

        # ==================================================
        # TIMER
        # ==================================================

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.update_animation
        )

        self.timer.start(
            16
        )


    # ======================================================
    # ANIMATION
    # ======================================================

    def update_animation(self):

        self.angle += 0.35
        self.secondary_angle -= 0.18
        self.pulse += 0.055

        # --------------------------------------------------
        # PARTICLES
        # --------------------------------------------------

        for particle in self.particles:

            particle["angle"] += (
                particle["speed"]
            )

        # --------------------------------------------------
        # RIPPLE UPDATE
        # --------------------------------------------------

        active_ripples = []

        for ripple in self.ripples:

            ripple["radius"] += (
                ripple["speed"]
            )

            ripple["alpha"] -= (
                ripple["fade"]
            )

            if ripple["alpha"] > 0:

                active_ripples.append(
                    ripple
                )

        self.ripples = active_ripples

        # --------------------------------------------------
        # GLITCH TIMER
        # --------------------------------------------------

        if self.glitch_frames > 0:

            self.glitch_frames -= 1

        else:

            self.glitch_strength = 0.0

            if random.random() < 0.025:

                self.trigger_glitch(
                    0.28,
                    8
                )

        self.update()


    # ======================================================
    # GLITCH
    # ======================================================

    def trigger_glitch(
        self,
        strength=1.0,
        frames=16
    ):

        self.glitch_strength = (
            strength
        )

        self.glitch_frames = (
            frames
        )

        self.update()


    # ======================================================
    # CREATE RIPPLE
    # ======================================================

    def create_ripple(
        self,
        position
    ):

        print(
            f"REACTOR TOUCHED: "
            f"{position.x():.0f}, "
            f"{position.y():.0f}"
        )

        self.ripples.append(
            {
                "x": position.x(),
                "y": position.y(),

                "radius": 15.0,

                "alpha": 255,

                "speed": 3.0,

                "fade": 3,
            }
        )

        self.trigger_glitch(
            1.20,
            18
        )

        self.update()


    # ======================================================
    # TOUCH EVENTS
    # ======================================================

    def event(
        self,
        event
    ):

        if (
            event.type()
            == QEvent.Type.TouchBegin
        ):

            points = (
                event.points()
            )

            if points:

                point = points[0]

                print(
                    "GLITCH REACTOR TOUCH DETECTED"
                )

                self.create_ripple(
                    point.position()
                )

            event.accept()

            return True


        if (
            event.type()
            == QEvent.Type.TouchUpdate
        ):

            event.accept()

            return True


        if (
            event.type()
            == QEvent.Type.TouchEnd
        ):

            event.accept()

            return True


        return super().event(
            event
        )


    # ======================================================
    # MOUSE CLICK
    # ======================================================

    def mousePressEvent(
        self,
        event
    ):

        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):

            print(
                "GLITCH REACTOR CLICK DETECTED"
            )

            self.create_ripple(
                event.position()
            )

            event.accept()

            return

        super().mousePressEvent(
            event
        )


    # ======================================================
    # PAINT
    # ======================================================

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

        center_x = width / 2
        center_y = height / 2

        # ==================================================
        # GLITCH JITTER
        # ==================================================

        jitter_x = 0
        jitter_y = 0

        if self.glitch_frames > 0:

            jitter_x = random.uniform(
                -16,
                16
            ) * self.glitch_strength

            jitter_y = random.uniform(
                -8,
                8
            ) * self.glitch_strength

        center_x += jitter_x
        center_y += jitter_y

        center = QPointF(
            center_x,
            center_y
        )

        # ==================================================
        # BACKGROUND
        # ==================================================

        background = QRadialGradient(
            center,
            max(
                width,
                height
            )
        )

        background.setColorAt(
            0.0,
            QColor(
                0,
                28,
                14
            )
        )

        background.setColorAt(
            0.45,
            QColor(
                0,
                15,
                8
            )
        )

        background.setColorAt(
            1.0,
            QColor(
                0,
                5,
                3
            )
        )

        painter.fillRect(
            self.rect(),
            background
        )

        # ==================================================
        # GRID
        # ==================================================

        grid_pen = QPen(
            QColor(
                20,
                120,
                65,
                40
            )
        )

        grid_pen.setWidth(
            1
        )

        painter.setPen(
            grid_pen
        )

        spacing = 45

        for x in range(
            0,
            width,
            spacing
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
            spacing
        ):

            painter.drawLine(
                0,
                y,
                width,
                y
            )

        # ==================================================
        # SCAN LINE
        # ==================================================

        scan_y = int(
            (
                math.sin(
                    self.pulse * 0.28
                )
                * 0.5
                + 0.5
            )
            * height
        )

        scan_gradient = QLinearGradient(
            0,
            scan_y - 20,
            0,
            scan_y + 20
        )

        scan_gradient.setColorAt(
            0,
            QColor(
                30,
                255,
                110,
                0
            )
        )

        scan_gradient.setColorAt(
            0.5,
            QColor(
                30,
                255,
                110,
                18
            )
        )

        scan_gradient.setColorAt(
            1,
            QColor(
                30,
                255,
                110,
                0
            )
        )

        painter.fillRect(
            0,
            scan_y - 20,
            width,
            40,
            QBrush(
                scan_gradient
            )
        )

        # ==================================================
        # REACTOR SIZE
        # ==================================================

        base_radius = min(
            width,
            height
        ) * 0.25

        # ==================================================
        # OUTER RINGS
        # ==================================================

        ring_pen = QPen(
            QColor(
                30,
                255,
                105,
                105
            )
        )

        ring_pen.setWidthF(
            1.4
        )

        painter.setPen(
            ring_pen
        )

        for multiplier in [
            1.0,
            1.17,
            1.36,
            1.55,
        ]:

            radius = (
                base_radius
                * multiplier
            )

            painter.drawEllipse(
                center,
                radius,
                radius
            )

        # ==================================================
        # ROTATING SEGMENTED ARC
        # ==================================================

        arc_pen = QPen(
            QColor(
                40,
                255,
                115,
                210
            )
        )

        arc_pen.setWidthF(
            3.5
        )

        painter.setPen(
            arc_pen
        )

        radius = (
            base_radius * 1.65
        )

        rect = (
            center_x - radius,
            center_y - radius,
            radius * 2,
            radius * 2
        )

        arc_sections = [
            (0, 32),
            (62, 22),
            (112, 38),
            (184, 28),
            (238, 42),
            (315, 25),
        ]

        for offset, length in arc_sections:

            start_angle = (
                self.angle
                + offset
            )

            painter.drawArc(
                *rect,
                int(
                    start_angle
                    * 16
                ),
                int(
                    length
                    * 16
                )
            )

        # ==================================================
        # SECOND ROTATING ARC
        # ==================================================

        secondary_pen = QPen(
            QColor(
                25,
                210,
                90,
                145
            )
        )

        secondary_pen.setWidthF(
            2
        )

        painter.setPen(
            secondary_pen
        )

        radius2 = (
            base_radius * 1.95
        )

        rect2 = (
            center_x - radius2,
            center_y - radius2,
            radius2 * 2,
            radius2 * 2
        )

        for offset in [
            20,
            108,
            204,
            292,
        ]:

            start_angle = (
                self.secondary_angle
                + offset
            )

            painter.drawArc(
                *rect2,
                int(
                    start_angle
                    * 16
                ),
                int(
                    38
                    * 16
                )
            )

        # ==================================================
        # CALIBRATION TICKS
        # ==================================================

        tick_pen = QPen(
            QColor(
                45,
                255,
                120,
                170
            )
        )

        tick_pen.setWidthF(
            1.5
        )

        painter.setPen(
            tick_pen
        )

        tick_inner = (
            base_radius * 1.72
        )

        tick_outer = (
            base_radius * 1.82
        )

        for degrees in range(
            0,
            360,
            10
        ):

            angle = math.radians(
                degrees
                + self.secondary_angle
            )

            x1 = (
                center_x
                + math.cos(angle)
                * tick_inner
            )

            y1 = (
                center_y
                + math.sin(angle)
                * tick_inner
            )

            length_modifier = (
                1.12
                if degrees % 30 == 0
                else 1.0
            )

            x2 = (
                center_x
                + math.cos(angle)
                * tick_outer
                * length_modifier
            )

            y2 = (
                center_y
                + math.sin(angle)
                * tick_outer
                * length_modifier
            )

            painter.drawLine(
                QPointF(
                    x1,
                    y1
                ),
                QPointF(
                    x2,
                    y2
                )
            )

        # ==================================================
        # PARTICLES
        # ==================================================

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QColor(
                110,
                255,
                160,
                180
            )
        )

        for particle in self.particles:

            distance = (
                min(
                    width,
                    height
                )
                * particle[
                    "distance"
                ]
            )

            px = (
                center_x
                + math.cos(
                    particle["angle"]
                )
                * distance
            )

            py = (
                center_y
                + math.sin(
                    particle["angle"]
                )
                * distance
            )

            painter.drawEllipse(
                QPointF(
                    px,
                    py
                ),

                particle["size"],
                particle["size"]
            )

        # ==================================================
        # CORE GLOW
        # ==================================================

        pulse_amount = (
            1.0
            + math.sin(
                self.pulse
            )
            * 0.055
        )

        core_radius = (
            base_radius
            * 0.39
            * pulse_amount
        )

        glow = QRadialGradient(
            center,
            core_radius * 2.2
        )

        glow.setColorAt(
            0.0,
            QColor(
                235,
                255,
                240,
                255
            )
        )

        glow.setColorAt(
            0.12,
            QColor(
                100,
                255,
                155,
                250
            )
        )

        glow.setColorAt(
            0.35,
            QColor(
                30,
                255,
                105,
                190
            )
        )

        glow.setColorAt(
            0.70,
            QColor(
                20,
                190,
                80,
                60
            )
        )

        glow.setColorAt(
            1.0,
            QColor(
                0,
                80,
                30,
                0
            )
        )

        painter.setBrush(
            QBrush(
                glow
            )
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.drawEllipse(
            center,
            core_radius * 2.2,
            core_radius * 2.2
        )

        # ==================================================
        # CENTER LIGHT
        # ==================================================

        painter.setBrush(
            QColor(
                230,
                255,
                237
            )
        )

        painter.drawEllipse(
            center,
            7,
            7
        )

        # ==================================================
        # TOUCH ENERGY RIPPLES
        # ==================================================

        for ripple in self.ripples:

            alpha = int(
                max(
                    0,
                    ripple["alpha"]
                )
            )

            # Main bright ring
            ripple_pen = QPen(
                QColor(
                    57,
                    255,
                    120,
                    alpha
                )
            )

            ripple_pen.setWidthF(
                3.0
            )

            painter.setPen(
                ripple_pen
            )

            painter.setBrush(
                Qt.BrushStyle.NoBrush
            )

            painter.drawEllipse(
                QPointF(
                    ripple["x"],
                    ripple["y"]
                ),

                ripple["radius"],
                ripple["radius"]
            )

            # Middle glow ring
            middle_alpha = int(
                alpha * 0.60
            )

            middle_pen = QPen(
                QColor(
                    80,
                    255,
                    150,
                    middle_alpha
                )
            )

            middle_pen.setWidthF(
                2.0
            )

            painter.setPen(
                middle_pen
            )

            painter.drawEllipse(
                QPointF(
                    ripple["x"],
                    ripple["y"]
                ),

                ripple["radius"] * 1.45,
                ripple["radius"] * 1.45
            )

            # Outer faint ring
            outer_alpha = int(
                alpha * 0.30
            )

            outer_pen = QPen(
                QColor(
                    57,
                    255,
                    120,
                    outer_alpha
                )
            )

            outer_pen.setWidthF(
                1.0
            )

            painter.setPen(
                outer_pen
            )

            painter.drawEllipse(
                QPointF(
                    ripple["x"],
                    ripple["y"]
                ),

                ripple["radius"] * 2.0,
                ripple["radius"] * 2.0
            )

        # ==================================================
        # HUD LABELS
        # ==================================================

        painter.setPen(
            QColor(
                70,
                255,
                135,
                145
            )
        )

        label_font = QFont(
            "Consolas",
            7
        )

        painter.setFont(
            label_font
        )

        painter.drawText(
            int(
                center_x
                - base_radius * 1.55
            ),
            int(
                center_y
                - base_radius * 1.25
            ),
            "CORE.SYS"
        )

        painter.drawText(
            int(
                center_x
                + base_radius * 1.10
            ),
            int(
                center_y
                - base_radius * 0.90
            ),
            "SYNC 100%"
        )

        painter.drawText(
            int(
                center_x
                - base_radius * 1.75
            ),
            int(
                center_y
                + base_radius * 1.05
            ),
            "ENERGY STABLE"
        )

        painter.drawText(
            int(
                center_x
                + base_radius * 1.25
            ),
            int(
                center_y
                + base_radius * 1.15
            ),
            "AI NODE 01"
        )

        # ==================================================
        # GLITCH ARTIFACTS
        # ==================================================

        if self.glitch_frames > 0:

            strength = (
                self.glitch_strength
            )

            for _ in range(12):

                y = random.randint(
                    0,
                    max(
                        1,
                        height - 1
                    )
                )

                x = random.randint(
                    0,
                    max(
                        1,
                        width - 120
                    )
                )

                tear_width = random.randint(
                    40,
                    max(
                        50,
                        int(
                            width * 0.35
                        )
                    )
                )

                painter.fillRect(
                    x,
                    y,
                    tear_width,
                    random.randint(
                        2,
                        5
                    ),

                    QColor(
                        40,
                        255,
                        110,
                        random.randint(
                            20,
                            75
                        )
                    )
                )

            for _ in range(48):

                x = random.randint(
                    0,
                    max(
                        1,
                        width - 20
                    )
                )

                y = random.randint(
                    0,
                    max(
                        1,
                        height - 10
                    )
                )

                painter.fillRect(
                    x,
                    y,

                    random.randint(
                        4,
                        24
                    ),

                    random.randint(
                        2,
                        8
                    ),

                    QColor(
                        35,
                        255,
                        105,
                        random.randint(
                            15,
                            80
                        )
                    )
                )

            for _ in range(22):

                x = random.randint(
                    0,
                    max(
                        1,
                        width - 2
                    )
                )

                y = random.randint(
                    0,
                    max(
                        1,
                        height - 80
                    )
                )

                painter.fillRect(
                    x,
                    y,

                    random.randint(
                        1,
                        3
                    ),

                    random.randint(
                        12,
                        70
                    ),

                    QColor(
                        70,
                        255,
                        140,
                        random.randint(
                            20,
                            65
                        )
                    )
                )

            for _ in range(8):

                band_y = random.randint(
                    int(
                        center_y
                        - base_radius
                    ),

                    int(
                        center_y
                        + base_radius
                    )
                )

                band_width = random.randint(
                    int(
                        base_radius * 0.5
                    ),

                    int(
                        base_radius * 2.0
                    )
                )

                painter.fillRect(
                    int(
                        center_x
                        - band_width / 2
                        + random.randint(
                            -40,
                            40
                        )
                    ),

                    band_y,

                    band_width,

                    random.randint(
                        2,
                        7
                    ),

                    QColor(
                        30,
                        255,
                        100,
                        random.randint(
                            20,
                            70
                        )
                    )
                )

        painter.end()