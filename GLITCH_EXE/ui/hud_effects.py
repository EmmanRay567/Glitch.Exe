"""
ui/hud_effects.py

Jarvis-style visual effects for GLITCH.EXE.

HudTransitionOverlay
    A full-screen holographic "scan wipe" that plays whenever the HUD
    changes page: a bright scan line sweeps across in the direction of
    your swipe, a data-grid veil is torn away behind it, corner brackets
    snap in, and the destination name decodes out of random glyphs.

HandHologramOverlay
    A live holographic skeleton of your tracked hand, a rotating palm
    reticle, swipe-charge chevrons that build as you move your hand,
    and an expanding ring on pinch-select.

    It also draws the finger POINTER: a reticle locked to your index
    fingertip, corner brackets that glide onto whichever HUD button it
    is aiming at, and a flash when a pinch clicks that button.

Both widgets are transparent to the mouse and sit on top of the page
stack, so they never interfere with normal clicking.

HoloNavRail / HoloProjector
    The holographic navigation that replaces the old sidebar: a rail of
    holographic nodes across the top, and a projection bay on the left
    that shows a rotating hologram and briefing for each section.
"""

import math
import random
import time

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)

from PySide6.QtWidgets import QPushButton, QWidget


ACCENT = (57, 255, 120)
WHITE_GREEN = (200, 255, 220)
BACKGROUND = (2, 5, 4)

GLYPHS = "01ABCDEF<>/\\|[]{}#$%&*+=-_"


# Destination -> (big title, small subtitle) shown during transitions.
PAGE_TITLES = {
    "HOME": ("HOME CORE", "LIVE SYSTEM TELEMETRY"),
    "CHAT": ("COMM CHANNEL", "AI COMMUNICATION LINK ESTABLISHED"),
    "CREATE": ("CREATIVE SYSTEMS", "CONCEPT ENGINE ONLINE"),
    "SEARCH": ("INFO NETWORK", "LIVE SEARCH UPLINK ACTIVE"),
    "CODE": ("DEV ENVIRONMENT", "CODE ANALYSIS MODULE READY"),
    "APPS": ("APP CONTROL", "APPLICATION LAUNCHER ARMED"),
    "SETTINGS": ("CONFIGURATION", "SYSTEM PARAMETERS UNLOCKED"),
    "SYSTEM_MATRIX": ("SYSTEM MATRIX", "HARDWARE DIAGNOSTICS ONLINE"),
    "SECURITY_MATRIX": ("SECURITY MATRIX", "CYBER DEFENSE GRID ONLINE"),
}


def _color(alpha, rgb=ACCENT):

    return QColor(
        rgb[0],
        rgb[1],
        rgb[2],
        max(0, min(255, int(alpha))),
    )


def _clamp(value, low=0.0, high=1.0):

    return max(low, min(high, value))


def _ease_out(t):

    t = _clamp(t)

    return 1.0 - (1.0 - t) ** 3


# =========================================================
# PAGE TRANSITION
# =========================================================

class HudTransitionOverlay(QWidget):

    DURATION_MS = 780

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.progress = 0.0
        self.direction = 1
        self.vertical = False
        self.title = ""
        self.subtitle = ""

        self._frame = 0
        self._slices = []

        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(self.DURATION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._on_value)
        self._animation.finished.connect(self._on_finished)

        self.hide()

    # -----------------------------------------------------

    def play(self, title, subtitle="", direction=0, vertical=False):
        """
        direction:  1 = sweep left -> right (hand moved right)
                   -1 = sweep right -> left (hand moved left)
                    0 = default (left -> right)
        vertical:   True turns the sweep 90 degrees:
                    1 = top -> bottom (hand moved down)
                   -1 = bottom -> top (hand moved up)
        """

        parent = self.parentWidget()

        if parent is not None:

            self.setGeometry(parent.rect())

        self.direction = -1 if direction < 0 else 1
        self.vertical = bool(vertical)
        self.title = title or ""
        self.subtitle = subtitle or ""
        self.progress = 0.0
        self._frame = 0
        self._slices = []

        self.show()
        self.raise_()

        self._animation.stop()
        self._animation.start()

    def _on_value(self, value):

        self.progress = float(value)

        self._frame += 1

        # Refresh the "digital tear" slices a few times per second.
        if self.progress < 0.55 and self._frame % 3 == 0:

            height = max(1, self.height())

            self._slices = [
                (
                    random.uniform(0, height),
                    random.uniform(2, 14),
                    random.uniform(-30, 30),
                )
                for _ in range(random.randint(2, 5))
            ]

        elif self.progress >= 0.55:

            self._slices = []

        self.update()

    def _on_finished(self):

        self.progress = 0.0
        self.hide()

    # -----------------------------------------------------

    @staticmethod
    def _decode(text, progress, offset=0.0):

        if not text:

            return ""

        count = max(1, len(text))

        output = []

        for index, character in enumerate(text):

            if character == " ":

                output.append(" ")

                continue

            resolve_at = 0.08 + offset + 0.34 * (index / count)

            if progress >= resolve_at:

                output.append(character)

            else:

                output.append(random.choice(GLYPHS))

        return "".join(output)

    # -----------------------------------------------------

    def paintEvent(self, event):

        p = self.progress

        width = self.width()
        height = self.height()

        if width <= 0 or height <= 0 or p <= 0.0:

            return

        d = self.direction

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        # Vertical sweep: draw the same scan/veil turned 90 degrees.
        # Logical x then runs down the screen.
        if self.vertical:

            painter.translate(width, 0)

            painter.rotate(90)

            width, height = height, width

        # ---------------------------------------------
        # Scan line position
        # ---------------------------------------------

        sweep = _ease_out(p / 0.62)

        line_x = sweep * width if d > 0 else width - sweep * width

        line_alpha = 1.0 - _clamp((p - 0.55) / 0.10)

        # ---------------------------------------------
        # Data-grid veil ahead of the scan line
        # ---------------------------------------------

        veil_in = _clamp(p / 0.08)

        veil_alpha = 225 * veil_in * (1.0 - 0.2 * p)

        if d > 0:

            veil = QRectF(line_x, 0, width - line_x, height)

        else:

            veil = QRectF(0, 0, line_x, height)

        if veil.width() > 0:

            painter.fillRect(
                veil,
                _color(veil_alpha, BACKGROUND),
            )

            painter.save()

            painter.setClipRect(veil)

            # Moving grid.
            painter.setPen(
                QPen(_color(22 * veil_in), 1)
            )

            step = 48

            shift = int(p * 90) % step

            for x in range(-step, width + step, step):

                painter.drawLine(
                    x + shift,
                    0,
                    x + shift,
                    height,
                )

            for y in range(-step, height + step, step):

                painter.drawLine(
                    0,
                    y + shift,
                    width,
                    y + shift,
                )

            # Scanlines.
            painter.setPen(
                QPen(_color(14 * veil_in), 1)
            )

            for y in range(0, height, 3):

                painter.drawLine(0, y, width, y)

            painter.restore()

        # ---------------------------------------------
        # Glowing trail behind the scan line
        # ---------------------------------------------

        trail_width = width * 0.28

        if d > 0:

            trail = QRectF(
                line_x - trail_width,
                0,
                trail_width,
                height,
            )

            gradient = QLinearGradient(
                trail.left(),
                0,
                trail.right(),
                0,
            )

            gradient.setColorAt(0.0, _color(0))

            gradient.setColorAt(
                1.0,
                _color(70 * line_alpha),
            )

        else:

            trail = QRectF(
                line_x,
                0,
                trail_width,
                height,
            )

            gradient = QLinearGradient(
                trail.left(),
                0,
                trail.right(),
                0,
            )

            gradient.setColorAt(
                0.0,
                _color(70 * line_alpha),
            )

            gradient.setColorAt(1.0, _color(0))

        painter.fillRect(
            trail,
            QBrush(gradient),
        )

        # ---------------------------------------------
        # The scan line itself
        # ---------------------------------------------

        if line_alpha > 0.01:

            for glow_width, glow_alpha in (
                (22, 16),
                (10, 36),
            ):

                painter.setPen(
                    QPen(
                        _color(glow_alpha * line_alpha),
                        glow_width,
                    )
                )

                painter.drawLine(
                    QPointF(line_x, 0),
                    QPointF(line_x, height),
                )

            painter.setPen(
                QPen(
                    _color(255 * line_alpha, WHITE_GREEN),
                    2,
                )
            )

            painter.drawLine(
                QPointF(line_x, 0),
                QPointF(line_x, height),
            )

            # Measurement ticks trailing the line.
            painter.setPen(
                QPen(_color(150 * line_alpha), 1)
            )

            tick = -10 if d > 0 else 10

            for y in range(0, height, 24):

                painter.drawLine(
                    QPointF(line_x, y),
                    QPointF(line_x + tick, y),
                )

        # ---------------------------------------------
        # Digital tear slices
        # ---------------------------------------------

        for y, slice_height, dx in self._slices:

            painter.fillRect(
                QRectF(dx, y, width, slice_height),
                _color(26),
            )

        # Everything from here on is drawn upright.
        if self.vertical:

            painter.resetTransform()

            width = self.width()

            height = self.height()

        # ---------------------------------------------
        # Center pulse rings
        # ---------------------------------------------

        center = QPointF(width / 2, height / 2)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        radius = _ease_out(p) * max(width, height) * 0.55

        painter.setPen(
            QPen(_color(110 * (1.0 - p)), 2)
        )

        painter.drawEllipse(center, radius, radius)

        painter.setPen(
            QPen(_color(55 * (1.0 - p)), 1)
        )

        painter.drawEllipse(
            center,
            radius * 0.7,
            radius * 0.7,
        )

        # ---------------------------------------------
        # Corner brackets
        # ---------------------------------------------

        bracket_alpha = 200 * _clamp(
            min(p / 0.15, (1.0 - p) / 0.25)
        )

        if bracket_alpha > 1:

            inset = 26 + (
                1.0 - _ease_out(p / 0.5)
            ) * 70

            arm = 46

            left = inset
            top = inset
            right = width - inset
            bottom = height - inset

            painter.setPen(
                QPen(_color(bracket_alpha), 2)
            )

            for (cx, cy, sx, sy) in (
                (left, top, 1, 1),
                (right, top, -1, 1),
                (left, bottom, 1, -1),
                (right, bottom, -1, -1),
            ):

                painter.drawLine(
                    QPointF(cx, cy),
                    QPointF(cx + sx * arm, cy),
                )

                painter.drawLine(
                    QPointF(cx, cy),
                    QPointF(cx, cy + sy * arm),
                )

        # ---------------------------------------------
        # Destination readout
        # ---------------------------------------------

        text_alpha = _clamp(
            min(p / 0.18, (1.0 - p) / 0.25)
        )

        if self.title and text_alpha > 0.01:

            plate_width = width * 0.5

            painter.fillRect(
                QRectF(
                    width / 2 - plate_width / 2,
                    height / 2 - 58,
                    plate_width,
                    124,
                ),
                _color(120 * text_alpha, BACKGROUND),
            )

            title_font = QFont(
                "Consolas",
                28,
                QFont.Weight.Bold,
            )

            title_font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                6,
            )

            painter.setFont(title_font)

            painter.setPen(
                _color(255 * text_alpha, WHITE_GREEN)
            )

            painter.drawText(
                QRectF(0, height / 2 - 50, width, 60),
                Qt.AlignmentFlag.AlignCenter,
                self._decode(self.title, p),
            )

            underline = (
                width
                * 0.36
                * _ease_out((p - 0.05) / 0.4)
            )

            painter.setPen(
                QPen(_color(200 * text_alpha), 2)
            )

            painter.drawLine(
                QPointF(
                    width / 2 - underline / 2,
                    height / 2 + 22,
                ),
                QPointF(
                    width / 2 + underline / 2,
                    height / 2 + 22,
                ),
            )

            if self.vertical:

                arrow = "\u25bc\u25bc" if d > 0 else "\u25b2\u25b2"

            else:

                arrow = "\u00bb\u00bb" if d > 0 else "\u00ab\u00ab"

            sub_font = QFont("Consolas", 11)

            sub_font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                3,
            )

            painter.setFont(sub_font)

            painter.setPen(_color(190 * text_alpha))

            painter.drawText(
                QRectF(0, height / 2 + 30, width, 24),
                (
                    Qt.AlignmentFlag.AlignHCenter
                    | Qt.AlignmentFlag.AlignTop
                ),
                f"{arrow}  "
                + self._decode(self.subtitle, p, 0.10),
            )

        painter.end()


