"""
ui/auth_overlay.py

GLITCH secure-access terminal: a cyber-grid "hacker room" with a live
holographic body of the person at the camera.

Layers (back to front)
    perspective floor + ceiling grid that lights up under your mouse
    falling data-rain columns at both edges
    typed terminal log (reacts to the scan stages)
    projector base, light beam, orbit rings, rising particles
    HOLOGRAM of you: your camera image rebuilt as iso-lines/contours, with a
        wireframe body extruded from your own silhouette (see hologram_render)
    face tracking reticle + callouts anchored to your face
    title / status readouts / retry button, corner telemetry
    cursor crosshair + click ripples

Drop-in replacement for the previous AuthOverlay. Same public API:
    signals   retry_requested, unlock_finished
    methods   begin_session, set_stage, set_preview, set_face_status,
              show_granted, show_denied, show_lockdown,
              set_voice_level / set_factor (kept as no-ops)

set_preview accepts a QImage, QPixmap or a numpy BGR/RGBA frame.
"""

import math
import random
import time
from collections import deque
from pathlib import Path

import numpy as np

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
)

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from PySide6.QtWidgets import QWidget

from ui.hud_effects import (
    ACCENT,
    BACKGROUND,
    WHITE_GREEN,
    HudTransitionOverlay,
    _clamp,
    _color,
    _ease_out,
)

from ui.hologram_render import HologramRenderer


RED = (255, 64, 64)
AMBER = (255, 176, 32)
CYAN = (120, 255, 235)
WHITE_RED = (255, 215, 215)
WHITE_AMBER = (255, 236, 200)

RETRYABLE_STATES = ("DENIED", "WARN", "READY")

RAIN_GLYPHS = "01ABCDEF<>/\\|[]{}#$%&*+=-_;:"

LOG_FILLER = (
    "sensor.sync ........ OK",
    "mesh.integrity .... OK",
    "entropy.pool ...... OK",
    "optics.autoexp .... LOCKED",
    "tensor.cache ...... WARM",
    "bus.local ......... SECURE",
    "hash.verify ....... OK",
    "render.holo ....... ONLINE",
)

# reason (from the auth worker) -> (state, title, subtitle)
REASON_TEXT = {

    "NO_FACE": (
        "WARN",
        "NO SUBJECT DETECTED",
        "FACE NOT FOUND IN CAMERA VIEW // RETRY",
    ),

    "NO_PROFILE": (
        "WARN",
        "NO OWNER ENROLLED",
        "RUN  python tools/enroll_404.py  THEN RESTART",
    ),

    "FAULT": (
        "WARN",
        "SECURITY SUBSYSTEM FAULT",
        "ACCESS DENIED // FAIL-SAFE ENGAGED",
    ),

    "CANCELLED": (
        "WARN",
        "SCAN CANCELLED",
        "AUTHENTICATION INTERRUPTED",
    ),
}


def _frame_to_rgb(frame, mirror_arrays=True):
    """QImage / QPixmap / numpy BGR(A) frame -> contiguous RGB uint8."""

    if frame is None:

        return None

    if isinstance(frame, QPixmap):

        frame = frame.toImage()

    if isinstance(frame, QImage):

        if frame.isNull():

            return None

        image = frame.convertToFormat(QImage.Format.Format_RGB888)

        width = image.width()
        height = image.height()

        buffer = np.frombuffer(image.constBits(), dtype=np.uint8)

        array = buffer.reshape(height, image.bytesPerLine())[:, : width * 3]

        return np.ascontiguousarray(array.reshape(height, width, 3))

    if hasattr(frame, "shape"):

        array = np.asarray(frame)

        if array.ndim == 2:

            array = np.stack([array] * 3, axis=2)

        elif array.shape[2] == 4:

            array = array[:, :, :3]            # RGBA -> RGB

        else:

            array = array[:, :, ::-1]          # BGR -> RGB

        if mirror_arrays:

            array = array[:, ::-1]

        return np.ascontiguousarray(array.astype(np.uint8, copy=False))

    return None


