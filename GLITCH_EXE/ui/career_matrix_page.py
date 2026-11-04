"""
ui/career_matrix_page.py

GLITCH Career Matrix.

Left:  a holographic "agent": a full-body figure in a hacker mask
       (an original visor-faceplate design) wearing whatever outfit is
       set in the Customizer, rendered in your chosen shade of green.
Right: four decks, every control a real button (mouse or finger pinch):

  CAMPUS  FAMU iStrike events + FAMU / Famuan / press news
  JOBS    local (Adzuna) + remote (Remotive) leads, Handshake link
  WORLD   local news, world news, local events (Ticketmaster)
  STYLE   the Customizer: style, top, bottom, shoes, shade, fit,
          budget. "GLITCH PICKS" asks the AI for today's outfit
          (weather + campus aware); "FIND IT" web-searches real
          products that match, each one opens in your browser.

Swipe left/right on this page to change deck.
"""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal

from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
    QRadialGradient,
)

from PySide6.QtWidgets import QPushButton, QWidget

from services.career_service import (
    OUTFIT_OPTIONS,
    SHADE_HEX,
    format_age,
    format_when,
)


GREEN = QColor(57, 255, 120)
PALE = QColor(205, 255, 222)
DARK = QColor(2, 10, 6)
DIM = QColor(57, 255, 120, 90)


def _font(px, bold=False):

    font = QFont("Consolas")

    font.setStyleHint(QFont.StyleHint.Monospace)

    font.setPixelSize(max(7, int(px)))

    font.setBold(bold)

    return font


def _a(color, alpha):

    c = QColor(color)

    c.setAlpha(max(0, min(255, int(alpha))))

    return c


def _ease(t):

    t = max(0.0, min(1.0, t))

    return 1.0 - (1.0 - t) ** 3


def _frame(w, h, cut=7):

    return QPolygonF(
        [
            QPointF(cut, 0.5), QPointF(w - 0.5, 0.5), QPointF(w - 0.5, h - cut),
            QPointF(w - cut, h - 0.5), QPointF(0.5, h - 0.5), QPointF(0.5, cut),
        ]
    )


# =========================================================
# BUTTONS
# =========================================================

class HoloTab(QPushButton):

    def __init__(self, text, parent=None, small=False):

        super().__init__(text, parent)

        self.active = False

        self.small = small

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setFlat(True)

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        glow = 1.0 if self.active else (0.5 if self.underMouse() else 0.2)

        p.setBrush(QBrush(_a(GREEN, 18 + 55 * glow)))

        p.setPen(QPen(_a(GREEN, 80 + 170 * glow), 1.1))

        p.drawPolygon(_frame(w, h, 6 if self.small else 8))

        p.setFont(_font(h * (0.38 if self.small else 0.36), bold=self.active))

        p.setPen(_a(PALE if self.active else GREEN, 150 + 105 * glow))

        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.text())

        if self.active and not self.small:

            p.setPen(Qt.PenStyle.NoPen)

            p.setBrush(QBrush(_a(PALE, 230)))

            p.drawRect(QRectF(w * 0.25, h - 3, w * 0.5, 2))

        p.end()


class OptionChip(QPushButton):

    def __init__(self, category, value, parent=None):

        super().__init__(value, parent)

        self.category = category

        self.value = value

        self.selected = False

        self.swatch = QColor(SHADE_HEX[value]) if category == "shade" else None

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setFlat(True)

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        on = 1.0 if self.selected else (0.45 if self.underMouse() else 0.0)

        p.setBrush(QBrush(_a(GREEN, 12 + 60 * on)))

        p.setPen(QPen(_a(GREEN, 70 + 180 * on), 1))

        p.drawPolygon(_frame(w, h, 5))

        x = 0

        if self.swatch is not None:

            p.setPen(Qt.PenStyle.NoPen)

            p.setBrush(QBrush(self.swatch))

            p.drawEllipse(QPointF(9, h / 2), 4.5, 4.5)

            x = 10

        p.setFont(_font(min(11, h * 0.42), bold=self.selected))

        p.setPen(_a(PALE if self.selected else GREEN, 160 + 95 * on))

        text = p.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, w - 6 - x)

        p.drawText(QRectF(x, 0, w - x, h), Qt.AlignmentFlag.AlignCenter, text)

        p.end()


