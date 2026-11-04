"""
ui/sports_holo_page.py

GLITCH Sports Nexus: a holographic team-intel deck.

For the selected team it shows
  * a rotating holographic emblem in the team's colours: a wireframe
    football or basketball on a projector beam, the team code on a
    hex plate, a win/loss orbit ring and the last five results
    orbiting as W/L beacons
  * record, standing, home/away splits, points for/against, streak
  * next game with a live countdown, venue and broadcast
  * recent results + upcoming schedule
  * injury report (status colour-coded)
  * statistical leaders

Switch teams with the tabs (mouse or finger pinch), or swipe left /
right on this page. The emblem is an original design built from the
team's colours and code, not a recreation of any team logo.
"""

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)

from PySide6.QtWidgets import QPushButton, QWidget

from services.sports_service import format_game_time, seconds_until


GREEN = QColor(57, 255, 120)
PALE = QColor(200, 255, 220)
DARK = QColor(2, 8, 6)


def _font(px, bold=False):

    font = QFont("Consolas")

    font.setStyleHint(QFont.StyleHint.Monospace)

    font.setPixelSize(max(7, int(px)))

    font.setBold(bold)

    return font


def _qcolor(hex_value, fallback=GREEN):

    try:

        value = str(hex_value).lstrip("#")

        return QColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))

    except Exception:

        return QColor(fallback)


def _holo(color, min_value=0.80, max_sat=0.85):

    """Make a team colour read as a glowing hologram on black."""

    color = QColor(color)

    h, s, v, _ = color.getHsvF()

    if h < 0:

        h = 0.38

    return QColor.fromHsvF(h, min(s, max_sat), max(v, min_value), 1.0)


def _alpha(color, alpha):

    c = QColor(color)

    c.setAlpha(max(0, min(255, int(alpha))))

    return c


def _ease(t):

    t = max(0.0, min(1.0, t))

    return 1.0 - (1.0 - t) ** 3


# ---------------------------------------------------------
# Team themes
# ---------------------------------------------------------
#
# Each team gets a full colour scheme tuned for contrast: a very dark
# background in the team's hue, a bright accent for lines/labels, a
# second accent, and near-white text with a hint of the team colour.
# The favourites are hand-tuned; any other team is derived from the
# colours ESPN reports.

THEMES = {
    "JAX": {
        "bg": "#010f16",       # deep jaguars teal-blue
        "mid": "#03303f",
        "accent": "#19c6ee",   # bright teal
        "accent2": "#e8b730",  # gold
        "text": "#e4f9ff",
        "ball": "football",
    },
    "BOS": {
        "bg": "#01110a",       # deep celtic green
        "mid": "#04371d",
        "accent": "#2fe57d",   # bright kelly green
        "accent2": "#e6c46e",  # gold
        "text": "#ebfff2",
        "ball": "basketball",
    },
    "NE": {
        "bg": "#020a1c",       # deep navy
        "mid": "#0b2252",
        "accent": "#4f8fff",   # bright navy blue
        "accent2": "#ff3d52",  # patriots red
        "text": "#e9eff8",     # silver-white
        "ball": "football",
    },
}


def team_theme(key, data=None):

    """Colour scheme for a team as QColors."""

    data = data or {}

    preset = THEMES.get(key)

    if preset is None:

        primary = QColor(_qcolor(data.get("color"), GREEN))

        h, s, v, _ = primary.getHsvF()

        if h < 0:

            h = 0.38

        alternate = _holo(_qcolor(data.get("alt_color"), PALE), 0.88, 0.7)

        preset = {
            "bg": QColor.fromHsvF(h, min(1.0, s * 0.9 + 0.1), 0.07).name(),
            "mid": QColor.fromHsvF(h, min(1.0, s * 0.9 + 0.1), 0.22).name(),
            "accent": QColor.fromHsvF(h, min(s, 0.8), 0.95).name(),
            "accent2": alternate.name(),
            "text": QColor.fromHsvF(h, 0.08, 0.98).name(),
            "ball": "basketball" if data.get("sport") == "basketball" else "football",
        }

    return {
        name: (QColor(value) if name != "ball" else value)
        for name, value in preset.items()
    }


# ---------------------------------------------------------
# Wireframe balls
# ---------------------------------------------------------

def _football_model():

    """Pointed (lemon-shaped) ball, long axis = x. Returns
    [(points, kind)] where kind is 'seam' (bright) or 'mesh' (faint)."""

    lines = []

    a, b = 1.3, 0.72

    def radius(x):

        return b * max(0.0, 1 - (x / a) ** 2) ** 0.82

    # Faint cross-section rings give it holographic volume.
    for k in range(-5, 6):

        x = a * k / 6.0

        r = radius(x)

        lines.append(
            ([(x, r * math.cos(t * math.pi / 20), r * math.sin(t * math.pi / 20)) for t in range(41)], "mesh")
        )

    # Four panel seams running tip to tip.
    for j in range(4):

        phi = j * math.pi / 2 + math.pi / 4

        seam = []

        for i in range(49):

            x = -a + 2 * a * i / 48

            r = radius(x)

            seam.append((x, r * math.cos(phi), r * math.sin(phi)))

        lines.append((seam, "seam"))

    # Laces on top (between two seams).
    top = math.pi / 2

    lace_r = lambda x: radius(x) * 1.03

    lines.append(([(x / 20.0, lace_r(x / 20.0) * math.sin(top), lace_r(x / 20.0) * math.cos(top)) for x in range(-8, 9)], "seam"))

    for k in range(-4, 5):

        x = k * 0.085

        r = lace_r(x)

        lines.append(([(x, r * math.cos(0.17), r * math.sin(0.17)), (x, r, 0.0), (x, r * math.cos(0.17), -r * math.sin(0.17))], "seam"))

    return lines