# =========================================================
# LIVE HAND HOLOGRAM
# =========================================================

class HandHologramOverlay(QWidget):

    BONES = (
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (17, 18), (18, 19), (19, 20),
        (0, 17),
    )

    TIPS = (4, 8, 12, 16, 20)

    PALM = (0, 5, 9, 13, 17)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.enabled = True

        self._target = []
        self._display = []

        self._alpha = 0.0
        self._target_alpha = 0.0
        self._last_update = 0.0

        self._charge = 0.0
        self._charge_display = 0.0

        self._spin = 0.0

        self._flash_direction = 0
        self._flash_vertical = False
        self._flash_start = 0.0

        self._charge_v = 0.0
        self._charge_v_display = 0.0

        self._pinch = None

        # Finger pointer / hover state.
        self._pointer = None
        self._pointer_display = None

        self._hover_target = None
        self._hover_rect = None
        self._hover_alpha = 0.0
        self._hover_label = ""

        self._click_flash = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        self.hide()

    # -----------------------------------------------------
    # Public slots
    # -----------------------------------------------------

    def set_pointer(self, x, y):

        if not self.enabled:

            return

        self._pointer = (float(x), float(y))

        if self._pointer_display is None:

            self._pointer_display = self._pointer

        self._last_update = time.perf_counter()

        self._target_alpha = 1.0

        self._start()

    def set_hover(self, rect, label=""):

        # rect: QRectF in this overlay's pixel coordinates, or None.
        if rect is None:

            self._hover_target = None

            return

        self._hover_target = QRectF(rect)

        self._hover_label = str(label or "")

        if self._hover_rect is None:

            self._hover_rect = QRectF(rect)

        self._start()

    def flash_click(self, rect):

        if not self.enabled or rect is None:

            return

        self._click_flash = (
            QRectF(rect),
            time.perf_counter(),
        )

        self._start()

    def set_enabled(self, enabled):

        self.enabled = bool(enabled)

        if not self.enabled:

            self.clear_hand()

    def set_landmarks(self, points):

        if not self.enabled or not points:

            return

        self._target = [
            (float(x), float(y))
            for x, y in points
        ]

        if len(self._display) != len(self._target):

            self._display = list(self._target)

        self._target_alpha = 1.0

        self._last_update = time.perf_counter()

        self._start()

    def clear_hand(self):

        self._target_alpha = 0.0

        self._charge = 0.0

        self._charge_v = 0.0

        self._pointer = None

        self._hover_target = None

    def set_swipe_charge(self, value):

        self._charge = float(value)

    def set_swipe_charge_vertical(self, value):

        self._charge_v = float(value)

    def flash_swipe(self, direction, vertical=False):

        if not self.enabled:

            return

        self._flash_direction = 1 if direction > 0 else -1

        self._flash_vertical = bool(vertical)

        self._flash_start = time.perf_counter()

        self._start()

    def flash_pinch(self, x, y):

        if not self.enabled:

            return

        self._pinch = (
            float(x),
            float(y),
            time.perf_counter(),
        )

        self._start()

    # -----------------------------------------------------
    # Animation loop
    # -----------------------------------------------------

    def _start(self):

        parent = self.parentWidget()

        if parent is not None and self.size() != parent.size():

            self.setGeometry(parent.rect())

        if not self.isVisible():

            self.show()

            self.raise_()

        if not self._timer.isActive():

            self._timer.start()

    def _tick(self):

        now = time.perf_counter()

        # Watchdog: if landmarks stop arriving, fade out.
        if now - self._last_update > 0.35:

            self._target_alpha = 0.0

        self._alpha += (
            self._target_alpha - self._alpha
        ) * 0.25

        self._charge_display += (
            self._charge - self._charge_display
        ) * 0.30

        self._charge_v_display += (
            self._charge_v - self._charge_v_display
        ) * 0.30

        self._spin += 0.06

        for index, (tx, ty) in enumerate(self._target):

            if index >= len(self._display):

                break

            dx, dy = self._display[index]

            self._display[index] = (
                dx + (tx - dx) * 0.55,
                dy + (ty - dy) * 0.55,
            )

        if self._pointer is not None and self._pointer_display is not None:

            px, py = self._pointer_display

            self._pointer_display = (
                px + (self._pointer[0] - px) * 0.65,
                py + (self._pointer[1] - py) * 0.65,
            )

        elif self._pointer is None:

            self._pointer_display = None

        if self._hover_target is not None and self._hover_rect is not None:

            cur = self._hover_rect
            tgt = self._hover_target

            self._hover_rect = QRectF(
                cur.x() + (tgt.x() - cur.x()) * 0.38,
                cur.y() + (tgt.y() - cur.y()) * 0.38,
                cur.width() + (tgt.width() - cur.width()) * 0.38,
                cur.height() + (tgt.height() - cur.height()) * 0.38,
            )

        self._hover_alpha += (
            (1.0 if self._hover_target is not None else 0.0)
            - self._hover_alpha
        ) * 0.28

        if self._hover_alpha < 0.01 and self._hover_target is None:

            self._hover_alpha = 0.0

            self._hover_rect = None

        if (
            self._click_flash is not None
            and now - self._click_flash[1] > 0.40
        ):

            self._click_flash = None

        if (
            self._pinch is not None
            and now - self._pinch[2] > 0.45
        ):

            self._pinch = None

        if (
            self._flash_direction != 0
            and now - self._flash_start > 0.50
        ):

            self._flash_direction = 0

        idle = (
            self._alpha < 0.01
            and self._target_alpha == 0.0
            and self._pinch is None
            and self._flash_direction == 0
            and self._hover_alpha == 0.0
            and self._click_flash is None
        )

        if idle:

            self._timer.stop()

            self._alpha = 0.0

            self.hide()

            return

        self.update()

    # -----------------------------------------------------
    # Painting
    # -----------------------------------------------------

    def paintEvent(self, event):

        width = self.width()
        height = self.height()

        if width <= 0 or height <= 0:

            return

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        now = time.perf_counter()

        a = self._alpha * 0.85

        points = [
            QPointF(x * width, y * height)
            for x, y in self._display
        ]

        if len(points) >= 21 and a > 0.02:

            self._paint_hand(painter, points, a)

        if a > 0.02:

            self._paint_hover(painter, a)

            self._paint_pointer(painter, a, width, height)

        self._paint_click_flash(painter, now)

        # Swipe flash chevrons across the screen.
        if self._flash_direction != 0:

            t = _clamp(
                (now - self._flash_start) / 0.45
            )

            direction = self._flash_direction

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.save()

            travel = width * 0.28

            if self._flash_vertical:

                # Rotate about the centre: +x becomes +y (down).
                painter.translate(width / 2, height / 2)

                painter.rotate(90)

                painter.translate(-width / 2, -height / 2)

                travel = height * 0.28

            for k in range(3):

                x = (
                    width * 0.5
                    + direction
                    * (
                        travel * _ease_out(t)
                        + (k - 1) * 34
                    )
                )

                y = height * 0.5

                painter.setPen(
                    QPen(
                        _color(
                            220 * (1.0 - t) * (1.0 - k * 0.2)
                        ),
                        3,
                    )
                )

                painter.drawPolyline(
                    QPolygonF(
                        [
                            QPointF(x - direction * 14, y - 24),
                            QPointF(x, y),
                            QPointF(x - direction * 14, y + 24),
                        ]
                    )
                )

            painter.restore()

        # Pinch ring.
        if self._pinch is not None:

            px, py, start = self._pinch

            t = _clamp((now - start) / 0.40)

            cx = px * width
            cy = py * height

            radius = 8 + 40 * _ease_out(t)

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.setPen(
                QPen(_color(230 * (1.0 - t)), 2)
            )

            painter.drawEllipse(
                QPointF(cx, cy),
                radius,
                radius,
            )

            painter.setPen(
                QPen(_color(180 * (1.0 - t)), 1)
            )

            painter.drawLine(
                QPointF(cx - radius - 8, cy),
                QPointF(cx - radius + 6, cy),
            )

            painter.drawLine(
                QPointF(cx + radius - 6, cy),
                QPointF(cx + radius + 8, cy),
            )

            painter.drawLine(
                QPointF(cx, cy - radius - 8),
                QPointF(cx, cy - radius + 6),
            )

            painter.drawLine(
                QPointF(cx, cy + radius - 6),
                QPointF(cx, cy + radius + 8),
            )

        painter.end()

    def _paint_hover(self, painter, a):

        rect = self._hover_rect

        ha = self._hover_alpha

        if rect is None or ha < 0.02:

            return

        ha = ha * min(1.0, a * 1.4)

        pulse = 0.5 + 0.5 * math.sin(self._spin * 2.2)

        grown = rect.adjusted(-5, -5, 5, 5)

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(_color(26 * ha + 14 * pulse * ha)))

        painter.drawRect(grown)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        arm = max(8.0, min(18.0, min(grown.width(), grown.height()) * 0.35))

        for glow, width_px, strength in (
            (ACCENT, 5, 55),
            (WHITE_GREEN, 2, 235),
        ):

            painter.setPen(
                QPen(
                    _color(strength * ha, glow),
                    width_px,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.SquareCap,
                )
            )

            l, t, r, b = (
                grown.left(),
                grown.top(),
                grown.right(),
                grown.bottom(),
            )

            for cx, cy, dx, dy in (
                (l, t, 1, 1),
                (r, t, -1, 1),
                (l, b, 1, -1),
                (r, b, -1, -1),
            ):

                painter.drawLine(
                    QPointF(cx, cy),
                    QPointF(cx + dx * arm, cy),
                )

                painter.drawLine(
                    QPointF(cx, cy),
                    QPointF(cx, cy + dy * arm),
                )

        if self._hover_label:

            font = QFont("Consolas", 8)

            font.setBold(True)

            painter.setFont(font)

            text = f"TARGET // {self._hover_label.upper()[:28]}"

            metrics = painter.fontMetrics()

            chip_w = metrics.horizontalAdvance(text) + 14

            chip_h = metrics.height() + 6

            chip_x = grown.left()

            chip_y = grown.top() - chip_h - 4

            if chip_y < 2:

                chip_y = grown.bottom() + 4

            chip = QRectF(chip_x, chip_y, chip_w, chip_h)

            painter.setPen(QPen(_color(150 * ha), 1))

            painter.setBrush(QBrush(_color(40 * ha, BACKGROUND)))

            painter.drawRect(chip)

            painter.setPen(QPen(_color(240 * ha, WHITE_GREEN)))

            painter.drawText(
                chip,
                Qt.AlignmentFlag.AlignCenter,
                text,
            )

    def _paint_pointer(self, painter, a, width, height):

        if self._pointer_display is None:

            return

        cx = self._pointer_display[0] * width

        cy = self._pointer_display[1] * height

        lock = self._hover_alpha

        spin = math.degrees(self._spin)

        radius = 17.0 - 6.0 * lock

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(_color(60 * a), 5))

        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setPen(QPen(_color((160 + 80 * lock) * a, WHITE_GREEN), 1.6))

        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setPen(QPen(_color(230 * a, WHITE_GREEN), 2))

        for offset in (0, 120, 240):

            painter.drawArc(
                QRectF(
                    cx - radius - 5,
                    cy - radius - 5,
                    (radius + 5) * 2,
                    (radius + 5) * 2,
                ),
                int((spin * (1.0 + 2.0 * lock) + offset) * 16),
                36 * 16,
            )

        tick = 6.0

        painter.setPen(QPen(_color(210 * a, WHITE_GREEN), 1.4))

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):

            painter.drawLine(
                QPointF(cx + dx * (radius + 2), cy + dy * (radius + 2)),
                QPointF(
                    cx + dx * (radius + 2 + tick),
                    cy + dy * (radius + 2 + tick),
                ),
            )

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(_color(255 * a, WHITE_GREEN)))

        painter.drawEllipse(QPointF(cx, cy), 2.6 + 1.4 * lock, 2.6 + 1.4 * lock)

    def _paint_click_flash(self, painter, now):

        if self._click_flash is None:

            return

        rect, start = self._click_flash

        t = _clamp((now - start) / 0.38)

        grow = 4 + 22 * _ease_out(t)

        flash = rect.adjusted(-grow, -grow, grow, grow)

        painter.setPen(QPen(_color(240 * (1.0 - t), WHITE_GREEN), 2))

        painter.setBrush(QBrush(_color(70 * (1.0 - t) ** 2)))

        painter.drawRect(flash)

    def _paint_hand(self, painter, points, a):

        # Bones: soft glow underneath, crisp core on top.
        for line_width, line_alpha in (
            (9, 18),
            (4, 40),
            (1.6, 190),
        ):

            painter.setPen(
                QPen(
                    _color(
                        line_alpha * a,
                        WHITE_GREEN
                        if line_width < 2
                        else ACCENT,
                    ),
                    line_width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )

            for start, end in self.BONES:

                painter.drawLine(
                    points[start],
                    points[end],
                )

        # Joints.
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(_color(200 * a)))

        for point in points:

            painter.drawEllipse(point, 2.5, 2.5)

        # Fingertip rings with a rotating arc.
        painter.setBrush(Qt.BrushStyle.NoBrush)

        spin_degrees = math.degrees(self._spin)

        for index in self.TIPS:

            tip = points[index]

            painter.setPen(
                QPen(_color(220 * a), 1.2)
            )

            painter.drawEllipse(tip, 7, 7)

            painter.setPen(
                QPen(_color(160 * a), 1.2)
            )

            painter.drawArc(
                QRectF(
                    tip.x() - 12,
                    tip.y() - 12,
                    24,
                    24,
                ),
                int(spin_degrees * 16),
                90 * 16,
            )

        # Palm reticle.
        cx = sum(points[i].x() for i in self.PALM) / len(self.PALM)
        cy = sum(points[i].y() for i in self.PALM) / len(self.PALM)

        span = math.hypot(
            points[5].x() - points[17].x(),
            points[5].y() - points[17].y(),
        )

        radius = span * 0.9 + 10

        dashed = QPen(_color(90 * a), 1)

        dashed.setStyle(Qt.PenStyle.DashLine)

        painter.setPen(dashed)

        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setPen(QPen(_color(200 * a), 2))

        for offset in (0, 180):

            painter.drawArc(
                QRectF(
                    cx - radius - 6,
                    cy - radius - 6,
                    (radius + 6) * 2,
                    (radius + 6) * 2,
                ),
                int((-spin_degrees * 1.4 + offset) * 16),
                50 * 16,
            )

        # Swipe-charge chevrons build up as the hand accelerates.
        # Whichever axis is moving faster wins.
        charge = self._charge_display

        vertical = abs(self._charge_v_display) > abs(charge)

        if vertical:

            charge = self._charge_v_display

        if abs(charge) > 0.08:

            direction = 1 if charge > 0 else -1

            strength = _clamp(abs(charge))

            painter.save()

            if vertical:

                painter.translate(cx, cy)

                painter.rotate(90)

                painter.translate(-cx, -cy)

            for k in range(3):

                tip_x = cx + direction * (radius + 24 + k * 18)

                painter.setPen(
                    QPen(
                        _color(
                            235 * strength * a * (1.0 - k * 0.25)
                        ),
                        3,
                    )
                )

                painter.drawPolyline(
                    QPolygonF(
                        [
                            QPointF(tip_x - direction * 9, cy - 12),
                            QPointF(tip_x, cy),
                            QPointF(tip_x - direction * 9, cy + 12),
                        ]
                    )
                )

            painter.restore()