class HoloRow(QPushButton):

    """One clickable feed item: title, meta line and a tag."""

    def __init__(self, parent=None):

        super().__init__("", parent)

        self.title = ""

        self.meta = ""

        self.tag = ""

        self.url = ""

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setFlat(True)

        self.clicked.connect(self._open)

    def set_item(self, title, meta="", tag="", url=""):

        self.title, self.meta, self.tag, self.url = title, meta, tag, url

        # Text is what the finger pointer shows as the target label.
        self.setText(title[:40])

        self.setToolTip(url)

        self.update()

    def _open(self):

        if self.url:

            QDesktopServices.openUrl(QUrl(self.url))

    def paintEvent(self, event):

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        hover = 1.0 if self.underMouse() or self.isDown() else 0.0

        p.setBrush(QBrush(_a(DARK, 200)))

        p.setPen(QPen(_a(GREEN, 55 + 150 * hover), 1))

        p.drawPolygon(_frame(w, h, 6))

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(_a(GREEN, 120 + 120 * hover)))

        p.drawRect(QRectF(0, 6, 2, h - 12))

        tag_w = 0

        if self.tag:

            p.setFont(_font(9, bold=True))

            tag_w = p.fontMetrics().horizontalAdvance(self.tag) + 14

            box = QRectF(w - tag_w - 8, 6, tag_w, 15)

            p.setPen(QPen(_a(GREEN, 160), 1))

            p.setBrush(QBrush(_a(GREEN, 30)))

            p.drawRect(box)

            p.setPen(_a(PALE, 230))

            p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.tag)

        p.setFont(_font(12, bold=True))

        p.setPen(_a(PALE, 240))

        title = p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, int(w - 22 - tag_w - 10))

        p.drawText(QRectF(10, 4, w - 20 - tag_w, h * 0.5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

        p.setFont(_font(10))

        p.setPen(_a(GREEN, 200))

        meta = p.fontMetrics().elidedText(self.meta, Qt.TextElideMode.ElideRight, int(w - 22))

        p.drawText(QRectF(10, h * 0.5, w - 20, h * 0.45), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)

        p.end()


# =========================================================
# HOLOGRAPHIC AGENT
# =========================================================

def _sym(points):

    """Mirror right-side points (x >= 0, listed top to bottom) to make
    a closed symmetric outline."""

    right = list(points)

    left = [(-x, y) for x, y in reversed(points)]

    return right + left


def _limb(x0, y0, x1, y1, w0, w1):

    """Quad for an arm / leg segment from (x0,y0) to (x1,y1)."""

    dx, dy = x1 - x0, y1 - y0

    length = math.hypot(dx, dy) or 1

    nx, ny = -dy / length, dx / length

    return [
        (x0 + nx * w0, y0 + ny * w0),
        (x1 + nx * w1, y1 + ny * w1),
        (x1 - nx * w1, y1 - ny * w1),
        (x0 - nx * w0, y0 - ny * w0),
    ]


class AgentRenderer:

    """
    Draws the masked agent in unit space (y: 0 top of head .. 1 floor,
    x centred) scaled into a rect. Garments follow the outfit dict.
    """

    def __init__(self):

        self.turn = 1.0

    def paint(self, p, rect, outfit, now, reveal=1.0):

        shade = QColor(SHADE_HEX.get(outfit.get("shade"), "#39ff78"))

        fit = {"SLIM": 0.93, "REGULAR": 1.0, "OVERSIZED": 1.14}.get(outfit.get("fit"), 1.0)

        height = rect.height() * 0.86

        cx = rect.center().x()

        top = rect.top() + rect.height() * 0.05 + math.sin(now * 1.2) * 2.0

        # Slow quarter-turn sway, faked by squashing x.
        self.turn = 0.82 + 0.18 * math.cos(now * 0.55)

        sx = height * self.turn

        sy = height

        flicker = (0.93 + 0.07 * math.sin(now * 27)) * reveal

        def pt(x, y):

            return QPointF(cx + x * sx, top + y * sy)

        def poly(points):

            return QPolygonF([pt(x, y) for x, y in points])

        def draw(points, fill_alpha=55, line_alpha=230, color=None, width=1.4):

            color = color or shade

            p.setBrush(QBrush(_a(color, fill_alpha * flicker)))

            p.setPen(QPen(_a(color, line_alpha * flicker), width))

            p.drawPolygon(poly(points))

        def line(points, alpha=200, color=None, width=1.1):

            p.setPen(QPen(_a(color or shade, alpha * flicker), width))

            p.setBrush(Qt.BrushStyle.NoBrush)

            p.drawPolyline(QPolygonF([pt(x, y) for x, y in points]))

        # -------- projector base + beam
        base_y = top + 0.985 * sy

        beam = QLinearGradient(0, base_y, 0, top)

        beam.setColorAt(0.0, _a(GREEN, 60 * flicker))

        beam.setColorAt(1.0, _a(GREEN, 0))

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(beam))

        p.drawPolygon(
            QPolygonF(
                [
                    QPointF(cx - height * 0.16, base_y), QPointF(cx + height * 0.16, base_y),
                    QPointF(cx + height * 0.30, top), QPointF(cx - height * 0.30, top),
                ]
            )
        )

        p.setBrush(Qt.BrushStyle.NoBrush)

        for k, alpha in ((0, 220), (1, 110), (2, 55)):

            r = height * 0.16 + k * 8

            p.setPen(QPen(_a(GREEN, alpha * flicker), 1.3))

            p.drawEllipse(QPointF(cx, base_y), r, r * 0.18)

        # -------- base body (skin layer: faint wireframe)
        skin = GREEN

        body = _sym([(0.035, 0.14), (0.04, 0.175), (0.13, 0.195), (0.115, 0.30), (0.10, 0.47), (0.11, 0.52)])

        draw(body, 14, 70, skin, 1.0)

        arms = [
            _limb(0.125, 0.205, 0.155, 0.36, 0.032, 0.026),
            _limb(0.155, 0.36, 0.165, 0.49, 0.026, 0.021),
        ]

        for arm in arms:

            draw(arm, 14, 70, skin, 1.0)

            draw([(-x, y) for x, y in arm], 14, 70, skin, 1.0)

        for side in (1, -1):

            hand = [(side * 0.15, 0.49), (side * 0.18, 0.49), (side * 0.178, 0.535), (side * 0.152, 0.535)]

            draw(hand, 25, 110, skin, 1.0)

        legs = [
            _limb(0.055, 0.52, 0.06, 0.72, 0.048, 0.038),
            _limb(0.06, 0.72, 0.062, 0.93, 0.038, 0.03),
        ]

        for leg in legs:

            draw(leg, 14, 70, skin, 1.0)

            draw([(-x, y) for x, y in leg], 14, 70, skin, 1.0)

        # -------- garments (bottom, shoes, top, then head on top)
        self._bottom(outfit.get("bottom"), fit, draw, line, shade)

        self._shoes(outfit.get("shoes"), draw, line, shade)

        self._top(outfit.get("top"), fit, draw, line, shade)

        self._head(p, pt, poly, draw, line, outfit.get("top"), now, flicker)

        # -------- holographic scan lines + rising rings
        figure = QRectF(cx - height * 0.24, top - 4, height * 0.48, sy * 0.99)

        p.setPen(QPen(_a(GREEN, 16 * flicker), 1))

        y = figure.top()

        while y < figure.bottom():

            p.drawLine(QPointF(figure.left(), y), QPointF(figure.right(), y))

            y += 3

        for k in range(3):

            phase = (now * 0.22 + k / 3.0) % 1.0

            ry = top + (0.96 - phase * 0.94) * sy

            rw = height * (0.17 + 0.03 * math.sin(phase * math.pi))

            p.setPen(QPen(_a(GREEN, 140 * math.sin(phase * math.pi) * flicker), 1.2))

            p.drawEllipse(QPointF(cx, ry), rw, rw * 0.12)

    # -----------------------------------------------------

    def _top(self, kind, fit, draw, line, shade):

        f = fit

        sw = 0.135 * f

        accent = QColor(PALE)

        if kind == "SUIT JACKET":

            jacket = _sym([(0.035, 0.155), (sw + 0.008, 0.195), (0.118 * f, 0.30), (0.108 * f, 0.47), (0.115 * f, 0.56), (0.0, 0.565)])

            draw(jacket, 70, 240)

            for side in (1, -1):

                sleeve = _limb(side * 0.128 * f, 0.205, side * 0.16, 0.36, 0.036 * f, 0.03 * f)

                draw(sleeve, 70, 230)

                draw(_limb(side * 0.16, 0.36, side * 0.168, 0.485, 0.03 * f, 0.026 * f), 70, 230)

            draw([(-0.03, 0.16), (0.03, 0.16), (0.0, 0.32)], 150, 255, accent, 1.0)   # shirt

            draw([(-0.009, 0.165), (0.009, 0.165), (0.014, 0.30), (0.0, 0.325), (-0.014, 0.30)], 160, 255, shade.darker(160), 1.0)  # tie

            for side in (1, -1):   # lapels

                line([(side * 0.032, 0.158), (side * 0.06, 0.215), (side * 0.045, 0.225), (side * 0.004, 0.36)], 240, accent, 1.3)

            for by in (0.40, 0.45):

                line([(0.0, by), (0.004, by + 0.004)], 255, accent, 3)

            line([(0.055, 0.42), (0.095, 0.418)], 160)

            line([(-0.095, 0.418), (-0.055, 0.42)], 160)

        elif kind == "HOODIE":

            hoodie = _sym([(0.04, 0.155), (sw + 0.012, 0.2), (0.122 * f, 0.31), (0.112 * f, 0.5), (0.115 * f, 0.535), (0.0, 0.54)])

            draw(hoodie, 75, 240)

            for side in (1, -1):

                draw(_limb(side * 0.13 * f, 0.21, side * 0.162, 0.36, 0.04 * f, 0.034 * f), 75, 230)

                draw(_limb(side * 0.162, 0.36, side * 0.168, 0.475, 0.034 * f, 0.03 * f), 75, 230)

                draw(_limb(side * 0.167, 0.472, side * 0.168, 0.492, 0.024, 0.022), 110, 230)   # cuff

            draw([(-0.06, 0.40), (0.06, 0.40), (0.075, 0.49), (-0.075, 0.49)], 40, 200)   # pocket

            line([(-0.11 * f, 0.515), (0.11 * f, 0.515)], 160)   # rib band

            for side in (1, -1):   # drawstrings

                line([(side * 0.018, 0.17), (side * 0.022, 0.26)], 230, accent, 1.2)

        elif kind in ("BUTTON-UP", "QUARTER-ZIP"):

            shirt = _sym([(0.035, 0.155), (sw, 0.198), (0.115 * f, 0.30), (0.105 * f, 0.48), (0.108 * f, 0.51), (0.0, 0.515)])

            draw(shirt, 65, 235)

            for side in (1, -1):

                draw(_limb(side * 0.126 * f, 0.205, side * 0.158, 0.36, 0.033 * f, 0.028 * f), 65, 225)

                draw(_limb(side * 0.158, 0.36, side * 0.166, 0.485, 0.028 * f, 0.024 * f), 65, 225)

            if kind == "BUTTON-UP":

                for side in (1, -1):

                    draw([(side * 0.002, 0.152), (side * 0.045, 0.16), (side * 0.03, 0.19)], 120, 245, accent, 1.0)

                line([(0.0, 0.17), (0.0, 0.5)], 200, accent, 1.0)

                for by in (0.22, 0.29, 0.36, 0.43):

                    line([(0.0, by), (0.003, by + 0.003)], 255, accent, 3)

            else:

                draw(_sym([(0.035, 0.12), (0.042, 0.165), (0.0, 0.17)]), 110, 245)   # high collar

                line([(0.0, 0.125), (0.0, 0.30)], 255, accent, 1.6)   # zip

                line([(-0.008, 0.30), (0.008, 0.30)], 255, accent, 2)

        else:   # TEE / POLO

            tee = _sym([(0.035, 0.155), (sw, 0.198), (0.115 * f, 0.30), (0.105 * f, 0.48), (0.108 * f, 0.505), (0.0, 0.51)])

            draw(tee, 65, 235)

            for side in (1, -1):

                draw(_limb(side * 0.128 * f, 0.205, side * 0.15, 0.30, 0.036 * f, 0.032 * f), 65, 225)

            if kind == "POLO":

                for side in (1, -1):

                    draw([(side * 0.002, 0.152), (side * 0.042, 0.158), (side * 0.03, 0.188)], 120, 245, accent, 1.0)

                line([(0.0, 0.17), (0.0, 0.25)], 220, accent, 1.0)

                for by in (0.19, 0.22):

                    line([(0.0, by), (0.003, by + 0.003)], 255, accent, 3)

            else:

                line([(-0.035, 0.158), (0.0, 0.178), (0.035, 0.158)], 230, accent, 1.2)


    def _bottom(self, kind, fit, draw, line, shade):

        f = fit

        accent = QColor(PALE)

        if kind == "SHORTS":

            for side in (1, -1):

                draw(_limb(side * 0.055, 0.5, side * 0.062, 0.665, 0.058 * f, 0.05 * f), 70, 235)

            draw(_sym([(0.11 * f, 0.47), (0.112 * f, 0.52), (0.0, 0.53)]), 70, 235)

            line([(-0.008, 0.48), (0.008, 0.48)], 200, accent, 1.2)

            return

        widths = {
            "SUIT PANTS": (0.05, 0.036),
            "CHINOS": (0.05, 0.035),
            "JEANS": (0.052, 0.038),
            "SWEATPANTS": (0.058, 0.04),
            "JOGGERS": (0.054, 0.03),
        }.get(kind, (0.05, 0.036))

        hip, ankle = widths[0] * f, widths[1] * f

        draw(_sym([(0.11 * f, 0.47), (0.115 * f, 0.53), (0.0, 0.54)]), 70, 235)

        for side in (1, -1):

            draw(_limb(side * 0.055, 0.5, side * 0.06, 0.72, hip, (hip + ankle) / 2), 70, 235)

            draw(_limb(side * 0.06, 0.72, side * 0.062, 0.925, (hip + ankle) / 2, ankle), 70, 235)

            if kind in ("SUIT PANTS", "CHINOS"):

                line([(side * 0.058, 0.55), (side * 0.062, 0.92)], 140, accent, 0.9)   # crease

            if kind == "JEANS":

                line([(side * (0.055 + hip * 0.8), 0.53), (side * (0.062 + ankle * 0.8), 0.92)], 150, accent, 0.9)

            if kind in ("SWEATPANTS", "JOGGERS"):

                draw(_limb(side * 0.062, 0.905, side * 0.062, 0.93, ankle * 0.9, ankle * 0.9), 120, 240)   # cuff

        if kind in ("CHINOS", "SUIT PANTS", "JEANS"):

            line([(-0.11 * f, 0.485), (0.11 * f, 0.485)], 220, accent, 1.4)   # belt line

        if kind in ("SWEATPANTS", "JOGGERS"):

            for side in (1, -1):

                line([(side * 0.012, 0.48), (side * 0.016, 0.54)], 220, accent, 1.1)   # drawstring


    def _shoes(self, kind, draw, line, shade):

        accent = QColor(PALE)

        for side in (1, -1):

            x = side * 0.062

            toe = side * 0.03

            if kind == "DRESS SHOES":

                draw([(x - 0.028, 0.93), (x + 0.028, 0.93), (x + 0.03 + toe, 0.965), (x + 0.02 + toe, 0.975), (x - 0.03, 0.975)], 120, 245, shade.darker(140))

            elif kind == "BOOTS":

                draw([(x - 0.032, 0.86), (x + 0.032, 0.86), (x + 0.034, 0.94), (x + 0.03 + toe, 0.96), (x + 0.028 + toe, 0.978), (x - 0.034, 0.978)], 110, 245)

                line([(x - 0.034, 0.968), (x + 0.03 + toe, 0.968)], 220, accent, 1.2)

            elif kind == "SLIDES":

                draw([(x - 0.03, 0.965), (x + 0.03 + toe * 0.6, 0.965), (x + 0.03 + toe * 0.6, 0.978), (x - 0.03, 0.978)], 120, 245)

                draw([(x - 0.026, 0.94), (x + 0.026, 0.94), (x + 0.028, 0.962), (x - 0.028, 0.962)], 100, 240)

            else:   # SNEAKERS / HIGH-TOPS

                collar = 0.885 if kind == "HIGH-TOPS" else 0.925

                draw([(x - 0.032, collar), (x + 0.03, collar), (x + 0.034, 0.95), (x + 0.03 + toe, 0.962), (x + 0.03 + toe, 0.975), (x - 0.034, 0.975)], 110, 245)

                line([(x - 0.034, 0.966), (x + 0.03 + toe, 0.966)], 230, accent, 1.6)   # sole

                for k in range(3):

                    ly = collar + 0.01 + k * 0.009

                    line([(x - 0.006, ly), (x + 0.012, ly)], 210, accent, 1.0)   # laces


    def _head(self, p, pt, poly, draw, line, top_kind, now, flicker):

        # Hood behind the head.
        if top_kind == "HOODIE":

            hood = [(0.0, -0.005), (0.06, 0.012), (0.082, 0.07), (0.075, 0.13), (0.045, 0.165), (-0.045, 0.165), (-0.075, 0.13), (-0.082, 0.07), (-0.06, 0.012)]

            draw(hood, 60, 220)

        # Neck.
        draw([(-0.024, 0.13), (0.024, 0.13), (0.028, 0.165), (-0.028, 0.165)], 30, 110, GREEN, 1.0)

        # Head + mask faceplate (original design: smooth plate,
        # single angular visor, cheek vents, circuit traces).
        head = [(0.0, 0.002), (0.045, 0.012), (0.058, 0.05), (0.056, 0.095), (0.04, 0.13), (0.0, 0.142), (-0.04, 0.13), (-0.056, 0.095), (-0.058, 0.05), (-0.045, 0.012)]

        draw(head, 40, 150, GREEN, 1.0)

        mask = [(0.0, 0.02), (0.044, 0.03), (0.052, 0.06), (0.05, 0.1), (0.03, 0.128), (0.0, 0.136), (-0.03, 0.128), (-0.05, 0.1), (-0.052, 0.06), (-0.044, 0.03)]

        draw(mask, 120, 255, QColor(16, 40, 26), 1.6)

        p.setPen(QPen(_a(GREEN, 230 * flicker), 1.4))

        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawPolygon(poly(mask))

        pulse = 0.6 + 0.4 * math.sin(now * 3.1)

        visor = [(-0.045, 0.058), (0.0, 0.07), (0.045, 0.058), (0.042, 0.072), (0.0, 0.084), (-0.042, 0.072)]

        draw(visor, 200 * pulse, 255, QColor(170, 255, 205), 1.2)

        # Visor glow.
        center = pt(0.0, 0.07)

        glow = QRadialGradient(center, max(4.0, abs(pt(0.06, 0).x() - pt(0, 0).x())))

        glow.setColorAt(0.0, _a(GREEN, 120 * pulse * flicker))

        glow.setColorAt(1.0, _a(GREEN, 0))

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QBrush(glow))

        p.drawEllipse(center, abs(pt(0.07, 0).x() - pt(0, 0).x()), abs(pt(0, 0.03).y() - pt(0, 0).y()))

        for side in (1, -1):

            for k in range(3):

                vx = side * (0.026 + k * 0.007)

                line([(vx, 0.098), (vx, 0.118)], 200, GREEN, 1.0)   # vents

            line([(side * 0.046, 0.064), (side * 0.054, 0.048), (side * 0.054, 0.036)], 210, GREEN, 1.0)   # traces

        line([(0.0, 0.03), (0.0, 0.052)], 200, GREEN, 1.0)