def _basketball_model():

    """Classic 8-line basketball: equator, one great circle and two
    curved side seams, plus a faint lat/long mesh."""

    lines = []

    def circle(axis, offset=0.0, radius=1.0, n=56):

        points = []

        for i in range(n + 1):

            t = 2 * math.pi * i / n

            u, v = radius * math.cos(t), radius * math.sin(t)

            if axis == "y":

                points.append((u, offset, v))

            elif axis == "x":

                points.append((offset, u, v))

            else:

                points.append((u, v, offset))

        return points

    for lat in (-0.82, -0.55, -0.28, 0.28, 0.55, 0.82):

        lines.append((circle("y", lat, math.sqrt(1 - lat * lat), 40), "mesh"))

    for j in range(6):

        phi = j * math.pi / 6

        lines.append(
            ([(math.cos(t) * math.cos(phi), math.sin(t), math.cos(t) * math.sin(phi)) for t in [i * math.pi / 20 for i in range(41)]], "mesh")
        )

    lines.append((circle("y"), "seam"))

    lines.append((circle("x"), "seam"))

    for side in (-1, 1):

        seam = []

        for i in range(65):

            t = 2 * math.pi * i / 64

            y, z = math.sin(t), math.cos(t)

            x = side * 0.62 * math.cos(t) ** 2

            norm = math.sqrt(x * x + y * y + z * z) or 1

            seam.append((x / norm, y / norm, z / norm))

        lines.append((seam, "seam"))

    return lines


MODELS = {
    "football": _football_model(),
    "basketball": _basketball_model(),
}


# ---------------------------------------------------------
# Team tab
# ---------------------------------------------------------

class TeamTab(QPushButton):

    def __init__(self, key, label, league, parent=None):

        super().__init__(label, parent)

        self.team_key = key

        self.league = league

        self.color = GREEN

        self.ink = PALE

        self.active = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setFlat(True)

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        color = self.color

        glow = 1.0 if self.active else (0.55 if self.underMouse() else 0.25)

        cut = 8

        frame = QPolygonF(
            [
                QPointF(cut, 1), QPointF(w - 1, 1), QPointF(w - 1, h - cut),
                QPointF(w - cut, h - 1), QPointF(1, h - 1), QPointF(1, cut),
            ]
        )

        painter.setBrush(QBrush(_alpha(color, 25 + 60 * glow)))

        painter.setPen(QPen(_alpha(color, 90 + 160 * glow), 1.2))

        painter.drawPolygon(frame)

        painter.setPen(_alpha(self.ink if self.active else color, 150 + 105 * glow))

        painter.setFont(_font(h * 0.36, bold=True))

        painter.drawText(QRectF(0, 0, w, h * 0.68), Qt.AlignmentFlag.AlignCenter, self.text())

        painter.setFont(_font(h * 0.2))

        painter.setPen(_alpha(color, 120 + 100 * glow))

        painter.drawText(QRectF(0, h * 0.58, w, h * 0.38), Qt.AlignmentFlag.AlignCenter, self.league)

        if self.active:

            painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(QBrush(_alpha(self.ink, 230)))

            painter.drawRect(QRectF(w * 0.25, h - 3, w * 0.5, 2))

        painter.end()


# ---------------------------------------------------------
# The page
# ---------------------------------------------------------