# =========================================================
# HOLOGRAPHIC NAVIGATION + PROJECTION BAY
# =========================================================
#
# HoloNavRail     replaces the old left sidebar. A floating rail of
#                 holographic nodes across the top of the HUD. Every
#                 node is a real QPushButton, so mouse clicks AND the
#                 finger-pointer pinch-click both work on it.
#
# HoloProjector   sits where the sidebar used to be. It projects a
#                 rotating wireframe hologram of the current section,
#                 decodes its name and briefs you on what it does.
#                 Hovering a node (mouse or finger) previews it.
#
# Edit PAGE_BRIEFS below to change any wording.

NAV_ORDER = (
    "HOME",
    "CHAT",
    "CREATE",
    "SEARCH",
    "CODE",
    "APPS",
    "SYSTEM_MATRIX",
    "SECURITY_MATRIX",
    "SETTINGS",
)

NAV_LABELS = {
    "HOME": "HOME",
    "CHAT": "CHAT",
    "CREATE": "CREATE",
    "SEARCH": "SEARCH",
    "CODE": "CODE",
    "APPS": "APPS",
    "SYSTEM_MATRIX": "SYSTEM",
    "SECURITY_MATRIX": "SECURITY",
    "SETTINGS": "SETTINGS",
}

# Attribute names kept from the old Sidebar so existing code such as
# self.sidebar.chat_button keeps working.
NAV_ATTRS = {
    "HOME": "home_button",
    "CHAT": "chat_button",
    "CREATE": "create_button",
    "SEARCH": "search_button",
    "CODE": "code_button",
    "APPS": "apps_button",
    "SYSTEM_MATRIX": "matrix_button",
    "SECURITY_MATRIX": "security_button",
    "SETTINGS": "settings_button",
}