# =========================================================
# PAGE
# =========================================================

TABS = ("CAMPUS", "JOBS", "WORLD", "STYLE")

FEEDS = {
    "CAMPUS": [("EVENTS", "campus_events"), ("NEWS", "campus_news")],
    "JOBS": [("ALL", "jobs"), ("LOCAL", "jobs:LOCAL"), ("REMOTE", "jobs:REMOTE")],
    "WORLD": [("LOCAL", "local_news"), ("WORLD", "world_news"), ("EVENTS", "local_events")],
}

EMPTY_HINTS = {
    "campus_events": "NO UPCOMING iSTRIKE EVENTS FOUND",
    "campus_news": "NO CAMPUS NEWS ON UPLINK",
    "jobs": "NO JOB LEADS YET // CHECK KEYWORDS IN data/career_profile.json",
    "jobs:LOCAL": "LOCAL JOBS NEED A FREE ADZUNA KEY (ADZUNA_APP_ID / ADZUNA_APP_KEY)",
    "jobs:REMOTE": "NO REMOTE LEADS FOR YOUR KEYWORDS",
    "local_news": "NO LOCAL NEWS ON UPLINK",
    "world_news": "NO WORLD NEWS ON UPLINK",
    "local_events": "LOCAL EVENTS NEED A FREE TICKETMASTER KEY (TICKETMASTER_API_KEY)",
}