class AuthOverlay(QWidget):

    retry_requested = Signal()
    unlock_finished = Signal()

    GRANT_HOLD_S = 2.0
    FADE_S = 0.6

    MIRROR_ARRAY_FRAMES = True

    SPRITE_INTERVAL_S = 0.066          # ~15 fps hologram refresh

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setMouseTracking(True)

        self.setCursor(Qt.CursorShape.CrossCursor)

        root = Path(__file__).resolve().parent.parent

        self._renderer = HologramRenderer(
            segmenter_model=(
                root / "data" / "auth" / "models" / "selfie_segmenter.tflite"
            ),
        )

        # ---- state ----
        self.state = "BOOT"
        self.title = "CAMERA IDENTITY SCAN"
        self.subtitle = "FACE VERIFICATION REQUIRED // VOICE BIOMETRICS DISABLED"
        self.stage_text = "SECURITY CORE // CAMERA STARTING"
        self.face_text = "WAITING"
        self.face_score = None
        self.owner = "404"

        self._state_since = time.perf_counter()

        self._lock_until = 0.0

        self._opacity = 1.0
        self._fading = False
        self._granted_at = 0.0

        # ---- hologram ----
        self._pending_frame = None
        self._have_frame = False
        self._sprite = None
        self._sprite_info = self._renderer.last_info
        self._last_sprite = 0.0
        self._reveal_start = None

        # ---- interaction ----
        self._mouse = None
        self._ripples = []
        self._retry_rect = QRectF()

        # ---- decoration ----
        self._rain = []
        self._particles = []
        self._log = deque(maxlen=10)
        self._next_filler = 0.0
        self._slices = []

        self._frame = 0
        self._last_tick = time.perf_counter()

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

        self.hide()

    # =====================================================
    # PUBLIC API (unchanged from the previous overlay)
    # =====================================================

    def begin_session(self):

        self._renderer.reset()

        self._pending_frame = None
        self._have_frame = False
        self._sprite = None
        self._reveal_start = None

        self.face_score = None
        self.face_text = "WAITING"

        self._opacity = 1.0
        self._fading = False

        self._log.clear()

        self._set_state(
            "BOOT",
            "CAMERA IDENTITY SCAN",
            "FACE VERIFICATION REQUIRED // VOICE BIOMETRICS DISABLED",
            "SECURITY CORE // CAMERA STARTING",
        )

        self._log_add("secure_boot ........ OK")
        self._log_add("mount biometric.core")

        self.show()
        self.raise_()
        self.setFocus()

        if not self._timer.isActive():

            self._last_tick = time.perf_counter()

            self._timer.start()

    def set_stage(self, stage, *args):

        text = str(stage).strip()

        if "voice" in text.lower():

            text = "FACE VERIFIED"

        if self.state in ("BOOT", "SCAN"):

            if self.state == "BOOT" and "boot" not in text.lower():

                self.state = "SCAN"

                self._state_since = time.perf_counter()

        self.stage_text = f"SECURITY CORE // {text.upper()}"

        self._log_add(text.lower().replace(" ", "_") + " ...")

    def set_preview(self, frame):

        self._pending_frame = frame

        if not self._have_frame:

            self._have_frame = True

            self._reveal_start = time.perf_counter()

            if self.state == "BOOT":

                self.state = "SCAN"

                self._state_since = time.perf_counter()

            self._log_add("optical feed ....... LIVE")

    def set_face_status(self, status, *args):

        if isinstance(status, (int, float)):

            self.face_score = _clamp(float(status))

            if self.face_score > 0.0:

                self.face_text = f"MATCH {self.face_score:.2f}"

            return

        text = str(status).strip().upper()

        if text != self.face_text:

            self._log_add(f"face_match: {text.lower()}")

        self.face_text = text

    def show_granted(self, owner="404"):

        self.owner = str(owner)

        self._set_state(
            "GRANTED",
            "IDENTITY VERIFIED",
            f"CAMERA MATCH CONFIRMED // WELCOME {self.owner}",
            "SECURITY CORE // ACCESS GRANTED",
        )

        self.face_text = "VERIFIED"

        self._granted_at = time.perf_counter()

        self._log_add(f"identity verified :: {self.owner}")
        self._log_add("unlocking glitch.exe")

    def show_denied(self, result=None):

        reason = str(getattr(result, "reason", "") or "")

        state, title, subtitle = REASON_TEXT.get(
            reason,
            (
                "DENIED",
                "UNAUTHORIZED ACCESS",
                "IDENTITY NOT VERIFIED // CAMERA MATCH FAILED",
            ),
        )

        self._set_state(
            state,
            title,
            subtitle,
            (
                "SECURITY CORE // ACCESS DENIED"
                if state == "DENIED"
                else "SECURITY CORE // STANDBY"
            ),
        )

        self.face_text = "FAILED" if state == "DENIED" else "NO RESULT"

        if state == "DENIED":

            self._log_add("ALERT: unauthorized access")
            self._log_add("snapshot archived")

        else:

            self._log_add(f"notice: {reason.lower() or 'retry'}")

    def show_lockdown(self, *args):

        seconds = 0

        if args and isinstance(args[0], (int, float)):

            seconds = int(args[0])

        self._lock_until = (
            time.perf_counter() + seconds if seconds > 0 else 0.0
        )

        self._set_state(
            "LOCKDOWN",
            "SECURITY LOCKDOWN",
            "CAMERA VERIFICATION TEMPORARILY LOCKED",
            "SECURITY CORE // LOCKDOWN",
        )

        self.face_text = "BLOCKED"

        self._log_add("ALERT: lockdown engaged")

        if not self.isVisible():

            self.show()

        self.raise_()

        if not self._timer.isActive():

            self._timer.start()

    # Voice biometrics are disabled in this build; kept for compatibility.
    def set_voice_level(self, *args):

        pass

    def set_factor(self, *args):

        pass

    # =====================================================
    # INTERNAL STATE
    # =====================================================

    def _set_state(self, state, title, subtitle, stage):

        self.state = state
        self.title = title
        self.subtitle = subtitle
        self.stage_text = stage

        self._state_since = time.perf_counter()

    def _log_add(self, text):

        self._log.append((str(text), time.perf_counter()))

    def _theme(self):

        if self.state in ("DENIED", "LOCKDOWN"):

            return RED, WHITE_RED

        if self.state == "WARN":

            return AMBER, WHITE_AMBER

        if self.state == "GRANTED":

            return CYAN, (235, 255, 250)

        return ACCENT, WHITE_GREEN

    def _ensure_decor(self, width, height):

        if not self._rain:

            for side in (-1, 1):

                for index in range(7):

                    self._rain.append(
                        {
                            "side": side,
                            "index": index,
                            "speed": random.uniform(55, 150),
                            "offset": random.uniform(0, 900),
                            "glyphs": [
                                random.choice(RAIN_GLYPHS)
                                for _ in range(16)
                            ],
                        }
                    )

        if not self._particles:

            self._particles = [
                {
                    "x": random.uniform(-1, 1),
                    "p": random.random(),
                    "speed": random.uniform(0.08, 0.28),
                    "size": random.uniform(1.2, 2.6),
                }
                for _ in range(36)
            ]

    # =====================================================
    # TICK
    # =====================================================

    def _tick(self):

        now = time.perf_counter()

        dt = min(0.1, now - self._last_tick)

        self._last_tick = now

        self._frame += 1

        alert = self.state in ("DENIED", "LOCKDOWN")

        # ---- granted: hold, fade, hand control back ----
        if self.state == "GRANTED":

            if (
                not self._fading
                and now - self._granted_at >= self.GRANT_HOLD_S
            ):

                self._fading = True

            if self._fading:

                self._opacity -= dt / self.FADE_S

                if self._opacity <= 0.0:

                    self._opacity = 0.0

                    self._timer.stop()

                    self.hide()

                    self._renderer.close()

                    self.unlock_finished.emit()

                    return

        # ---- lockdown countdown finished ----
        if (
            self.state == "LOCKDOWN"
            and self._lock_until > 0.0
            and now >= self._lock_until
        ):

            self._set_state(
                "READY",
                "LOCKDOWN LIFTED",
                "CAMERA VERIFICATION AVAILABLE",
                "SECURITY CORE // STANDBY",
            )

            self.face_text = "WAITING"

        # ---- filler terminal output ----
        if (
            self.state in ("BOOT", "SCAN")
            and now >= self._next_filler
        ):

            self._next_filler = now + random.uniform(1.6, 3.0)

            self._log_add(random.choice(LOG_FILLER))

        # ---- particles ----
        speed_scale = 3.5 if alert else 1.0

        for particle in self._particles:

            particle["p"] += particle["speed"] * dt * speed_scale

            if alert:

                particle["x"] += random.uniform(-1, 1) * dt * 2.0

            if particle["p"] > 1.0:

                particle["p"] = 0.0

                particle["x"] = random.uniform(-1, 1)

        # ---- alert glitch slices ----
        if alert and self._frame % 3 == 0:

            height = max(1, self.height())

            self._slices = [
                (
                    random.uniform(0, height),
                    random.uniform(2, 16),
                    random.uniform(-40, 40),
                )
                for _ in range(random.randint(1, 4))
            ]

        elif not alert:

            self._slices = []

        # ---- ripples ----
        self._ripples = [
            ripple
            for ripple in self._ripples
            if now - ripple[2] < 1.4
        ]

        # ---- hologram sprite ----
        if now - self._last_sprite >= self.SPRITE_INTERVAL_S:

            self._last_sprite = now

            self._refresh_sprite(now)

        self.update()

    def _refresh_sprite(self, now):

        rgb = None

        if self._pending_frame is not None:

            try:

                rgb = _frame_to_rgb(
                    self._pending_frame,
                    self.MIRROR_ARRAY_FRAMES,
                )

            except Exception:

                rgb = None

        elapsed = now - self._state_since

        tint = (57, 255, 120)

        glitch = 0.0
        flash = 0.0
        dissolve = 0.0

        if self.state in ("DENIED", "LOCKDOWN"):

            tint = RED

            glitch = 0.75 + 0.2 * math.sin(now * 9.0)

            dissolve = 0.5 * _clamp(elapsed / 1.2)

        elif self.state == "WARN":

            tint = AMBER

            glitch = 0.10

        elif self.state == "GRANTED":

            tint = CYAN

            flash = max(0.0, 1.0 - elapsed / 0.9)

        elif random.random() < 0.03:

            glitch = 0.30

        if self._reveal_start is not None:

            reveal = _ease_out((now - self._reveal_start) / 1.7)

        else:

            reveal = 1.0

        try:

            rgba = self._renderer.render(
                rgb,
                now,
                tint=tint,
                reveal=reveal,
                glitch=glitch,
                flash=flash,
                dissolve=dissolve,
            )

        except Exception:

            return

        height, width = rgba.shape[:2]

        self._sprite = QImage(
            rgba.data,
            width,
            height,
            width * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()

        self._sprite_info = self._renderer.last_info

    # =====================================================
    # INPUT
    # =====================================================

    def _try_retry(self):

        if self.state in RETRYABLE_STATES:

            self.retry_requested.emit()

    def mouseMoveEvent(self, event):

        self._mouse = event.position()

        event.accept()

    def leaveEvent(self, event):

        self._mouse = None

        super().leaveEvent(event)

    def mousePressEvent(self, event):

        point = event.position()

        if (
            self.state in RETRYABLE_STATES
            and self._retry_rect.contains(point)
        ):

            self.retry_requested.emit()

        else:

            if len(self._ripples) < 8:

                self._ripples.append(
                    (point.x(), point.y(), time.perf_counter())
                )

        event.accept()

    def mouseReleaseEvent(self, event):

        event.accept()

    def wheelEvent(self, event):

        event.accept()

    def keyPressEvent(self, event):

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):

            self._try_retry()

        event.accept()

    # =====================================================
    # PAINTING
    # =====================================================

    @staticmethod
    def _font(size, bold=False, spacing=0.0):

        font = QFont(
            "Consolas",
            size,
            QFont.Weight.Bold if bold else QFont.Weight.Normal,
        )

        if spacing:

            font.setLetterSpacing(
                QFont.SpacingType.AbsoluteSpacing,
                spacing,
            )

        return font

    def paintEvent(self, event):

        width = self.width()
        height = self.height()

        if width <= 0 or height <= 0:

            return

        self._ensure_decor(width, height)

        now = time.perf_counter()

        t = now
        e = now - self._state_since

        accent, bright = self._theme()

        alert = self.state in ("DENIED", "LOCKDOWN")

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        painter.setOpacity(_clamp(self._opacity))

        cx = width / 2

        horizon = height * 0.50

        base_y = height * 0.75

        fig_h = min(height * 0.56, width * 0.62)

        fig_w = fig_h * (HologramRenderer.W / HologramRenderer.H)

        parallax = 0.0

        if self._mouse is not None:

            parallax = (self._mouse.x() - cx) / max(1.0, width) * 18.0

        # ---------------------------------------------
        # Background
        # ---------------------------------------------

        painter.fillRect(self.rect(), _color(255, BACKGROUND))

        glow = QRadialGradient(
            QPointF(cx, base_y - fig_h * 0.45),
            max(width, height) * 0.55,
        )

        glow.setColorAt(0.0, _color(34, accent))
        glow.setColorAt(1.0, _color(0, accent))

        painter.fillRect(self.rect(), QBrush(glow))

        if alert:

            painter.fillRect(
                self.rect(),
                _color(20 + 12 * math.sin(t * 6.0), (120, 0, 0)),
            )

        self._paint_grid(painter, width, height, horizon, accent, t)

        self._paint_rain(painter, width, height, accent, bright, t)

        self._paint_log(painter, width, height, accent, bright, now)

        # ---------------------------------------------
        # Hologram stage
        # ---------------------------------------------

        self._paint_beam(painter, cx, base_y, fig_w, fig_h, accent)

        self._paint_base(painter, cx, base_y, fig_w, accent, bright, t, e)

        sprite_rect = QRectF(
            cx - fig_w / 2 + parallax,
            base_y - fig_h + 6,
            fig_w,
            fig_h,
        )

        self._paint_figure(
            painter,
            sprite_rect,
            accent,
            bright,
            t,
            e,
            alert,
        )

        self._paint_orbits(
            painter,
            cx + parallax,
            base_y,
            fig_w,
            fig_h,
            accent,
            bright,
            t,
        )

        self._paint_particles(
            painter,
            cx + parallax,
            base_y,
            fig_w,
            fig_h,
            accent,
        )

        self._paint_callouts(
            painter,
            sprite_rect,
            width,
            height,
            accent,
            bright,
            t,
        )

        # ---------------------------------------------
        # Text, status, retry
        # ---------------------------------------------

        self._paint_headline(painter, width, accent, bright, e)

        self._paint_status(painter, width, height, accent, bright, t)

        self._paint_frame(painter, width, height, accent, t)

        # ---------------------------------------------
        # Alert effects
        # ---------------------------------------------

        if alert:

            vignette = QRadialGradient(
                QPointF(cx, height / 2),
                max(width, height) * 0.7,
            )

            vignette.setColorAt(0.55, _color(0, RED))

            vignette.setColorAt(
                1.0,
                _color(100 + 60 * math.sin(t * 6.0), RED),
            )

            painter.fillRect(self.rect(), QBrush(vignette))

        for y, slice_height, dx in self._slices:

            painter.fillRect(
                QRectF(dx, y, width, slice_height),
                _color(32, RED),
            )

        # ---------------------------------------------
        # Interactive layer
        # ---------------------------------------------

        self._paint_interactive(painter, accent, bright, t)

        painter.end()

    # -----------------------------------------------------
    # GRID
    # -----------------------------------------------------

    def _paint_grid(self, painter, width, height, horizon, accent, t):

        cx = width / 2

        floor_h = height - horizon

        mouse = self._mouse

        scroll = (t * 0.22) % 1.0

        lines = 16

        near_rows = []

        # Horizontal lines (floor + mirrored ceiling).
        for index in range(lines):

            z = (index + scroll) / lines

            curve = z ** 2.1

            y_floor = horizon + floor_h * curve

            y_ceiling = horizon - horizon * curve

            floor_alpha = 14 + 70 * z

            boost = 0.0

            if mouse is not None:

                distance = abs(y_floor - mouse.y())

                if distance < 70:

                    boost = (1.0 - distance / 70.0) * 130.0

                    near_rows.append(y_floor)

            painter.setPen(QPen(_color(floor_alpha + boost, accent), 1))

            painter.drawLine(
                QPointF(0, y_floor),
                QPointF(width, y_floor),
            )

            painter.setPen(QPen(_color(8 + 34 * z, accent), 1))

            painter.drawLine(
                QPointF(0, y_ceiling),
                QPointF(width, y_ceiling),
            )

        # Vertical lines converging on the vanishing point.
        spacing = width / 9.0

        for k in range(-16, 17):

            x_bottom = cx + k * spacing * 1.5

            boost = 0.0

            if mouse is not None and mouse.y() > horizon:

                ratio = (mouse.y() - horizon) / floor_h

                x_at = cx + (x_bottom - cx) * ratio

                distance = abs(x_at - mouse.x())

                if distance < 90:

                    boost = (1.0 - distance / 90.0) * 120.0

            painter.setPen(QPen(_color(22 + boost, accent), 1))

            painter.drawLine(
                QPointF(cx, horizon),
                QPointF(x_bottom, height),
            )

            painter.setPen(QPen(_color(12, accent), 1))

            painter.drawLine(
                QPointF(cx, horizon),
                QPointF(cx + (x_bottom - cx), 0),
            )

            # Lit nodes where the highlighted rows cross this line.
            if boost > 0.0 and near_rows:

                for y in near_rows:

                    ratio = (y - horizon) / floor_h

                    node_x = cx + (x_bottom - cx) * ratio

                    painter.setPen(Qt.PenStyle.NoPen)

                    painter.setBrush(QBrush(_color(150 + boost, accent)))

                    painter.drawEllipse(QPointF(node_x, y), 2.6, 2.6)

        # Horizon glow.
        band = QLinearGradient(0, horizon - 60, 0, horizon + 60)

        band.setColorAt(0.0, _color(0, accent))
        band.setColorAt(0.5, _color(44, accent))
        band.setColorAt(1.0, _color(0, accent))

        painter.fillRect(
            QRectF(0, horizon - 60, width, 120),
            QBrush(band),
        )

        painter.setPen(QPen(_color(130, accent), 1))

        painter.drawLine(
            QPointF(0, horizon),
            QPointF(width, horizon),
        )

    # -----------------------------------------------------
    # DATA RAIN
    # -----------------------------------------------------

    def _paint_rain(self, painter, width, height, accent, bright, t):

        painter.setFont(self._font(9))

        step = 14

        for column in self._rain:

            if column["side"] < 0:

                x = 14 + column["index"] * 13

            else:

                x = width - 22 - column["index"] * 13

            glyphs = column["glyphs"]

            span = height + len(glyphs) * step

            head = (t * column["speed"] + column["offset"]) % span

            if random.random() < 0.35:

                glyphs[random.randrange(len(glyphs))] = random.choice(
                    RAIN_GLYPHS
                )

            for k, glyph in enumerate(glyphs):

                y = head - k * step

                if y < -step or y > height + step:

                    continue

                if k == 0:

                    painter.setPen(_color(230, bright))

                else:

                    painter.setPen(
                        _color(150 * (1.0 - k / len(glyphs)) + 12, accent)
                    )

                painter.drawText(QPointF(x, y), glyph)

    # -----------------------------------------------------
    # TERMINAL LOG
    # -----------------------------------------------------

    def _paint_log(self, painter, width, height, accent, bright, now):

        left = 110

        top = height * 0.24

        line_h = 16

        painter.setFont(self._font(9))

        entries = list(self._log)

        for index, (text, started) in enumerate(entries):

            y = top + index * line_h

            shown = int((now - started) * 70)

            visible = text[: max(0, shown)]

            age = len(entries) - 1 - index

            alpha = max(40, 220 - age * 22)

            painter.setPen(_color(alpha, accent))

            line = "> " + visible

            painter.drawText(QPointF(left, y), line)

            if index == len(entries) - 1 and int(now * 2) % 2 == 0:

                painter.fillRect(
                    QRectF(
                        left + 7.2 * len(line) + 2,
                        y - 9,
                        6,
                        11,
                    ),
                    _color(200, bright),
                )

    # -----------------------------------------------------
    # PROJECTOR BASE, BEAM, ORBITS, PARTICLES
    # -----------------------------------------------------

    def _paint_beam(self, painter, cx, base_y, fig_w, fig_h, accent):

        top_y = base_y - fig_h

        half_bottom = fig_w * 0.66

        half_top = fig_w * 0.40

        gradient = QLinearGradient(0, base_y, 0, top_y)

        gradient.setColorAt(0.0, _color(46, accent))
        gradient.setColorAt(1.0, _color(0, accent))

        polygon = QPolygonF(
            [
                QPointF(cx - half_bottom, base_y),
                QPointF(cx + half_bottom, base_y),
                QPointF(cx + half_top, top_y),
                QPointF(cx - half_top, top_y),
            ]
        )

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(gradient))

        painter.drawPolygon(polygon)

        painter.setPen(QPen(_color(46, accent), 1))

        painter.drawLine(
            QPointF(cx - half_bottom, base_y),
            QPointF(cx - half_top, top_y),
        )

        painter.drawLine(
            QPointF(cx + half_bottom, base_y),
            QPointF(cx + half_top, top_y),
        )

    def _paint_base(
        self,
        painter,
        cx,
        base_y,
        fig_w,
        accent,
        bright,
        t,
        e,
    ):

        rx = fig_w * 0.72

        ry = rx * 0.22

        painter.save()

        painter.translate(cx, base_y)

        glow = QRadialGradient(QPointF(0, 0), rx * 1.2)

        glow.setColorAt(0.0, _color(80, accent))
        glow.setColorAt(1.0, _color(0, accent))

        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QBrush(glow))

        painter.drawEllipse(QPointF(0, 0), rx * 1.2, ry * 1.2)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        for scale, alpha, pen_width in (
            (1.0, 230, 2),
            (0.82, 130, 1),
            (0.58, 100, 1),
        ):

            painter.setPen(QPen(_color(alpha, accent), pen_width))

            painter.drawEllipse(
                QPointF(0, 0),
                rx * scale,
                ry * scale,
            )

        # Rotating tick marks on the outer ring.
        for index in range(60):

            angle = index * (2.0 * math.pi / 60.0) + t * 0.5

            long = index % 5 == 0

            inner = 1.0 if long else 1.0

            x1 = rx * math.cos(angle)
            y1 = ry * math.sin(angle)

            x2 = rx * (1.07 if long else 1.04) * math.cos(angle)
            y2 = ry * (1.07 if long else 1.04) * math.sin(angle)

            painter.setPen(
                QPen(_color(190 if long else 100, accent), 1)
            )

            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Sweeping arcs.
        painter.setPen(QPen(_color(220, bright), 3))

        for k in range(3):

            start = (-t * 55.0 + k * 120.0) % 360.0

            painter.drawArc(
                QRectF(-rx * 0.91, -ry * 0.91, rx * 1.82, ry * 1.82),
                int(start * 16),
                44 * 16,
            )

        painter.restore()

        # Shockwave on grant.
        if self.state == "GRANTED":

            grow = 1.0 + e * 2.4

            fade = 1.0 - _clamp(e / 1.3)

            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.setPen(QPen(_color(210 * fade, bright), 3))

            painter.drawEllipse(
                QPointF(cx, base_y),
                rx * grow,
                ry * grow,
            )

    def _paint_orbits(
        self,
        painter,
        cx,
        base_y,
        fig_w,
        fig_h,
        accent,
        bright,
        t,
    ):

        painter.setBrush(Qt.BrushStyle.NoBrush)

        for level, speed, scale in (
            (0.30, 38.0, 0.64),
            (0.62, -52.0, 0.58),
            (0.90, 70.0, 0.44),
        ):

            y = base_y - fig_h * level

            rx = fig_w * scale

            ry = rx * 0.17

            painter.setPen(QPen(_color(40, accent), 1))

            painter.drawEllipse(QPointF(cx, y), rx, ry)

            painter.setPen(QPen(_color(210, bright), 2))

            start = (t * speed) % 360.0

            painter.drawArc(
                QRectF(cx - rx, y - ry, rx * 2, ry * 2),
                int(start * 16),
                54 * 16,
            )

            angle = math.radians(start)

            painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(QBrush(_color(240, bright)))

            painter.drawEllipse(
                QPointF(
                    cx + rx * math.cos(-angle),
                    y + ry * math.sin(-angle),
                ),
                3.0,
                3.0,
            )

            painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_particles(
        self,
        painter,
        cx,
        base_y,
        fig_w,
        fig_h,
        accent,
    ):

        painter.setPen(Qt.PenStyle.NoPen)

        for particle in self._particles:

            progress = particle["p"]

            x = cx + particle["x"] * fig_w * 0.55

            y = base_y - progress * fig_h

            painter.setBrush(
                QBrush(_color(190 * (1.0 - progress), accent))
            )

            painter.drawEllipse(
                QPointF(x, y),
                particle["size"],
                particle["size"],
            )

    # -----------------------------------------------------
    # FIGURE
    # -----------------------------------------------------

    def _paint_figure(
        self,
        painter,
        rect,
        accent,
        bright,
        t,
        e,
        alert,
    ):

        if self._sprite is None:

            return

        flicker = 0.93 + 0.07 * math.sin(t * 23.0)

        if alert:

            flicker = 0.55 + 0.45 * random.random()

        if alert:

            # Red chromatic ghosts.
            painter.setOpacity(_clamp(self._opacity) * 0.30)

            painter.drawImage(rect.translated(-7, 0), self._sprite)

            painter.drawImage(rect.translated(7, 0), self._sprite)

        painter.setOpacity(_clamp(self._opacity) * flicker)

        painter.drawImage(rect, self._sprite)

        painter.setOpacity(_clamp(self._opacity))

        # Tracking reticle on the face.
        face = self._sprite_info.get("face_box")

        if face is not None and self.state in ("SCAN", "BOOT", "GRANTED"):

            sx = rect.width() / HologramRenderer.W
            sy = rect.height() / HologramRenderer.H

            box = QRectF(
                rect.left() + face[0] * sx,
                rect.top() + face[1] * sy,
                face[2] * sx,
                face[3] * sy,
            )

            pad = 6 + 3 * math.sin(t * 4.0)

            box.adjust(-pad, -pad, pad, pad)

            arm = max(8.0, min(box.width(), box.height()) * 0.22)

            painter.setPen(QPen(_color(240, bright), 2))

            for (x, y, dx, dy) in (
                (box.left(), box.top(), 1, 1),
                (box.right(), box.top(), -1, 1),
                (box.left(), box.bottom(), 1, -1),
                (box.right(), box.bottom(), -1, -1),
            ):

                painter.drawLine(
                    QPointF(x, y),
                    QPointF(x + dx * arm, y),
                )

                painter.drawLine(
                    QPointF(x, y),
                    QPointF(x, y + dy * arm),
                )

            painter.setFont(self._font(8, True, 1))

            painter.drawText(
                QPointF(box.left(), box.top() - 6),
                "TRACKING",
            )

    # -----------------------------------------------------
    # CALLOUTS
    # -----------------------------------------------------

    def _callout(
        self,
        painter,
        anchor,
        box,
        title,
        value,
        accent,
        bright,
    ):

        elbow = QPointF(box.left() - 22, box.center().y())

        painter.setPen(QPen(_color(110, accent), 1))

        painter.drawLine(anchor, elbow)

        painter.drawLine(elbow, QPointF(box.left(), box.center().y()))

        painter.setBrush(QBrush(_color(220, bright)))

        painter.setPen(Qt.PenStyle.NoPen)

        painter.drawEllipse(anchor, 3.0, 3.0)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.fillRect(box, _color(70, BACKGROUND))

        painter.setPen(QPen(_color(170, accent), 1))

        arm = 9

        for (x, y, dx, dy) in (
            (box.left(), box.top(), 1, 1),
            (box.right(), box.top(), -1, 1),
            (box.left(), box.bottom(), 1, -1),
            (box.right(), box.bottom(), -1, -1),
        ):

            painter.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))

            painter.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))

        painter.setFont(self._font(8, True, 2))

        painter.setPen(_color(230, bright))

        painter.drawText(
            QPointF(box.left() + 10, box.top() + 17),
            title,
        )

        painter.setFont(self._font(9))

        painter.setPen(_color(190, accent))

        painter.drawText(
            QPointF(box.left() + 10, box.top() + 34),
            value,
        )

    def _paint_callouts(
        self,
        painter,
        rect,
        width,
        height,
        accent,
        bright,
        t,
    ):

        if self._sprite is None:

            return

        info = self._sprite_info

        sx = rect.width() / HologramRenderer.W
        sy = rect.height() / HologramRenderer.H

        left = rect.right() + 64

        # Shrink the panels on narrow windows; hide them if there is no room.
        box_w = min(230.0, width - 110.0 - left)

        if box_w < 150.0:

            return

        face = info.get("face_box")

        if face is not None:

            face_anchor = QPointF(
                rect.left() + (face[0] + face[2]) * sx,
                rect.top() + (face[1] + face[3] * 0.4) * sy,
            )

        else:

            face_anchor = QPointF(
                rect.center().x() + rect.width() * 0.14,
                rect.top() + rect.height() * 0.18,
            )

        shoulder = info.get("shoulder_px", 0.7 * HologramRenderer.W)

        body_anchor = QPointF(
            rect.left() + (info.get("body_cx", 170) + shoulder / 2) * sx,
            rect.top() + 372 * sy,
        )

        match_anchor = QPointF(
            rect.center().x() + rect.width() * 0.18,
            rect.top() + 440 * sy,
        )

        top = rect.top() + 6

        self._callout(
            painter,
            face_anchor,
            QRectF(left, top, box_w, 44),
            "FACIAL MESH",
            f"SILHOUETTE // {info.get('mode', 'ESTIMATED')}",
            accent,
            bright,
        )

        self._callout(
            painter,
            body_anchor,
            QRectF(left, top + 78, box_w, 44),
            "BODY EXTRUSION",
            f"SHOULDER SPAN // {shoulder / HologramRenderer.W:.2f}",
            accent,
            bright,
        )

        self._callout(
            painter,
            match_anchor,
            QRectF(left, top + 156, box_w, 44),
            "BIOMETRIC MATCH",
            self.face_text[:26],
            accent,
            bright,
        )

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    def _paint_headline(self, painter, width, accent, bright, e):

        painter.setFont(self._font(9, False, 3))

        painter.setPen(_color(150, accent))

        painter.drawText(
            QRectF(0, 40, width, 18),
            Qt.AlignmentFlag.AlignCenter,
            "// SECURITY ACCESS",
        )

        big = self.state in ("GRANTED", "DENIED", "LOCKDOWN")

        painter.setFont(self._font(26 if big else 22, True, 7))

        painter.setPen(_color(255, bright))

        title = HudTransitionOverlay._decode(
            self.title,
            _clamp(e / 1.1),
        )

        painter.drawText(
            QRectF(0, 58, width, 44),
            Qt.AlignmentFlag.AlignCenter,
            title,
        )

        underline = width * 0.30 * _ease_out(e / 0.6)

        painter.setPen(QPen(_color(210, accent), 2))

        painter.drawLine(
            QPointF(width / 2 - underline / 2, 106),
            QPointF(width / 2 + underline / 2, 106),
        )

        painter.setFont(self._font(10, False, 2))

        painter.setPen(_color(200, accent))

        painter.drawText(
            QRectF(0, 112, width, 20),
            Qt.AlignmentFlag.AlignCenter,
            HudTransitionOverlay._decode(
                self.subtitle,
                _clamp(e / 1.1),
                0.10,
            ),
        )

    def _paint_status(self, painter, width, height, accent, bright, t):

        cx = width / 2

        painter.setFont(self._font(11, True, 3))

        painter.setPen(_color(235, accent))

        painter.drawText(
            QRectF(0, height - 128, width, 20),
            Qt.AlignmentFlag.AlignCenter,
            self.stage_text,
        )

        painter.setFont(self._font(10, False, 2))

        painter.setPen(_color(200, bright))

        painter.drawText(
            QRectF(0, height - 104, width, 18),
            Qt.AlignmentFlag.AlignCenter,
            f"FACE MATCH // {self.face_text}",
        )

        # Progress / score bar.
        bar = QRectF(cx - 150, height - 80, 300, 5)

        painter.fillRect(bar, _color(40, accent))

        if self.state in ("BOOT", "SCAN") and self.face_score is None:

            sweep = (math.sin(t * 3.0) + 1.0) / 2.0

            painter.fillRect(
                QRectF(bar.left() + sweep * 220, bar.top(), 80, 5),
                _color(230, accent),
            )

        else:

            fill = (
                self.face_score
                if self.face_score is not None
                else (1.0 if self.state == "GRANTED" else 0.0)
            )

            painter.fillRect(
                QRectF(
                    bar.left(),
                    bar.top(),
                    bar.width() * _clamp(fill),
                    5,
                ),
                _color(230, accent),
            )

        painter.setPen(QPen(_color(110, accent), 1))

        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRect(bar)

        # Retry button / lockdown countdown.
        self._retry_rect = QRectF()

        if self.state in RETRYABLE_STATES:

            rect = QRectF(cx - 140, height - 64, 280, 34)

            self._retry_rect = rect

            hover = (
                self._mouse is not None
                and rect.contains(self._mouse)
            )

            painter.fillRect(
                rect,
                _color(70 if hover else 28, accent),
            )

            painter.setPen(QPen(_color(240 if hover else 170, accent), 2))

            painter.drawRect(rect)

            blink = 255 if int(t * 2) % 2 == 0 or hover else 190

            painter.setFont(self._font(11, True, 3))

            painter.setPen(_color(blink, bright))

            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "RETRY CAMERA SCAN //",
            )

        elif self.state == "LOCKDOWN":

            if self._lock_until > 0.0:

                remaining = max(
                    0,
                    int(math.ceil(self._lock_until - time.perf_counter())),
                )

                text = (
                    f"LOCKDOWN  //  RETRY IN "
                    f"{remaining // 60:02d}:{remaining % 60:02d}"
                )

            else:

                text = "LOCKDOWN  //  VERIFICATION BLOCKED"

            painter.setFont(self._font(11, True, 3))

            painter.setPen(_color(240, accent))

            painter.drawText(
                QRectF(0, height - 66, width, 30),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )

    def _paint_frame(self, painter, width, height, accent, t):

        inset = 20

        arm = 38

        painter.setPen(QPen(_color(200, accent), 2))

        for (x, y, dx, dy) in (
            (inset, inset, 1, 1),
            (width - inset, inset, -1, 1),
            (inset, height - inset, 1, -1),
            (width - inset, height - inset, -1, -1),
        ):

            painter.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))

            painter.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))

        painter.setFont(self._font(8, False, 2))

        painter.setPen(_color(150, accent))

        painter.drawText(
            QPointF(inset + 12, inset + 24),
            "GLITCH.EXE // SECURE ACCESS TERMINAL",
        )

        painter.drawText(
            QRectF(width - 300 - inset - 12, inset + 10, 300, 20),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
            time.strftime("%H:%M:%S"),
        )

        painter.drawText(
            QPointF(inset + 12, height - inset - 14),
            "IDENT: OWNER 404 // BIOMETRIC DATA: LOCAL ONLY",
        )

        painter.drawText(
            QRectF(
                width - 320 - inset - 12,
                height - inset - 28,
                320,
                20,
            ),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
            f"HOLO.RENDER // {self._sprite_info.get('mode', 'ESTIMATED')}",
        )

    # -----------------------------------------------------
    # INTERACTIVE LAYER
    # -----------------------------------------------------

    def _paint_interactive(self, painter, accent, bright, t):

        now = time.perf_counter()

        painter.setBrush(Qt.BrushStyle.NoBrush)

        for x, y, started in self._ripples:

            age = (now - started) / 1.4

            radius = 8 + 130 * _ease_out(age)

            fade = 1.0 - _clamp(age)

            painter.setPen(QPen(_color(220 * fade, bright), 2))

            painter.drawEllipse(QPointF(x, y), radius, radius * 0.55)

            painter.setPen(QPen(_color(110 * fade, accent), 1))

            painter.drawEllipse(
                QPointF(x, y),
                radius * 0.65,
                radius * 0.36,
            )

        if self._mouse is None:

            return

        mx = self._mouse.x()
        my = self._mouse.y()

        painter.setPen(QPen(_color(210, bright), 1))

        painter.drawEllipse(QPointF(mx, my), 11, 11)

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):

            painter.drawLine(
                QPointF(mx + dx * 15, my + dy * 15),
                QPointF(mx + dx * 24, my + dy * 24),
            )

        painter.setFont(self._font(8))

        painter.setPen(_color(170, accent))

        painter.drawText(
            QPointF(mx + 18, my - 14),
            f"X:{int(mx):04d}  Y:{int(my):04d}",
        )