PAGE_BRIEFS = {
    "HOME": {
        "code": "MOD-00",
        "summary": (
            "Primary command core. Live system telemetry streams "
            "into the reactor while GLITCH stands by for orders."
        ),
        "functions": [
            "Live telemetry",
            "Reactor status",
            "Command console",
        ],
    },
    "CHAT": {
        "code": "MOD-01",
        "summary": (
            "Direct communication link with GLITCH. Speak or type "
            "and responses stream back through the comm channel."
        ),
        "functions": [
            "Conversation",
            "Voice replies",
            "Context memory",
        ],
    },
    "CREATE": {
        "code": "MOD-02",
        "summary": (
            "Concept engine for ideas, drafts and creative builds, "
            "from a rough spark to a finished concept."
        ),
        "functions": [
            "Idea generation",
            "Drafting",
            "Concept design",
        ],
    },
    "SEARCH": {
        "code": "MOD-03",
        "summary": (
            "Live information uplink. Query the network and receive "
            "condensed intelligence on any subject."
        ),
        "functions": [
            "Network lookup",
            "Weather + location",
            "Fact retrieval",
        ],
    },
    "CODE": {
        "code": "MOD-04",
        "summary": (
            "Development environment for writing, reviewing and "
            "debugging code with GLITCH at your side."
        ),
        "functions": [
            "Code generation",
            "Error analysis",
            "Refactoring",
        ],
    },
    "APPS": {
        "code": "MOD-05",
        "summary": (
            "Application control grid. Launch and manage the "
            "programs on this machine."
        ),
        "functions": [
            "App launcher",
            "Quick access",
            "Process control",
        ],
    },
    "SYSTEM_MATRIX": {
        "code": "MTX-01",
        "summary": (
            "Hardware diagnostics layer. Deep readouts for the "
            "processor, memory, storage and thermals."
        ),
        "functions": [
            "CPU + memory",
            "Storage health",
            "Thermals",
        ],
    },
    "SECURITY_MATRIX": {
        "code": "MTX-02",
        "summary": (
            "Cyber defense grid. Threat scans, findings and "
            "protective actions for this machine."
        ),
        "functions": [
            "Threat scans",
            "Findings review",
            "Defensive actions",
        ],
    },
    "SETTINGS": {
        "code": "CFG-00",
        "summary": (
            "System configuration. Tune voice, gestures, location "
            "and core GLITCH parameters."
        ),
        "functions": [
            "Voice + gesture",
            "Location",
            "Core parameters",
        ],
    },
}