class CareerMatrixPage(QWidget):

    # Spoken feedback for the main window ("Found 6 matches...").
    announce = Signal(str)

    def __init__(self, career_service, parent=None):

        super().__init__(parent)

        self.service = career_service

        self.agent = AgentRenderer()

        self.tab = "CAMPUS"

        self.feed_index = {name: 0 for name in FEEDS}

        self.page_index = 0

        self.outfit = dict(career_service.outfit)

        self.products = []

        self.product_page = 0

        self.style_status = "SET YOUR LOOK, THEN FIND IT"

        self.status = {}

        self._reveal_start = time.perf_counter()

        # ---- tabs
        self.tab_buttons = {}

        for name in TABS:

            button = HoloTab(name, self)

            button.clicked.connect(lambda checked=False, n=name: self.set_tab(n))

            self.tab_buttons[name] = button

        # ---- feed selector (max 3) + link button
        self.feed_buttons = [HoloTab("", self, small=True) for _ in range(3)]

        for index, button in enumerate(self.feed_buttons):

            button.clicked.connect(lambda checked=False, i=index: self.set_feed(i))

        self.link_button = HoloTab("", self, small=True)

        self.link_button.clicked.connect(self._open_link)

        self.sync_button = HoloTab("SYNC", self, small=True)

        self.sync_button.clicked.connect(lambda: self.service.refresh(force=True))

        # ---- rows + pager
        self.rows = [HoloRow(self) for _ in range(10)]

        self.prev_button = HoloTab("◀ PREV", self, small=True)

        self.next_button = HoloTab("NEXT ▶", self, small=True)

        self.prev_button.clicked.connect(lambda: self._page(-1))

        self.next_button.clicked.connect(lambda: self._page(1))

        # ---- customizer
        self.chips = {}

        for category, options in OUTFIT_OPTIONS.items():

            for value in options:

                chip = OptionChip(category, value, self)

                chip.clicked.connect(lambda checked=False, c=category, v=value: self.choose(c, v))

                self.chips[(category, value)] = chip

        self.pick_button = HoloTab("GLITCH PICKS", self, small=True)

        self.find_button = HoloTab("FIND IT ▶", self, small=True)

        self.pick_button.clicked.connect(self.recommend)

        self.find_button.clicked.connect(self.find)

        # ---- service
        self.service.section_updated.connect(self._on_section)

        self.service.section_status.connect(self._on_status)

        self.service.outfit_recommended.connect(self._on_recommended)

        self.service.products_found.connect(self._on_products)

        self.service.outfit_error.connect(self._on_outfit_error)

        self._timer = QTimer(self)

        self._timer.setInterval(40)

        self._timer.timeout.connect(self._tick)

        self._sync_chips()

        self.set_tab("CAMPUS")

    # =====================================================
    # PUBLIC
    # =====================================================

    def set_tab(self, name):

        if name not in TABS:

            return

        self.tab = name

        self.page_index = 0

        for key, button in self.tab_buttons.items():

            button.active = key == name

            button.update()

        self._layout()

        self.update()


    def next_tab(self, step=1):

        index = TABS.index(self.tab)

        self.set_tab(TABS[(index + step) % len(TABS)])


    def set_feed(self, index):

        if self.tab not in FEEDS or index >= len(FEEDS[self.tab]):

            return

        self.feed_index[self.tab] = index

        self.page_index = 0

        self._layout()

        self.update()


    def choose(self, category, value):

        self.outfit[category] = value

        self.service.save_outfit({k: v for k, v in self.outfit.items() if k != "why"})

        self._sync_chips()

        self.update()


    def recommend(self, occasion=""):

        self.style_status = "GLITCH IS PICKING YOUR FIT..."

        self.service.recommend_outfit(occasion if isinstance(occasion, str) else "")

        self.update()


    def find(self, extra=""):

        self.style_status = "SEARCHING STORES FOR YOUR LOOK..."

        self.products = []

        self._layout()

        self.service.find_products(self.outfit, extra if isinstance(extra, str) else "")

        self.update()

    # =====================================================
    # SERVICE CALLBACKS
    # =====================================================

    def _on_section(self, section, payload):

        self._layout()

        self.update()


    def _on_status(self, section, text):

        self.status[section] = text

        self.update()


    def _on_recommended(self, outfit):

        why = outfit.pop("why", "")

        self.outfit.update(outfit)

        self.service.save_outfit(self.outfit)

        self._sync_chips()

        self.style_status = "GLITCH PICKED THIS // " + (why.upper()[:70] if why else "READY")

        self.announce.emit(why or "Here's what I'd wear today.")

        self.update()


    def _on_products(self, products):

        self.products = products

        self.product_page = 0

        self.style_status = f"{len(products)} MATCHES FOUND // TAP ONE TO OPEN" if products else "NO MATCHING PRODUCTS FOUND"

        self.announce.emit(
            f"Found {len(products)} pieces that match your look." if products else "I couldn't find good matches for that look."
        )

        self._layout()

        self.update()


    def _on_outfit_error(self, message):

        self.style_status = message.upper()[:80]

        self.update()

    # =====================================================
    # HELPERS
    # =====================================================

    def _feed_key(self):

        return FEEDS[self.tab][self.feed_index[self.tab]][1]


    def _items(self):

        key = self._feed_key()

        if key.startswith("jobs:"):

            kind = key.split(":")[1]

            return [job for job in self.service.get("jobs") if job.get("kind") == kind]

        return self.service.get(key)


    def _row_view(self, key, item):

        if key in ("campus_events", "local_events"):

            where = item.get("location") or "TBA"

            org = f" // {item['org']}" if item.get("org") else ""

            return item["title"], f"{format_when(item.get('start')).upper()} // {where.upper()}{org.upper()}", "EVENT"

        if key.startswith("jobs"):

            parts = [item.get("company", ""), item.get("location", ""), item.get("salary", "")]

            return item["title"], " // ".join(part for part in parts if part).upper(), item.get("kind", "")

        meta = " // ".join(part for part in (item.get("source", ""), format_age(item.get("time")) or item.get("year", "")) if part)

        return item["title"], meta.upper(), "NEWS"


    def _sync_chips(self):

        for (category, value), chip in self.chips.items():

            chip.selected = self.outfit.get(category) == value

            chip.update()


    def _open_link(self):

        url = {
            "CAMPUS": self.service.profile.get("istrike_url"),
            "JOBS": self.service.profile.get("handshake_url"),
        }.get(self.tab)

        if url:

            QDesktopServices.openUrl(QUrl(url))


    def _page(self, step):

        if self.tab == "STYLE":

            self.product_page = max(0, self.product_page + step)

        else:

            self.page_index = max(0, self.page_index + step)

        self._layout()

        self.update()

    # =====================================================
    # LAYOUT
    # =====================================================

    def _boxes(self):

        w, h = self.width(), self.height()

        left_w = max(200, min(w * 0.34, 330))

        rx = left_w + 12

        return w, h, left_w, rx, w - rx - 8


    def resizeEvent(self, event):

        super().resizeEvent(event)

        self._layout()


    def _layout(self):

        w, h, left_w, rx, rw = self._boxes()

        tab_w = (rw - 3 * 6) / 4

        for index, name in enumerate(TABS):

            self.tab_buttons[name].setGeometry(int(rx + index * (tab_w + 6)), 6, int(tab_w), 34)

        for row in self.rows:

            row.hide()

        for chip in self.chips.values():

            chip.setVisible(self.tab == "STYLE")

        for button in self.feed_buttons + [self.link_button]:

            button.hide()

        self.pick_button.setVisible(self.tab == "STYLE")

        self.find_button.setVisible(self.tab == "STYLE")

        self.sync_button.setGeometry(int(w - 8 - 58), int(h - 30), 58, 24)

        y = 48

        if self.tab == "STYLE":

            y = self._layout_style(rx, rw, y, h)

            items = self.products

            page = self.product_page

            key = "products"

        else:

            feeds = FEEDS[self.tab]

            fx = rx

            for index, (label, _) in enumerate(feeds):

                button = self.feed_buttons[index]

                button.setText(label)

                button.active = index == self.feed_index[self.tab]

                button.setGeometry(int(fx), y, 84, 26)

                button.show()

                button.update()

                fx += 90

            link = {"CAMPUS": "OPEN iSTRIKE ↗", "JOBS": "OPEN HANDSHAKE ↗"}.get(self.tab)

            if link:

                self.link_button.setText(link)

                self.link_button.setGeometry(int(rx + rw - 150), y, 150, 26)

                self.link_button.show()

            y += 34

            items = self._items()

            page = self.page_index

            key = self._feed_key()

        row_h = 44 if self.tab != "STYLE" else 40

        bottom = h - 38

        per_page = max(1, min(len(self.rows), int((bottom - y) // (row_h + 6))))

        pages = max(1, math.ceil(len(items) / per_page))

        page = min(page, pages - 1)

        if self.tab == "STYLE":

            self.product_page = page

        else:

            self.page_index = page

        self._list_top = y

        self._list_key = key

        for slot, item in enumerate(items[page * per_page:(page + 1) * per_page]):

            row = self.rows[slot]

            if key == "products":

                title = f"{item['piece']} // {item['name']}"

                meta = " // ".join(part for part in (item["store"], item["price"], item["match"]) if part).upper()

                row.set_item(title, meta, item["price"] or "SHOP", item["url"])

            else:

                title, meta, tag = self._row_view(key, item)

                row.set_item(title, meta, tag, item.get("url", ""))

            row.setGeometry(int(rx), int(y + slot * (row_h + 6)), int(rw), row_h)

            row.show()

        self._pages = (page, pages, len(items))

        show_pager = pages > 1

        self.prev_button.setVisible(show_pager)

        self.next_button.setVisible(show_pager)

        self.prev_button.setGeometry(int(rx), int(h - 30), 80, 24)

        self.next_button.setGeometry(int(rx + 86), int(h - 30), 80, 24)


    def _layout_style(self, rx, rw, y, h):

        label_w = 64

        chip_h = 24

        gap = 4

        for category, options in OUTFIT_OPTIONS.items():

            count = len(options)

            chip_w = (rw - label_w - gap * (count - 1)) / count

            for index, value in enumerate(options):

                self.chips[(category, value)].setGeometry(
                    int(rx + label_w + index * (chip_w + gap)), int(y), int(chip_w), chip_h
                )

            y += chip_h + 5

        y += 4

        half = (rw - 8) / 2

        self.pick_button.setGeometry(int(rx), int(y), int(half), 28)

        self.find_button.setGeometry(int(rx + half + 8), int(y), int(half), 28)

        self._style_status_y = y + 34

        return y + 34 + 20

    # =====================================================
    # PAINT
    # =====================================================

    def showEvent(self, event):

        self._timer.start()

        self._reveal_start = time.perf_counter()

        self.service.refresh()

        self.service.emit_cached()

        super().showEvent(event)


    def hideEvent(self, event):

        self._timer.stop()

        super().hideEvent(event)


    def _figure_rect(self):

        w, h, left_w, rx, rw = self._boxes()

        return QRectF(6, 48, left_w - 6, h - 48 - 8)


    def _tick(self):

        # Only the hologram animates.
        self.update(self._figure_rect().adjusted(-2, -2, 2, 2).toAlignedRect())


    def paintEvent(self, event):

        w, h, left_w, rx, rw = self._boxes()

        if w < 320 or h < 260:

            return

        p = QPainter(self)

        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        now = time.perf_counter()

        reveal = _ease((now - self._reveal_start) / 0.8)

        # Header.
        p.setFont(_font(11, bold=True))

        p.setPen(_a(GREEN, 190))

        p.drawText(QRectF(8, 4, left_w, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "// CAREER MATRIX")

        p.setFont(_font(18, bold=True))

        p.setPen(_a(PALE, 250))

        p.drawText(QRectF(8, 20, left_w, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "AGENT 404")

        # Figure panel.
        figure = self._figure_rect()

        p.setPen(QPen(_a(GREEN, 70), 1))

        p.setBrush(QBrush(_a(DARK, 150)))

        p.drawRect(figure)

        self.agent.paint(p, figure.adjusted(10, 30, -10, -6), self.outfit, now, reveal)

        p.setFont(_font(9, bold=True))

        p.setPen(_a(GREEN, 200))

        p.drawText(figure.adjusted(8, 4, -8, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "HOLO-FIT // " + self.outfit.get("style", ""))

        weather = self.service.weather_summary()

        if weather:

            p.setFont(_font(9))

            p.setPen(_a(PALE, 200))

            p.drawText(figure.adjusted(8, 17, -8, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, weather.upper()[:44])

        # Right side.
        if self.tab == "STYLE":

            self._paint_style(p, rx, rw)

        self._paint_list_state(p, rx, rw, h)

        p.end()


    def _paint_style(self, p, rx, rw):

        y = 48

        p.setFont(_font(9, bold=True))

        for category in OUTFIT_OPTIONS:

            p.setPen(_a(GREEN, 210))

            p.drawText(QRectF(rx, y, 62, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, category.upper())

            y += 29

        p.setFont(_font(10, bold=True))

        p.setPen(_a(PALE, 230))

        p.drawText(
            QRectF(rx, getattr(self, "_style_status_y", y + 40), rw, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "▸ " + self.style_status,
        )


    def _paint_list_state(self, p, rx, rw, h):

        page, pages, total = getattr(self, "_pages", (0, 1, 0))

        key = getattr(self, "_list_key", "")

        p.setFont(_font(9))

        p.setPen(_a(GREEN, 170))

        if pages > 1:

            p.drawText(QRectF(rx + 174, h - 30, 140, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"PAGE {page + 1}/{pages} // {total} ITEMS")

        if key and key != "products":

            section = key.split(":")[0]

            age = self.service.age_minutes(section)

            status = self.status.get(section, "")

            text = status or ("CACHED" if age is not None else "AWAITING UPLINK")

            if age is not None:

                text += f" // SYNCED {age} MIN AGO"

            p.drawText(QRectF(rx, h - 30, rw - 66, 24), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text[:70])

        if total == 0:

            p.setFont(_font(11))

            p.setPen(_a(GREEN, 150))

            hint = (
                "NO PRODUCTS YET // PRESS FIND IT"
                if key == "products"
                else EMPTY_HINTS.get(key, "NO DATA")
            )

            if not (key == "products" and self.style_status.startswith("SEARCHING")):

                p.drawText(
                    QRectF(rx, getattr(self, "_list_top", 90), rw, 60),
                    Qt.AlignmentFlag.AlignCenter,
                    hint,
                )