class SportsHoloPage(QWidget):

    team_changed = Signal(str)

    SWITCH_S = 0.85

    def __init__(self, sports_service, parent=None):

        super().__init__(parent)

        self.service = sports_service

        self.keys = sports_service.team_keys()

        self.current = self.keys[0] if self.keys else None

        self.status = "STANDBY"

        self._switch_start = time.perf_counter()

        self._angle = 0.0

        self._static = None

        self._static_key = None

        self._ink = PALE

        self._bg = DARK

        self.tabs = {}

        for key in self.keys:

            config = sports_service.team_config(key)

            tab = TeamTab(key, key, config.get("league", "").upper(), self)

            tab.clicked.connect(lambda checked=False, k=key: self.select_team(k))

            self.tabs[key] = tab

        self.sync_button = QPushButton("SYNC", self)

        self.sync_button.setObjectName("sports_sync")

        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.sync_button.setStyleSheet(
            "QPushButton { background: rgba(0,18,10,90); color: #39ff78;"
            " border: 1px solid rgba(57,255,120,120); font: bold 10px Consolas; }"
            "QPushButton:hover { background: rgba(57,255,120,60); }"
        )

        self.sync_button.clicked.connect(lambda: self.service.refresh(force=True))

        self.service.team_updated.connect(self._on_team_updated)

        self.service.status_changed.connect(self._on_status)

        self._timer = QTimer(self)

        self._timer.setInterval(33)

        self._timer.timeout.connect(self._tick)

        self._refresh_tab_colors()

        self._mark_active()

    # =====================================================
    # PUBLIC
    # =====================================================

    def select_team(self, key):

        if key not in self.keys or key == self.current:

            return

        self.current = key

        self._switch_start = time.perf_counter()

        self._static = None

        self._mark_active()

        self.team_changed.emit(key)

        self.update()


    def next_team(self, step=1):

        if not self.keys:

            return

        index = self.keys.index(self.current) if self.current in self.keys else 0

        self.select_team(self.keys[(index + step) % len(self.keys)])


    def current_team_name(self):

        data = self.service.get(self.current) or {}

        config = self.service.team_config(self.current) or {}

        return data.get("name") or config.get("name") or self.current or ""

    # =====================================================
    # QT EVENTS
    # =====================================================

    def showEvent(self, event):

        self._timer.start()

        self._switch_start = time.perf_counter()

        self.service.refresh()

        super().showEvent(event)


    def hideEvent(self, event):

        self._timer.stop()

        super().hideEvent(event)


    def resizeEvent(self, event):

        super().resizeEvent(event)

        self._layout_tabs()

        self._static = None


    def _tick(self):

        self._angle += 0.022

        self.update()


    def _on_team_updated(self, key, data):

        self._refresh_tab_colors()

        if key == self.current:

            self._static = None

            self.update()


    def _on_status(self, text):

        self.status = text

        self._static = None

        self.update()

    # =====================================================
    # HELPERS
    # =====================================================

    def _team(self):

        return self.service.get(self.current) or {}


    def theme(self, key=None):

        key = key or self.current

        return team_theme(key, self.service.get(key) or {})


    def _colors(self):

        theme = self.theme()

        self._ink = theme["text"]

        self._bg = theme["bg"]

        return theme["accent"], theme["accent2"]


    def _refresh_tab_colors(self):

        for key, tab in self.tabs.items():

            theme = self.theme(key)

            tab.color = theme["accent"]

            tab.ink = theme["text"]

            tab.update()


    def _mark_active(self):

        for key, tab in self.tabs.items():

            tab.active = key == self.current

            tab.update()


    def _layout_tabs(self):

        tab_w = 74

        tab_h = 40

        x = self.width() - 12 - 56 - 10 - len(self.tabs) * (tab_w + 8)

        for key in self.keys:

            self.tabs[key].setGeometry(int(x), 6, tab_w, tab_h)

            x += tab_w + 8

        self.sync_button.setGeometry(self.width() - 12 - 56, 14, 56, 24)


    def _geometry(self):

        w, h = self.width(), self.height()

        top = 54

        body_h = h - top - 8

        left_w = max(220, min(w * 0.36, 360))

        holo_h = min(left_w, body_h * 0.58)

        return {
            "w": w,
            "h": h,
            "top": top,
            "body_h": body_h,
            "left_w": left_w,
            "holo": QRectF(8, top, left_w - 8, holo_h),
            "record": QRectF(8, top + holo_h + 8, left_w - 8, body_h - holo_h - 8),
            "right_x": left_w + 14,
        }

    # =====================================================
    # PAINT
    # =====================================================

    def paintEvent(self, event):

        if self.width() < 300 or self.height() < 260:

            return

        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        geo = self._geometry()

        primary, alternate = self._colors()

        reveal = _ease((time.perf_counter() - self._switch_start) / self.SWITCH_S)

        key = (self.current, self.width(), self.height(), self.status, self._team().get("updated_at"))

        if self._static is None or self._static_key != key:

            self._static = self._render_static(geo, primary, alternate)

            self._static_key = key

        painter.setOpacity(reveal)

        painter.drawPixmap(int((1 - reveal) * 24), 0, self._static)

        painter.setOpacity(1.0)

        self._paint_hologram(painter, geo["holo"], primary, alternate, reveal)

        self._paint_countdown(painter, geo, primary, reveal)

        # Scan line sweeping the whole deck during a team switch.
        if reveal < 1.0:

            y = geo["top"] + reveal * geo["body_h"]

            painter.setPen(QPen(_alpha(primary, 220 * (1 - reveal)), 2))

            painter.drawLine(QPointF(0, y), QPointF(self.width(), y))

        painter.end()

    # -----------------------------------------------------

    def _render_static(self, geo, primary, alternate):

        pixmap = QPixmap(self.width(), self.height())

        pixmap.fill(Qt.GlobalColor.transparent)

        p = QPainter(pixmap)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        data = self._team()

        config = self.service.team_config(self.current) or {}

        # Header.
        p.setFont(_font(11, bold=True))

        p.setPen(_alpha(primary, 200))

        p.drawText(QRectF(10, 6, 400, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "// SPORTS NEXUS")

        p.setFont(_font(20, bold=True))

        p.setPen(_alpha(self._ink, 250))

        name = (data.get("name") or config.get("name") or self.current or "").upper()

        p.drawText(QRectF(10, 22, geo["w"] * 0.6, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        updated = data.get("updated_at")

        age = f"SYNCED {int((time.time() - updated) / 60)} MIN AGO" if updated else "AWAITING UPLINK"

        p.setFont(_font(9))

        p.setPen(_alpha(primary, 200))

        p.drawText(
            QRectF(geo["w"] * 0.6 - 150, 6, 140, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self.status} // {age}",
        )

        self._paint_record(p, geo["record"], data, primary, alternate)

        rx = geo["right_x"]

        rw = geo["w"] - rx - 8

        top = geo["top"]

        next_h = 88

        leaders_h = 84

        mid_h = geo["body_h"] - next_h - leaders_h - 16

        self._paint_next_game(p, QRectF(rx, top, rw, next_h), data, primary)

        half = (rw - 8) / 2

        self._paint_schedule(p, QRectF(rx, top + next_h + 8, half, mid_h), data, primary)

        self._paint_injuries(p, QRectF(rx + half + 8, top + next_h + 8, half, mid_h), data, primary)

        self._paint_leaders(p, QRectF(rx, top + next_h + mid_h + 16, rw, leaders_h), data, primary, alternate)

        p.end()

        return pixmap

    # -----------------------------------------------------

    def _panel(self, p, rect, title, color):

        p.setPen(Qt.PenStyle.NoPen)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())

        gradient.setColorAt(0.0, _alpha(color, 34))

        gradient.setColorAt(0.25, _alpha(self._bg, 200))

        gradient.setColorAt(1.0, _alpha(self._bg, 225))

        p.setBrush(QBrush(gradient))

        p.drawRect(rect)

        p.setBrush(Qt.BrushStyle.NoBrush)

        p.setPen(QPen(_alpha(color, 90), 1))

        p.drawRect(rect)

        arm = 12

        p.setPen(QPen(_alpha(color, 230), 1.6))

        for x, y, dx, dy in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):

            p.drawLine(QPointF(x, y), QPointF(x + dx * arm, y))

            p.drawLine(QPointF(x, y), QPointF(x, y + dy * arm))

        p.setFont(_font(9, bold=True))

        p.setPen(_alpha(color, 220))

        p.drawText(QRectF(rect.left() + 10, rect.top() + 4, rect.width() - 20, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        return QRectF(rect.left() + 10, rect.top() + 22, rect.width() - 20, rect.height() - 28)


    def _empty(self, p, inner, color, text="NO DATA ON UPLINK"):

        p.setFont(_font(10))

        p.setPen(_alpha(color, 120))

        p.drawText(inner, Qt.AlignmentFlag.AlignCenter, text)


    def _rows(self, p, inner, rows, color, row_h=17):

        """rows: list of (left, right, highlight_color or None)."""

        y = inner.top()

        p.setFont(_font(11))

        for left, right, highlight in rows:

            if y + row_h > inner.bottom() + 2:

                break

            p.setPen(_alpha(highlight or self._ink, 225))

            p.drawText(QRectF(inner.left(), y, inner.width() * 0.68, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, left)

            p.setPen(_alpha(highlight or color, 235))

            p.drawText(QRectF(inner.left() + inner.width() * 0.5, y, inner.width() * 0.5, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, right)

            y += row_h

    # -----------------------------------------------------

    def _paint_record(self, p, rect, data, primary, alternate):

        inner = self._panel(p, rect, "// SEASON RECORD", primary)

        record = data.get("record") or "--"

        p.setFont(_font(min(44, inner.height() * 0.32), bold=True))

        p.setPen(_alpha(self._ink, 255))

        big_h = min(50, inner.height() * 0.36)

        p.drawText(QRectF(inner.left(), inner.top(), inner.width(), big_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, record)

        y = inner.top() + big_h

        p.setFont(_font(11, bold=True))

        p.setPen(_alpha(primary, 240))

        p.drawText(QRectF(inner.left(), y, inner.width(), 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, (data.get("standing") or "").upper())

        y += 22

        stats = data.get("stats", {}) or {}

        splits = data.get("splits", {}) or {}

        def fmt(value, digits=1):

            try:

                return f"{float(value):.{digits}f}"

            except (TypeError, ValueError):

                return "--"

        streak = stats.get("streak")

        streak_text = "--"

        if isinstance(streak, (int, float)) and streak:

            streak_text = f"{'W' if streak > 0 else 'L'}{abs(int(streak))}"

        diff = stats.get("differential", stats.get("pointDifferential"))

        if diff is None and stats.get("pointsFor") is not None and stats.get("pointsAgainst") is not None:

            diff = stats["pointsFor"] - stats["pointsAgainst"]

        chips = [
            ("HOME", splits.get("home", "--")),
            ("AWAY", splits.get("away", "--")),
            ("WIN %", fmt(stats.get("winPercent"), 3).lstrip("0") if stats.get("winPercent") is not None else "--"),
            ("STREAK", streak_text),
            ("PTS/G", fmt(stats.get("avgPointsFor"))),
            ("OPP/G", fmt(stats.get("avgPointsAgainst"))),
            ("DIFF", (f"{diff:+.0f}" if isinstance(diff, (int, float)) else "--")),
            ("SEASON", str(data.get("season") or "--")),
        ]

        cols = 2

        chip_w = (inner.width() - 8) / cols

        chip_h = 30

        for index, (label, value) in enumerate(chips):

            cx = inner.left() + (index % cols) * (chip_w + 8)

            cy = y + (index // cols) * (chip_h + 6)

            if cy + chip_h > inner.bottom() + 4:

                break

            box = QRectF(cx, cy, chip_w, chip_h)

            p.setPen(QPen(_alpha(primary, 80), 1))

            p.setBrush(QBrush(_alpha(self._bg, 220)))

            p.drawRect(box)

            p.setFont(_font(8))

            p.setPen(_alpha(primary, 190))

            p.drawText(QRectF(cx + 6, cy + 2, chip_w - 12, 11), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

            p.setFont(_font(12, bold=True))

            p.setPen(_alpha(self._ink, 245))

            p.drawText(QRectF(cx + 6, cy + 12, chip_w - 12, 17), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(value))


    def _paint_next_game(self, p, rect, data, primary):

        inner = self._panel(p, rect, "// NEXT ENGAGEMENT", primary)

        game = data.get("next_game")

        if not game:

            self._empty(p, inner, primary, "NO UPCOMING GAME ON SCHEDULE")

            return

        where = "VS" if game["home"] else "AT"

        opponent = (game.get("opponent_name") or game.get("opponent") or "?").upper()

        p.setFont(_font(18, bold=True))

        p.setPen(_alpha(self._ink, 255))

        p.drawText(QRectF(inner.left(), inner.top(), inner.width() * 0.66, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{where} {opponent}")

        p.setFont(_font(11))

        p.setPen(_alpha(primary, 230))

        p.drawText(QRectF(inner.left(), inner.top() + 26, inner.width() * 0.66, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, format_game_time(game.get("date")).upper())

        extra = " // ".join(part for part in (game.get("label"), game.get("venue"), game.get("broadcast")) if part)

        p.setFont(_font(9))

        p.setPen(_alpha(self._ink, 150))

        p.drawText(QRectF(inner.left(), inner.top() + 44, inner.width() * 0.7, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, extra.upper()[:70])


    def _paint_schedule(self, p, rect, data, primary):

        inner = self._panel(p, rect, "// RESULTS + SCHEDULE", primary)

        games = data.get("schedule") or []

        if not games:

            self._empty(p, inner, primary)

            return

        done = [game for game in games if game["completed"]][-4:]

        upcoming = [game for game in games if not game["completed"]][:5]

        rows = []

        for game in done:

            result = game["result"]

            color = QColor(90, 255, 140) if result.startswith("W") else QColor(255, 95, 95) if result.startswith("L") else None

            rows.append((f"{'VS' if game['home'] else '@ '} {game['opponent']}", result, color))

        if done and upcoming:

            rows.append(("─" * 8, "", _alpha(primary, 120)))

        for game in upcoming:

            rows.append((f"{'VS' if game['home'] else '@ '} {game['opponent']}", format_game_time(game["date"]).split(",")[0].upper(), None))

        self._rows(p, inner, rows, primary)


    def _paint_injuries(self, p, rect, data, primary):

        injuries = data.get("injuries") or []

        inner = self._panel(p, rect, f"// INJURY REPORT [{len(injuries)}]", primary)

        if not injuries:

            self._empty(p, inner, primary, "NO REPORTED INJURIES" if data else "NO DATA ON UPLINK")

            return

        palette = {
            "out": QColor(255, 85, 85),
            "injured reserve": QColor(255, 85, 85),
            "doubtful": QColor(255, 150, 70),
            "questionable": QColor(255, 215, 90),
            "day-to-day": QColor(255, 215, 90),
        }

        rows = []

        for item in injuries:

            name = item["name"]

            parts = name.split()

            short = f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else name

            label = f"{item.get('position', '')} {short}".strip()

            rows.append((label[:22], item["status"].upper()[:12], palette.get(item["status"].lower())))

        self._rows(p, inner, rows, primary)


    def _paint_leaders(self, p, rect, data, primary, alternate):

        inner = self._panel(p, rect, "// STATISTICAL LEADERS", primary)

        leaders = data.get("leaders") or []

        if not leaders:

            self._empty(p, inner, primary, "LEADER DATA UNAVAILABLE")

            return

        cols = 3

        chip_w = (inner.width() - 8 * (cols - 1)) / cols

        chip_h = (inner.height() - 6) / 2

        for index, item in enumerate(leaders[:6]):

            cx = inner.left() + (index % cols) * (chip_w + 8)

            cy = inner.top() + (index // cols) * (chip_h + 6)

            p.setFont(_font(8))

            p.setPen(_alpha(primary, 200))

            p.drawText(QRectF(cx, cy, chip_w, 11), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, item["category"].upper()[:20])

            p.setFont(_font(11, bold=True))

            p.setPen(_alpha(self._ink, 245))

            p.drawText(QRectF(cx, cy + 11, chip_w * 0.62, chip_h - 11), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, item["name"][:16])

            p.setPen(_alpha(alternate, 250))

            p.drawText(QRectF(cx + chip_w * 0.5, cy + 11, chip_w * 0.5, chip_h - 11), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, item["value"])

    # -----------------------------------------------------
    # Live layers
    # -----------------------------------------------------

    def _paint_countdown(self, p, geo, primary, reveal):

        game = self._team().get("next_game")

        if not game:

            return

        seconds = seconds_until(game.get("date", ""))

        if seconds is None:

            return

        rect = QRectF(geo["right_x"], geo["top"], geo["w"] - geo["right_x"] - 8, 88)

        box = QRectF(rect.right() - 150, rect.top() + 24, 136, 46)

        if seconds <= 0:

            text = "LIVE / FINAL SOON" if seconds > -4 * 3600 else "--"

        else:

            days = int(seconds // 86400)

            hours = int(seconds % 86400 // 3600)

            minutes = int(seconds % 3600 // 60)

            secs = int(seconds % 60)

            text = f"{days}D {hours:02d}:{minutes:02d}:{secs:02d}" if days else f"{hours:02d}:{minutes:02d}:{secs:02d}"

        p.setOpacity(reveal)

        p.setPen(QPen(_alpha(primary, 150), 1))

        p.setBrush(QBrush(_alpha(self._bg, 230)))

        p.drawRect(box)

        p.setFont(_font(8))

        p.setPen(_alpha(primary, 200))

        p.drawText(QRectF(box.left() + 6, box.top() + 3, box.width() - 12, 11), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "T-MINUS")

        p.setFont(_font(15, bold=True))

        p.setPen(_alpha(self._ink, 250))

        p.drawText(QRectF(box.left() + 6, box.top() + 14, box.width() - 12, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

        p.setOpacity(1.0)


    def _paint_hologram(self, p, rect, primary, alternate, reveal):

        data = self._team()

        config = self.service.team_config(self.current) or {}

        sport = data.get("sport") or config.get("sport", "football")

        now = time.perf_counter()

        flicker = 0.92 + 0.08 * math.sin(now * 29)

        cx = rect.center().x()

        size = min(rect.width(), rect.height())

        cy = rect.top() + size * 0.44

        emitter_y = rect.top() + size * 0.92

        # Panel frame (light).
        p.setPen(QPen(_alpha(primary, 60), 1))

        p.setBrush(QBrush(_alpha(primary, 10)))

        p.drawRect(rect)

        # Projector beam.
        beam = QPolygonF(
            [
                QPointF(cx - size * 0.16, emitter_y),
                QPointF(cx + size * 0.16, emitter_y),
                QPointF(cx + size * 0.44, rect.top() + 10),
                QPointF(cx - size * 0.44, rect.top() + 10),
            ]
        )

        gradient = QLinearGradient(0, emitter_y, 0, rect.top())

        boost = 1.0 + 1.5 * (1.0 - reveal)

        gradient.setColorAt(0.0, _alpha(primary, min(255, 75 * boost * flicker)))

        gradient.setColorAt(0.65, _alpha(primary, 16 * boost))

        gradient.setColorAt(1.0, _alpha(primary, 0))

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(gradient))

        p.drawPolygon(beam)

        p.setBrush(Qt.BrushStyle.NoBrush)

        for k, alpha in ((0, 230), (1, 120), (2, 60)):

            rx = size * 0.16 + k * 9

            p.setPen(QPen(_alpha(alternate if k == 0 else primary, alpha * flicker), 1.3))

            p.drawEllipse(QPointF(cx, emitter_y), rx, rx * 0.22)

        # Win/loss orbit ring.
        stats = data.get("stats", {}) or {}

        wins = float(stats.get("wins") or 0)

        losses = float(stats.get("losses") or 0)

        total = wins + losses

        ring_r = size * 0.40

        ring_ry = ring_r * 0.28

        ring_rect = QRectF(cx - ring_r, cy + size * 0.12 - ring_ry, ring_r * 2, ring_ry * 2)

        p.setPen(QPen(_alpha(primary, 50), 6))

        p.drawEllipse(ring_rect)

        if total > 0:

            win_span = int(360 * 16 * wins / total * reveal)

            p.setPen(QPen(_alpha(primary, 230 * flicker), 3))

            p.drawArc(ring_rect, 90 * 16, -win_span)

            p.setPen(QPen(QColor(255, 90, 90, int(160 * flicker)), 3))

            p.drawArc(ring_rect, 90 * 16 - win_span, -int(360 * 16 * losses / total * reveal))

        # Floating holographic ball.
        theme = self.theme()

        ball = theme.get("ball") or ("basketball" if sport == "basketball" else "football")

        lines = MODELS.get(ball, MODELS["football"])

        bob = math.sin(now * 1.35) * size * 0.035

        ball_cy = cy - size * 0.03 + bob

        scale = size * (0.25 if ball == "football" else 0.24) * _ease(reveal * 1.2)

        visible = max(1, int(len(lines) * min(1.0, reveal * 1.6)))

        if ball == "football":

            # A tight spiral around its long axis while it slowly turns.
            rotations = (
                ("x", now * 2.4),
                ("y", 0.55 + 0.35 * math.sin(now * 0.45)),
                ("z", 0.42 + 0.06 * math.sin(now * 0.9)),
                ("x2", -0.25),
            )

        else:

            rotations = (
                ("y", now * 0.9),
                ("x2", -0.38 + 0.08 * math.sin(now * 0.6)),
                ("z", 0.12 * math.sin(now * 0.5)),
            )

        trig = [(axis, math.cos(angle), math.sin(angle)) for axis, angle in rotations]

        jitter = (1.0 - reveal) * 8

        projected = []

        for points3d, kind in lines[:visible]:

            points = []

            depth = 0.0

            for x, y, z in points3d:

                for axis, c, s_ in trig:

                    if axis == "x":

                        y, z = y * c - z * s_, y * s_ + z * c

                    elif axis == "y":

                        x, z = x * c + z * s_, -x * s_ + z * c

                    elif axis == "z":

                        x, y = x * c - y * s_, x * s_ + y * c

                    else:

                        y, z = y * c - z * s_, y * s_ + z * c

                f = 3.6 / (3.6 + z)

                points.append(QPointF(cx + x * scale * f, ball_cy - y * scale * f))

                depth += z

            depth /= max(1, len(points3d))

            if jitter > 0.5:

                offset = random.uniform(-jitter, jitter)

                points = [QPointF(q.x() + offset, q.y()) for q in points]

            projected.append((depth, kind, QPolygonF(points)))

        projected.sort(key=lambda item: -item[0])

        # Soft inner glow so the ball reads as a solid hologram.
        glow_r = scale * (1.25 if ball == "football" else 1.05)

        glow = QRadialGradient(QPointF(cx, ball_cy), max(1.0, glow_r))

        glow.setColorAt(0.0, _alpha(primary, 70 * reveal * flicker))

        glow.setColorAt(0.7, _alpha(primary, 22 * reveal))

        glow.setColorAt(1.0, _alpha(primary, 0))

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(glow))

        p.drawEllipse(QPointF(cx, ball_cy), glow_r, glow_r * (0.75 if ball == "football" else 1.0))

        p.setBrush(Qt.BrushStyle.NoBrush)

        for depth, kind, polygon in projected:

            near = max(0.2, min(1.0, 0.6 - depth * 0.4))

            if kind == "mesh":

                p.setPen(QPen(_alpha(primary, 70 * near * flicker), 0.8))

                p.drawPolyline(polygon)

            else:

                p.setPen(QPen(_alpha(primary, 60 * near * flicker), 6))

                p.drawPolyline(polygon)

        for depth, kind, polygon in projected:

            if kind != "seam":

                continue

            near = max(0.2, min(1.0, 0.6 - depth * 0.4))

            color = self._ink if near > 0.7 else (alternate if ball == "football" and near > 0.45 else primary)

            p.setPen(QPen(_alpha(color, 250 * near * flicker), 1.6))

            p.drawPolyline(polygon)

        # Shadow pool on the emitter: smaller when the ball floats higher.
        lift = (bob / (size * 0.035) + 1) / 2

        shadow_w = size * (0.17 - 0.03 * lift)

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(_alpha(primary, (90 - 30 * lift) * reveal)))

        p.drawEllipse(QPointF(cx, emitter_y - 3), shadow_w, shadow_w * 0.16)

        # Holographic dust rising through the beam.
        for k in range(26):

            seed = k * 97.13

            speed = 0.10 + (k % 5) * 0.03

            life = (now * speed + (seed % 1.0)) % 1.0

            px = cx + math.sin(seed) * size * (0.10 + 0.26 * life)

            py = emitter_y - life * (emitter_y - rect.top() - 20)

            alpha = 180 * math.sin(life * math.pi) * reveal

            p.setBrush(QBrush(_alpha(self._ink if k % 4 == 0 else primary, alpha)))

            p.drawEllipse(QPointF(px, py), 1.4, 1.4)

        # Recent results orbiting as beacons.
        recent = [game for game in data.get("schedule", []) if game.get("completed")][-5:]

        for index, game in enumerate(recent):

            angle = self._angle * 0.8 + index * (2 * math.pi / max(1, len(recent)))

            bx = cx + math.cos(angle) * ring_r

            by = cy + size * 0.12 + math.sin(angle) * ring_ry

            behind = math.sin(angle) < 0

            won = game.get("result", "").startswith("W")

            color = primary if won else QColor(255, 90, 90)

            alpha = (110 if behind else 245) * reveal

            p.setPen(QPen(_alpha(color, alpha), 1.2))

            p.setBrush(QBrush(_alpha(self._bg, 220 * reveal)))

            p.drawEllipse(QPointF(bx, by), 9, 9)

            p.setFont(_font(9, bold=True))

            p.setPen(_alpha(color, alpha))

            p.drawText(QRectF(bx - 9, by - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, "W" if won else "L")

        # Hex plate with the team code.
        abbr = (data.get("abbr") or self.current or "").upper()

        plate_r = size * 0.11

        px, py = cx, rect.top() + size * 0.80

        hexagon = QPolygonF(
            [
                QPointF(px + plate_r * 1.6 * math.cos(math.radians(a)), py + plate_r * math.sin(math.radians(a)))
                for a in range(0, 360, 60)
            ]
        )

        p.setPen(QPen(_alpha(alternate, 230 * reveal), 1.6))

        p.setBrush(QBrush(_alpha(self._bg, 225 * reveal)))

        p.drawPolygon(hexagon)

        p.setFont(_font(plate_r * 0.9, bold=True))

        p.setPen(_alpha(self._ink, 255 * reveal))

        p.drawText(QRectF(px - plate_r * 1.6, py - plate_r, plate_r * 3.2, plate_r * 2), Qt.AlignmentFlag.AlignCenter, abbr)

        # Scan line through the emblem.
        scan = (now * 0.4) % 1.0

        sy = rect.top() + 8 + scan * (emitter_y - rect.top() - 16)

        p.setPen(QPen(_alpha(alternate, 70 * flicker), 1))

        p.drawLine(QPointF(rect.left() + 14, sy), QPointF(rect.right() - 14, sy))


# ---------------------------------------------------------
# Full-window team backdrop
# ---------------------------------------------------------

def _mix(a, b, t):

    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


class SportsBackdrop(QWidget):

    """
    Replaces GLITCH's green background while the Sports Nexus is open:
    a deep gradient in the team's hue, a soft glow, a fine grid, slow
    team-coloured rings and a vignette. It sits just above the reactor
    and is opaque, so nothing green bleeds through and the panels on
    top always have a dark, even surface behind them.
    Colours cross-fade when you switch teams.
    """

    FADE_S = 0.45

    BLEND_S = 0.6

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._theme = None

        self._previous = None

        self._blend_start = 0.0

        self._opacity = 0.0

        self._target = 0.0

        self._last = time.perf_counter()

        self._timer = QTimer(self)

        self._timer.setInterval(33)

        self._timer.timeout.connect(self._tick)

        self.hide()

    def set_theme(self, theme):

        if self._theme is not None and theme is not None:

            same = all(
                self._theme[name].name() == theme[name].name()
                for name in ("bg", "mid", "accent")
            )

            if same:

                return

            self._previous = self._current_colors()

            self._blend_start = time.perf_counter()

        self._theme = theme

        self.update()

    def activate(self, on):

        self._target = 1.0 if on else 0.0

        self._last = time.perf_counter()

        if on:

            self.show()

        self._timer.start()

    def _current_colors(self):

        theme = self._theme

        colors = {name: QColor(theme[name]) for name in ("bg", "mid", "accent", "accent2")}

        if self._previous is not None:

            t = _ease((time.perf_counter() - self._blend_start) / self.BLEND_S)

            if t >= 1.0:

                self._previous = None

            else:

                colors = {
                    name: _mix(self._previous[name], colors[name], t)
                    for name in colors
                }

        return colors

    def _tick(self):

        now = time.perf_counter()

        step = (now - self._last) / self.FADE_S

        self._last = now

        if self._opacity < self._target:

            self._opacity = min(self._target, self._opacity + step)

        elif self._opacity > self._target:

            self._opacity = max(self._target, self._opacity - step)

        if self._opacity <= 0.0 and self._target == 0.0:

            self._timer.stop()

            self.hide()

            return

        self.update()

    def paintEvent(self, event):

        if self._theme is None or self._opacity <= 0.0:

            return

        w, h = self.width(), self.height()

        colors = self._current_colors()

        bg, mid, accent, accent2 = colors["bg"], colors["mid"], colors["accent"], colors["accent2"]

        now = time.perf_counter()

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setOpacity(self._opacity)

        # Base gradient: darkest at the edges, a touch of the team hue
        # in the middle, never bright enough to hurt text contrast.
        base = QLinearGradient(0, 0, 0, h)

        base.setColorAt(0.0, bg)

        base.setColorAt(0.45, _mix(bg, mid, 0.55))

        base.setColorAt(1.0, bg)

        p.fillRect(self.rect(), QBrush(base))

        # Soft glow behind the hologram side.
        glow = QRadialGradient(QPointF(w * 0.32, h * 0.42), max(w, h) * 0.55)

        glow.setColorAt(0.0, _alpha(mid, 150))

        glow.setColorAt(1.0, _alpha(mid, 0))

        p.fillRect(self.rect(), QBrush(glow))

        # Fine grid.
        p.setPen(QPen(_alpha(accent, 14), 1))

        step = 40

        for x in range(0, w, step):

            p.drawLine(QPointF(x, 0), QPointF(x, h))

        for y in range(0, h, step):

            p.drawLine(QPointF(0, y), QPointF(w, y))

        # Slow rings (the team-coloured cousin of the reactor).
        cx, cy = w * 0.5, h * 0.5

        p.setBrush(Qt.BrushStyle.NoBrush)

        for k, radius in enumerate((0.22, 0.31, 0.40)):

            r = min(w, h) * radius

            p.setPen(QPen(_alpha(accent, 22), 1.2))

            p.drawEllipse(QPointF(cx, cy), r, r)

            span = 40 + 20 * k

            start = (now * (12 + 6 * k) * (1 if k % 2 == 0 else -1)) % 360

            p.setPen(QPen(_alpha(accent2 if k == 1 else accent, 55), 2))

            p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start * 16), int(span * 16))

        # Moving scan band.
        band_y = (now * 0.08 % 1.0) * (h + 200) - 100

        band = QLinearGradient(0, band_y - 80, 0, band_y + 80)

        band.setColorAt(0.0, _alpha(accent, 0))

        band.setColorAt(0.5, _alpha(accent, 16))

        band.setColorAt(1.0, _alpha(accent, 0))

        p.fillRect(QRectF(0, band_y - 80, w, 160), QBrush(band))

        # Vignette.
        vignette = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.75)

        vignette.setColorAt(0.55, _alpha(bg, 0))

        vignette.setColorAt(1.0, _alpha(QColor(0, 0, 0), 190))

        p.fillRect(self.rect(), QBrush(vignette))

        p.end()