def _decode_text(text, progress, seed=0):

    """Text that resolves left-to-right out of random glyphs."""

    if not text:

        return ""

    rng = random.Random(seed + int(progress * 40))

    count = max(1, len(text))

    output = []

    for index, character in enumerate(text):

        if character == " " or progress >= 0.15 + 0.85 * (index / count):

            output.append(character)

        else:

            output.append(rng.choice(GLYPHS))

    return "".join(output)


def _wrap_text(text, metrics, width):

    lines = []

    current = ""

    for word in text.split():

        trial = f"{current} {word}".strip()

        if current and metrics.horizontalAdvance(trial) > width:

            lines.append(current)

            current = word

        else:

            current = trial

    if current:

        lines.append(current)

    return lines


def _mono_font(pixel_size, bold=False):

    font = QFont("Consolas")

    font.setStyleHint(QFont.StyleHint.Monospace)

    font.setPixelSize(max(6, int(pixel_size)))

    font.setBold(bold)

    return font


# ---------------------------------------------------------
# Flat 2D glyphs for the nav nodes
# ---------------------------------------------------------

def _draw_nav_glyph(painter, key, cx, cy, s, color):

    pen = QPen(color, 1.6)

    pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)

    painter.setBrush(Qt.BrushStyle.NoBrush)

    def poly(points, closed=True):

        polygon = QPolygonF(
            [QPointF(cx + x * s, cy + y * s) for x, y in points]
        )

        if closed:

            painter.drawPolygon(polygon)

        else:

            painter.drawPolyline(polygon)

    if key == "HOME":

        poly(
            [
                (math.cos(math.radians(a)), math.sin(math.radians(a)))
                for a in range(30, 390, 60)
            ]
        )

        painter.setBrush(QBrush(color))

        painter.drawEllipse(QPointF(cx, cy), s * 0.28, s * 0.28)

    elif key == "CHAT":

        for i, h in enumerate((0.35, 0.75, 1.0, 0.6, 0.3)):

            x = cx + (i - 2) * s * 0.42

            painter.drawLine(
                QPointF(x, cy - h * s * 0.85),
                QPointF(x, cy + h * s * 0.85),
            )

    elif key == "CREATE":

        poly(
            [
                (0, -1), (0.22, -0.22), (1, 0), (0.22, 0.22),
                (0, 1), (-0.22, 0.22), (-1, 0), (-0.22, -0.22),
            ]
        )

    elif key == "SEARCH":

        painter.drawEllipse(
            QPointF(cx - s * 0.15, cy - s * 0.15), s * 0.62, s * 0.62
        )

        painter.drawLine(
            QPointF(cx + s * 0.3, cy + s * 0.3),
            QPointF(cx + s * 0.95, cy + s * 0.95),
        )

    elif key == "CODE":

        poly([(-0.45, -0.7), (-1, 0), (-0.45, 0.7)], closed=False)

        poly([(0.45, -0.7), (1, 0), (0.45, 0.7)], closed=False)

        poly([(0.18, -0.85), (-0.18, 0.85)], closed=False)

    elif key == "APPS":

        for dx in (-0.5, 0.5):

            for dy in (-0.5, 0.5):

                painter.drawRect(
                    QRectF(
                        cx + (dx - 0.36) * s,
                        cy + (dy - 0.36) * s,
                        0.72 * s,
                        0.72 * s,
                    )
                )

    elif key == "SYSTEM_MATRIX":

        painter.drawRect(
            QRectF(cx - 0.6 * s, cy - 0.6 * s, 1.2 * s, 1.2 * s)
        )

        painter.drawRect(
            QRectF(cx - 0.25 * s, cy - 0.25 * s, 0.5 * s, 0.5 * s)
        )

        for k in (-0.3, 0.3):

            for a, b, c, d in (
                (k, -0.6, k, -1.0),
                (k, 0.6, k, 1.0),
                (-0.6, k, -1.0, k),
                (0.6, k, 1.0, k),
            ):

                painter.drawLine(
                    QPointF(cx + a * s, cy + b * s),
                    QPointF(cx + c * s, cy + d * s),
                )

    elif key == "SECURITY_MATRIX":

        poly(
            [
                (-0.8, -0.85), (0.8, -0.85), (0.8, 0.05),
                (0, 1.0), (-0.8, 0.05),
            ]
        )

        poly([(-0.3, 0.0), (-0.05, 0.3), (0.38, -0.3)], closed=False)

    elif key == "SETTINGS":

        painter.drawEllipse(QPointF(cx, cy), s * 0.62, s * 0.62)

        painter.drawEllipse(QPointF(cx, cy), s * 0.22, s * 0.22)

        for i in range(8):

            a = i * math.pi / 4

            painter.drawLine(
                QPointF(cx + math.cos(a) * s * 0.62, cy + math.sin(a) * s * 0.62),
                QPointF(cx + math.cos(a) * s * 0.98, cy + math.sin(a) * s * 0.98),
            )


# ---------------------------------------------------------
# 3D wireframe models for the projector
# ---------------------------------------------------------

def _ring(radius, n=36, y=0.0, plane="xz"):

    points = []

    for i in range(n + 1):

        a = 2 * math.pi * i / n

        u = math.cos(a) * radius

        v = math.sin(a) * radius

        if plane == "xz":

            points.append((u, y, v))

        elif plane == "xy":

            points.append((u, v, y))

        else:

            points.append((y, u, v))

    return points


def _tilt(points, ax=0.0, az=0.0):

    out = []

    for x, y, z in points:

        cy, sy = math.cos(ax), math.sin(ax)

        y, z = y * cy - z * sy, y * sy + z * cy

        cz, sz = math.cos(az), math.sin(az)

        x, y = x * cz - y * sz, x * sz + y * cz

        out.append((x, y, z))

    return out


def _box_edges(cx, cy, cz, hx, hy, hz):

    corners = [
        (cx + sx * hx, cy + sy * hy, cz + sz * hz)
        for sx in (-1, 1)
        for sy in (-1, 1)
        for sz in (-1, 1)
    ]

    lines = []

    for i in range(8):

        for j in range(i + 1, 8):

            a, b = corners[i], corners[j]

            if sum(1 for k in range(3) if a[k] != b[k]) == 1:

                lines.append([a, b])

    return lines


def _sphere(radius, lats=5, lons=8):

    lines = []

    for i in range(1, lats + 1):

        phi = math.pi * i / (lats + 1) - math.pi / 2

        lines.append(
            _ring(radius * math.cos(phi), 36, radius * math.sin(phi))
        )

    for j in range(lons):

        a = math.pi * j / lons

        meridian = []

        for k in range(37):

            t = 2 * math.pi * k / 36

            meridian.append(
                (
                    radius * math.cos(t) * math.cos(a),
                    radius * math.sin(t),
                    radius * math.cos(t) * math.sin(a),
                )
            )

        lines.append(meridian)

    return lines


def _extrude(outline, depth):

    front = [(x, y, depth) for x, y in outline] + [(outline[0][0], outline[0][1], depth)]

    back = [(x, y, -depth) for x, y in outline] + [(outline[0][0], outline[0][1], -depth)]

    lines = [front, back]

    for x, y in outline:

        lines.append([(x, y, depth), (x, y, -depth)])

    return lines


def _build_model(key):

    if key == "HOME":

        lines = _sphere(1.0, 4, 6)

        lines.append(_ring(0.38, 24, 0.0, "xz"))

        lines.append(_ring(0.38, 24, 0.0, "xy"))

        lines.append(_tilt(_ring(1.32, 48), ax=0.35))

        return lines

    if key == "CHAT":

        lines = [_ring(r, 40, 0.0, "xy") for r in (0.55, 0.85, 1.15)]

        wave = []

        for i in range(61):

            x = -1.3 + 2.6 * i / 60

            env = math.exp(-(x * 1.4) ** 2)

            wave.append((x, 0.55 * env * math.sin(x * 11), 0.0))

        lines.append(wave)

        lines.append(_ring(1.15, 40, 0.0, "xz"))

        return lines

    if key == "CREATE":

        p = (1 + 5 ** 0.5) / 2

        verts = []

        for a, b in ((1, p), (-1, p), (1, -p), (-1, -p)):

            verts += [(0, a, b), (a, b, 0), (b, 0, a)]

        scale = 1.0 / math.sqrt(1 + p * p)

        verts = [(x * scale, y * scale, z * scale) for x, y, z in verts]

        lines = []

        for i in range(len(verts)):

            for j in range(i + 1, len(verts)):

                d = math.dist(verts[i], verts[j])

                if abs(d - 2 * scale) < 0.05:

                    lines.append([verts[i], verts[j]])

        lines.append(_ring(0.35, 20, 0.0, "xz"))

        return lines

    if key == "SEARCH":

        lines = _sphere(0.9, 3, 4)

        lines.append(_tilt(_ring(1.3, 48), ax=0.45, az=0.3))

        lines.append(_tilt(_ring(1.18, 48), ax=-0.6, az=-0.2))

        return lines

    if key == "CODE":

        lines = _box_edges(0, 0, 0, 0.9, 0.9, 0.9)

        lines += _box_edges(0, 0, 0, 0.42, 0.42, 0.42)

        for sx in (-1, 1):

            for sy in (-1, 1):

                for sz in (-1, 1):

                    lines.append(
                        [
                            (sx * 0.9, sy * 0.9, sz * 0.9),
                            (sx * 0.42, sy * 0.42, sz * 0.42),
                        ]
                    )

        return lines

    if key == "APPS":

        lines = []

        for sx in (-1, 1):

            for sy in (-1, 1):

                for sz in (-1, 1):

                    lines += _box_edges(
                        sx * 0.5, sy * 0.5, sz * 0.5, 0.3, 0.3, 0.3
                    )

        return lines

    if key == "SYSTEM_MATRIX":

        lines = _box_edges(0, 0, 0, 1.0, 0.14, 1.0)

        lines += _box_edges(0, 0.2, 0, 0.42, 0.06, 0.42)

        for k in (-0.6, -0.2, 0.2, 0.6):

            lines.append([(k, 0, 1.0), (k, -0.35, 1.3)])

            lines.append([(k, 0, -1.0), (k, -0.35, -1.3)])

            lines.append([(1.0, 0, k), (1.3, -0.35, k)])

            lines.append([(-1.0, 0, k), (-1.3, -0.35, k)])

        return lines

    if key == "SECURITY_MATRIX":

        shield = [
            (-0.85, 0.95), (0.85, 0.95), (0.85, 0.1),
            (0.0, -1.05), (-0.85, 0.1),
        ]

        lines = _extrude(shield, 0.18)

        inner = [(x * 0.62, y * 0.62 + 0.03) for x, y in shield]

        lines += _extrude(inner, 0.08)

        lines.append(_ring(1.35, 48, 0.0, "xz"))

        return lines

    if key == "SETTINGS":

        outline = []

        teeth = 10

        for i in range(teeth * 4):

            a = 2 * math.pi * i / (teeth * 4)

            r = 1.0 if (i % 4) in (1, 2) else 0.78

            outline.append((math.cos(a) * r, math.sin(a) * r))

        lines = _extrude(outline, 0.16)

        lines.append(_ring(0.3, 24, 0.16, "xy"))

        lines.append(_ring(0.3, 24, -0.16, "xy"))

        return lines

    return _sphere(1.0, 3, 4)


# ---------------------------------------------------------
# Nav node
# ---------------------------------------------------------

class HoloNavButton(QPushButton):

    def __init__(self, key, parent=None):

        super().__init__(NAV_LABELS.get(key, key), parent)

        self.nav_key = key

        self.setObjectName(f"holo_nav_{key.lower()}")

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setFlat(True)

        self.setToolTip(
            PAGE_TITLES.get(key, (key, ""))[0]
        )

        self.active = False

        self.hovered = False

        self.glow = 0.0

    def enterEvent(self, event):

        self.hovered = True

        rail = self.parentWidget()

        if isinstance(rail, HoloNavRail):

            rail.hovered.emit(self.nav_key)

        super().enterEvent(event)

    def leaveEvent(self, event):

        self.hovered = False

        rail = self.parentWidget()

        if isinstance(rail, HoloNavRail):

            rail.hovered.emit("")

        super().leaveEvent(event)

    def step(self):

        target = 1.0 if self.active else (0.6 if self.hovered else 0.0)

        before = self.glow

        self.glow += (target - self.glow) * 0.22

        return abs(self.glow - before) > 0.002

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()

        h = self.height()

        g = self.glow

        cut = 9

        frame = QPolygonF(
            [
                QPointF(cut, 1), QPointF(w - 1, 1),
                QPointF(w - 1, h - cut), QPointF(w - cut, h - 1),
                QPointF(1, h - 1), QPointF(1, cut),
            ]
        )

        gradient = QLinearGradient(0, 0, 0, h)

        gradient.setColorAt(0.0, _color(14 + 46 * g))

        gradient.setColorAt(1.0, _color(4 + 18 * g, BACKGROUND))

        painter.setBrush(QBrush(gradient))

        painter.setPen(QPen(_color(55 + 185 * g), 1))

        painter.drawPolygon(frame)

        if self.isDown():

            painter.setBrush(QBrush(_color(70)))

            painter.drawPolygon(frame)

        # Corner ticks.
        painter.setPen(QPen(_color(120 + 135 * g, WHITE_GREEN), 1.4))

        painter.drawLine(QPointF(cut, 1), QPointF(cut + 10, 1))

        painter.drawLine(QPointF(w - 1, h - cut), QPointF(w - 1, h - cut - 8))

        glyph_color = _color(150 + 105 * g, WHITE_GREEN if g > 0.5 else ACCENT)

        glyph_size = max(6.0, min(11.0, h * 0.17))

        _draw_nav_glyph(
            painter,
            self.nav_key,
            w / 2,
            h * 0.36,
            glyph_size,
            glyph_color,
        )

        painter.setFont(_mono_font(max(9, min(12, h * 0.19)), bold=g > 0.5))

        painter.setPen(QPen(_color(170 + 85 * g, WHITE_GREEN)))

        painter.drawText(
            QRectF(2, h * 0.58, w - 4, h * 0.36),
            Qt.AlignmentFlag.AlignCenter,
            self.text(),
        )

        if self.active:

            painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(QBrush(_color(230, WHITE_GREEN)))

            painter.drawRect(QRectF(w * 0.3, h - 3, w * 0.4, 2))

        painter.end()


# ---------------------------------------------------------
# Nav rail
# ---------------------------------------------------------

class HoloNavRail(QWidget):

    hovered = Signal(str)

    GAP = 8

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.buttons = {}

        for key in NAV_ORDER:

            button = HoloNavButton(key, self)

            self.buttons[key] = button

            setattr(self, NAV_ATTRS[key], button)

        self.active_key = "HOME"

        self._carriage = None

        self._carriage_target = None

        self._phase = 0.0

        self._timer = QTimer(self)

        self._timer.setInterval(33)

        self._timer.timeout.connect(self._tick)

        self._timer.start()

    # Public -------------------------------------------------

    def button_list(self):

        return [self.buttons[key] for key in NAV_ORDER]

    def set_active(self, key):

        key = str(key or "").strip().upper()

        if key not in self.buttons:

            return

        self.active_key = key

        for name, button in self.buttons.items():

            button.active = name == key

        self._carriage_target = self._button_span(key)

        if self._carriage is None:

            self._carriage = self._carriage_target

    def set_active_button(self, button):

        for key, candidate in self.buttons.items():

            if candidate is button:

                self.set_active(key)

                return

    # Layout -------------------------------------------------

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self._layout_buttons()

    def _layout_buttons(self):

        count = len(NAV_ORDER)

        usable = self.width() - 36

        button_w = max(54, min(124, (usable - self.GAP * (count - 1)) / count))

        total = button_w * count + self.GAP * (count - 1)

        left = (self.width() - total) / 2

        button_h = max(36, self.height() - 18)

        for index, key in enumerate(NAV_ORDER):

            x = left + index * (button_w + self.GAP)

            self.buttons[key].setGeometry(int(x), 4, int(button_w), int(button_h))

        self._carriage_target = self._button_span(self.active_key)

        self._carriage = self._carriage_target

    def _button_span(self, key):

        button = self.buttons.get(key)

        if button is None:

            return None

        geometry = button.geometry()

        return (float(geometry.left()), float(geometry.right()))

    # Animation ----------------------------------------------

    def _tick(self):

        if not self.isVisible():

            return

        self._phase = (self._phase + 0.012) % 1.0

        for button in self.buttons.values():

            if button.step():

                button.update()

        if self._carriage is not None and self._carriage_target is not None:

            l0, r0 = self._carriage

            l1, r1 = self._carriage_target

            self._carriage = (l0 + (l1 - l0) * 0.24, r0 + (r1 - r0) * 0.24)

        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()

        h = self.height()

        base_y = h - 6

        # Baseline with fading ends.
        gradient = QLinearGradient(0, 0, w, 0)

        gradient.setColorAt(0.0, _color(0))

        gradient.setColorAt(0.08, _color(110))

        gradient.setColorAt(0.92, _color(110))

        gradient.setColorAt(1.0, _color(0))

        painter.setPen(QPen(QBrush(gradient), 1))

        painter.drawLine(QPointF(0, base_y), QPointF(w, base_y))

        # Tick marks.
        painter.setPen(QPen(_color(55), 1))

        for x in range(18, w - 18, 14):

            painter.drawLine(QPointF(x, base_y + 1), QPointF(x, base_y + 4))

        # Shimmer travelling along the rail.
        sx = self._phase * (w + 160) - 80

        shimmer = QLinearGradient(sx - 80, 0, sx + 80, 0)

        shimmer.setColorAt(0.0, _color(0, WHITE_GREEN))

        shimmer.setColorAt(0.5, _color(170, WHITE_GREEN))

        shimmer.setColorAt(1.0, _color(0, WHITE_GREEN))

        painter.setPen(QPen(QBrush(shimmer), 1.5))

        painter.drawLine(QPointF(max(0, sx - 80), base_y), QPointF(min(w, sx + 80), base_y))

        # End brackets.
        painter.setPen(QPen(_color(160), 1.4))

        for x, d in ((4, 1), (w - 4, -1)):

            painter.drawLine(QPointF(x, base_y - 14), QPointF(x, base_y + 4))

            painter.drawLine(QPointF(x, base_y - 14), QPointF(x + d * 7, base_y - 14))

        # Carriage under the active node.
        if self._carriage is not None:

            left, right = self._carriage

            painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(QBrush(_color(60)))

            painter.drawRect(QRectF(left, base_y - 2, right - left, 5))

            painter.setBrush(QBrush(_color(240, WHITE_GREEN)))

            painter.drawRect(QRectF(left + 6, base_y - 1, right - left - 12, 2))

            mid = (left + right) / 2

            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(mid - 5, base_y + 5),
                        QPointF(mid + 5, base_y + 5),
                        QPointF(mid, base_y + 1),
                    ]
                )
            )

        painter.end()


# ---------------------------------------------------------
# Projection bay
# ---------------------------------------------------------

class HoloProjector(QWidget):

    BOOT_S = 0.95

    PREVIEW_BOOT_S = 0.45

    PREVIEW_DWELL_S = 0.12

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._models = {}

        self.active_key = "HOME"

        self._preview_key = ""

        self._preview_since = 0.0

        self._shown_key = "HOME"

        self._shown_is_preview = False

        self._boot_start = time.perf_counter()

        self._boot_len = self.BOOT_S

        self._angle = 0.0

        self._timer = QTimer(self)

        self._timer.setInterval(33)

        self._timer.timeout.connect(self._tick)

    # Public -------------------------------------------------

    def set_active(self, key):

        key = str(key or "").strip().upper()

        if key not in PAGE_BRIEFS:

            return

        self.active_key = key

        self._preview_key = ""

        self._show(key, preview=False)

    def preview(self, key):

        key = str(key or "").strip().upper()

        if key == self._preview_key:

            return

        self._preview_key = key if key in PAGE_BRIEFS else ""

        self._preview_since = time.perf_counter()

    # Internals ----------------------------------------------

    def _show(self, key, preview):

        if key == self._shown_key and preview == self._shown_is_preview:

            return

        self._shown_key = key

        self._shown_is_preview = preview

        self._boot_start = time.perf_counter()

        self._boot_len = self.PREVIEW_BOOT_S if preview else self.BOOT_S

    def _model(self, key):

        if key not in self._models:

            self._models[key] = _build_model(key)

        return self._models[key]

    def showEvent(self, event):

        self._timer.start()

        super().showEvent(event)

    def hideEvent(self, event):

        self._timer.stop()

        super().hideEvent(event)

    def _tick(self):

        now = time.perf_counter()

        self._angle += 0.018

        if self._preview_key and self._preview_key != self.active_key:

            if now - self._preview_since >= self.PREVIEW_DWELL_S:

                self._show(self._preview_key, preview=True)

        elif now - self._preview_since >= 0.25:

            self._show(self.active_key, preview=False)

        self.update()

    # Painting -----------------------------------------------

    def paintEvent(self, event):

        w = self.width()

        h = self.height()

        if w < 80 or h < 120:

            return

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        now = time.perf_counter()

        key = self._shown_key

        brief = PAGE_BRIEFS.get(key, PAGE_BRIEFS["HOME"])

        title, subtitle = PAGE_TITLES.get(key, (key, ""))

        boot = _clamp((now - self._boot_start) / self._boot_len)

        flicker = 0.93 + 0.07 * math.sin(now * 31.0)

        if random.random() < 0.012:

            flicker *= 0.55

        pad = 12

        # Panel frame.
        painter.setPen(Qt.PenStyle.NoPen)

        panel = QLinearGradient(0, 0, 0, h)

        panel.setColorAt(0.0, _color(16))

        panel.setColorAt(1.0, _color(4))

        painter.setBrush(QBrush(panel))

        painter.drawRect(QRectF(0, 0, w, h))

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.setPen(QPen(_color(180), 1.4))

        arm = 16

        for x, y, dx, dy in ((0.5, 0.5, 1, 1), (w - 0.5, 0.5, -1, 1), (0.5, h - 0.5, 1, -1), (w - 0.5, h - 0.5, -1, -1)):

            painter.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))

            painter.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))

        # Header.
        painter.setFont(_mono_font(10, bold=True))

        painter.setPen(QPen(_color(200)))

        header = "HOLO-PREVIEW" if self._shown_is_preview else "HOLO-PROJECTION"

        painter.drawText(QRectF(pad, 8, w - pad * 2, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, header)

        painter.setPen(QPen(_color(140, WHITE_GREEN)))

        painter.drawText(QRectF(pad, 8, w - pad * 2, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, brief["code"])

        painter.setPen(QPen(_color(60), 1))

        painter.drawLine(QPointF(pad, 28), QPointF(w - pad, 28))

        # Emblem bay.
        bay_top = 34

        bay_h = min(w * 0.95, h * 0.46)

        emitter_y = bay_top + bay_h - 10

        cx = w / 2

        cy = bay_top + bay_h * 0.44

        self._paint_beam(painter, cx, emitter_y, bay_top, w, boot, flicker)

        self._paint_model(painter, key, cx, cy, min(w, bay_h) * 0.30, boot, flicker)

        # Scan line through the emblem.
        scan = ((now * 0.42) % 1.0)

        sy = bay_top + 6 + scan * (emitter_y - bay_top - 12)

        painter.setPen(QPen(_color(70 * flicker, WHITE_GREEN), 1))

        painter.drawLine(QPointF(pad + 10, sy), QPointF(w - pad - 10, sy))

        # Text block.
        y = bay_top + bay_h + 8

        text_w = w - pad * 2

        painter.setFont(_mono_font(max(13, min(19, w * 0.075)), bold=True))

        painter.setPen(QPen(_color(250 * flicker, WHITE_GREEN)))

        painter.drawText(
            QRectF(pad, y, text_w, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            _decode_text(title, _clamp(boot * 1.6), seed=len(title)),
        )

        y += 26

        painter.setFont(_mono_font(9))

        painter.setPen(QPen(_color(170 * flicker)))

        painter.drawText(
            QRectF(pad, y, text_w, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            _decode_text(subtitle, _clamp(boot * 1.4 - 0.1), seed=7),
        )

        y += 20

        painter.setPen(QPen(_color(70), 1))

        painter.drawLine(QPointF(pad, y), QPointF(w - pad, y))

        for k in range(5):

            painter.drawLine(QPointF(pad + k * 8, y), QPointF(pad + k * 8, y + 3))

        y += 10

        # Description, typed in.
        painter.setFont(_mono_font(11))

        summary = brief["summary"]

        y_desc = y

        metrics = painter.fontMetrics()

        line_h = metrics.height() + 2

        wrapped = _wrap_text(summary, metrics, text_w)

        typed = int(len(summary) * _clamp((boot - 0.25) / 0.6))

        painter.setPen(QPen(_color(215 * flicker, WHITE_GREEN)))

        for line in wrapped:

            if typed <= 0:

                break

            painter.drawText(
                QRectF(pad, y, text_w, line_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line[:typed],
            )

            typed -= len(line) + 1

            y += line_h

        y = y_desc + len(wrapped) * line_h + 14

        # Function list.
        if y + 20 < h - 30:

            painter.setFont(_mono_font(9, bold=True))

            painter.setPen(QPen(_color(150)))

            painter.drawText(QRectF(pad, y, text_w, 14), Qt.AlignmentFlag.AlignLeft, "// FUNCTIONS")

            y += 18

            painter.setFont(_mono_font(10))

            for index, item in enumerate(brief["functions"]):

                if y + 16 > h - 28:

                    break

                reveal = _clamp((boot - 0.45 - index * 0.12) / 0.25)

                if reveal <= 0:

                    # Keep the slot so the layout below does not jump.
                    y += 20

                    continue

                painter.setPen(QPen(_color(230 * reveal, WHITE_GREEN)))

                painter.drawText(QRectF(pad, y, text_w, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"▸ {item.upper()}")

                bar_w = 34

                painter.setPen(Qt.PenStyle.NoPen)

                painter.setBrush(QBrush(_color(40)))

                painter.drawRect(QRectF(w - pad - bar_w, y + 6, bar_w, 4))

                painter.setBrush(QBrush(_color(220 * reveal)))

                painter.drawRect(QRectF(w - pad - bar_w, y + 6, bar_w * _ease_out(reveal), 4))

                y += 20

        # Data stream filling the rest of the bay.
        stream_top = y + 10

        stream_bottom = h - 34

        if stream_bottom - stream_top > 48:

            self._paint_stream(painter, pad, stream_top, text_w, stream_bottom - stream_top, now, key, flicker)

        # Footer.
        painter.setFont(_mono_font(8))

        painter.setPen(QPen(_color(110)))

        footer = "▲▼ SECTION   ◀▶ MATRIX" if not self._shown_is_preview else "PINCH OR CLICK TO OPEN"

        painter.drawText(QRectF(pad, h - 22, text_w, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, footer)

        bars = 4

        for b in range(bars):

            on = (math.sin(now * 3 + b) + 1) / 2 > 0.3

            painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(QBrush(_color(200 if on else 50)))

            bh = 3 + b * 2

            painter.drawRect(QRectF(w - pad - (bars - b) * 5, h - 12 - bh, 3, bh))

        painter.end()

    def _paint_stream(self, painter, x, top, width, height, now, key, flicker):

        painter.setPen(QPen(_color(60), 1))

        painter.drawLine(QPointF(x, top), QPointF(x + width, top))

        painter.setFont(_mono_font(9, bold=True))

        painter.setPen(QPen(_color(130)))

        painter.drawText(
            QRectF(x, top + 4, width, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "// LIVE DATA STREAM",
        )

        painter.setFont(_mono_font(9))

        row_h = 13

        area_top = top + 22

        rows = int((height - 22) / row_h)

        scroll = now * 2.2

        first = int(scroll)

        frac = scroll - first

        seed = sum(ord(c) for c in key)

        for r in range(rows):

            index = first + r

            rng = random.Random(seed * 7919 + index)

            words = " ".join(
                f"{rng.randrange(0, 0xFFFF):04X}" for _ in range(4)
            )

            line = f"{index % 0xFFF:03X}  {words}"

            ry = area_top + (r - frac) * row_h

            if ry < area_top - 1:

                continue

            fade = _clamp(min(r + 1 - frac, rows - r) / 3.0)

            hot = rng.random() < 0.12

            painter.setPen(
                QPen(
                    _color(
                        (150 if hot else 70) * fade * flicker,
                        WHITE_GREEN if hot else ACCENT,
                    )
                )
            )

            painter.drawText(
                QRectF(x, ry, width, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )

    def _paint_beam(self, painter, cx, emitter_y, top, w, boot, flicker):

        flare = 1.0 + 1.4 * (1.0 - _ease_out(boot))

        base_half = w * 0.16

        top_half = w * 0.42

        beam = QPolygonF(
            [
                QPointF(cx - base_half, emitter_y),
                QPointF(cx + base_half, emitter_y),
                QPointF(cx + top_half, top + 8),
                QPointF(cx - top_half, top + 8),
            ]
        )

        gradient = QLinearGradient(0, emitter_y, 0, top)

        gradient.setColorAt(0.0, _color(min(255, 70 * flare * flicker)))

        gradient.setColorAt(0.6, _color(18 * flare * flicker))

        gradient.setColorAt(1.0, _color(0))

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(gradient))

        painter.drawPolygon(beam)

        # Emitter rings.
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for k, alpha in ((0, 220), (1, 120), (2, 60)):

            rx = base_half + k * 9

            painter.setPen(QPen(_color(alpha * flicker, WHITE_GREEN if k == 0 else ACCENT), 1.3))

            painter.drawEllipse(QPointF(cx, emitter_y), rx, rx * 0.22)

        spin = math.degrees(self._angle * 3)

        painter.setPen(QPen(_color(230 * flicker, WHITE_GREEN), 2))

        painter.drawArc(
            QRectF(cx - base_half - 9, emitter_y - (base_half + 9) * 0.22, (base_half + 9) * 2, (base_half + 9) * 0.44),
            int(spin * 16),
            70 * 16,
        )

    def _paint_model(self, painter, key, cx, cy, scale, boot, flicker):

        lines = self._model(key)

        grow = _ease_out(boot)

        visible = max(1, int(len(lines) * _clamp(boot * 1.5)))

        ay = self._angle

        ax = -0.38 + 0.08 * math.sin(self._angle * 0.7)

        cos_y, sin_y = math.cos(ay), math.sin(ay)

        cos_x, sin_x = math.cos(ax), math.sin(ax)

        jitter = (1.0 - grow) * 10.0

        projected = []

        for line in lines[:visible]:

            points = []

            depth = 0.0

            for x, y, z in line:

                x, z = x * cos_y + z * sin_y, -x * sin_y + z * cos_y

                y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x

                f = 3.4 / (3.4 + z)

                s = scale * grow * f

                points.append(QPointF(cx + x * s, cy - y * s))

                depth += z

            depth /= max(1, len(line))

            offset = random.uniform(-jitter, jitter) if jitter > 0.5 else 0.0

            if offset:

                points = [QPointF(p.x() + offset, p.y()) for p in points]

            projected.append((depth, QPolygonF(points)))

        projected.sort(key=lambda item: -item[0])

        for depth, polygon in projected:

            near = _clamp(0.55 - depth * 0.35, 0.25, 1.0)

            painter.setPen(QPen(_color(38 * near * flicker), 4))

            painter.drawPolyline(polygon)

        for depth, polygon in projected:

            near = _clamp(0.55 - depth * 0.35, 0.25, 1.0)

            painter.setPen(QPen(_color(235 * near * flicker, WHITE_GREEN), 1.1))

            painter.drawPolyline(polygon)