from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    QPropertyAnimation,
    QEasingCurve,
)

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGraphicsOpacityEffect,
)


class SecurityAlertOverlay(QWidget):

    alert_finished = Signal()

    COLORS = {
        "REVIEW": "#ffc34d",
        "CAUTION": "#ffc34d",
        "SUSPICIOUS": "#ff8a4c",
        "WARNING": "#ff8a4c",
        "HIGH": "#ff4b4b",
        "CRITICAL": "#ff4b4b",
    }

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

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.hide()

        self.card = QFrame(
            self
        )

        self.card.setFixedHeight(
            104
        )

        self.card.setMinimumWidth(
            610
        )

        self.card.setMaximumWidth(
            820
        )

        layout = QVBoxLayout(
            self.card
        )

        layout.setContentsMargins(
            18,
            11,
            18,
            11
        )

        layout.setSpacing(
            4
        )

        header_row = QHBoxLayout()

        self.icon_label = QLabel(
            "⚠"
        )

        self.header_label = QLabel(
            "SECURITY ALERT"
        )

        self.score_label = QLabel(
            ""
        )

        header_row.addWidget(
            self.icon_label
        )

        header_row.addWidget(
            self.header_label,
            1
        )

        header_row.addWidget(
            self.score_label
        )

        self.message_label = QLabel(
            ""
        )

        self.message_label.setWordWrap(
            True
        )

        self.reason_label = QLabel(
            ""
        )

        self.reason_label.setWordWrap(
            True
        )

        layout.addLayout(
            header_row
        )

        layout.addWidget(
            self.message_label
        )

        layout.addWidget(
            self.reason_label
        )

        self.opacity_effect = (
            QGraphicsOpacityEffect(
                self.card
            )
        )

        self.card.setGraphicsEffect(
            self.opacity_effect
        )

        self.fade_animation = (
            QPropertyAnimation(
                self.opacity_effect,
                b"opacity",
                self
            )
        )

        self.fade_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self.hide_timer = QTimer(
            self
        )

        self.hide_timer.setSingleShot(
            True
        )

        self.hide_timer.timeout.connect(
            self._fade_out
        )


    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        width = min(
            820,
            max(
                610,
                self.width()
                - 360
            )
        )

        self.card.setFixedWidth(
            width
        )

        self.card.move(
            int(
                (
                    self.width()
                    - width
                )
                / 2
            ),
            26
        )


    def show_alert(
        self,
        severity,
        process_name,
        score,
        reason
    ):

        severity = str(
            severity
            or "REVIEW"
        ).strip().upper()

        accent = self.COLORS.get(
            severity,
            "#ffc34d"
        )

        self.card.setStyleSheet(
            f"""
            QFrame {{
                background: rgba(5, 8, 7, 242);
                border: 2px solid {accent};
                border-radius: 8px;
            }}
            """
        )

        self.icon_label.setStyleSheet(
            f"""
            color: {accent};
            font-family: Consolas;
            font-size: 26px;
            font-weight: bold;
            background: transparent;
            border: none;
            """
        )

        self.header_label.setText(
            f"SECURITY ALERT // {severity}"
        )

        self.header_label.setStyleSheet(
            f"""
            color: {accent};
            font-family: Consolas;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
            border: none;
            """
        )

        self.score_label.setText(
            f"RISK // {int(score or 0):02d}"
        )

        self.score_label.setStyleSheet(
            f"""
            color: {accent};
            font-family: Consolas;
            font-size: 11px;
            font-weight: bold;
            background: transparent;
            border: none;
            """
        )

        self.message_label.setText(
            f"PROCESS // {process_name or 'UNKNOWN'}"
        )

        self.message_label.setStyleSheet(
            """
            color: #d6ffe2;
            font-family: Consolas;
            font-size: 12px;
            font-weight: bold;
            background: transparent;
            border: none;
            """
        )

        self.reason_label.setText(
            f"ANALYSIS // {reason or 'Unusual process behavior requires review.'}"
        )

        self.reason_label.setStyleSheet(
            """
            color: rgba(190,255,210,190);
            font-family: Consolas;
            font-size: 10px;
            background: transparent;
            border: none;
            """
        )

        self.hide_timer.stop()
        self.fade_animation.stop()

        self.opacity_effect.setOpacity(
            0.0
        )

        self.show()
        self.raise_()

        self.fade_animation.setDuration(
            220
        )

        self.fade_animation.setStartValue(
            0.0
        )

        self.fade_animation.setEndValue(
            1.0
        )

        self.fade_animation.start()

        self.hide_timer.start(
            9000
            if severity
            in {
                "HIGH",
                "CRITICAL",
            }
            else 6500
        )


    def _fade_out(
        self
    ):

        self.fade_animation.stop()

        self.fade_animation.setDuration(
            320
        )

        self.fade_animation.setStartValue(
            self.opacity_effect.opacity()
        )

        self.fade_animation.setEndValue(
            0.0
        )

        try:
            self.fade_animation.finished.disconnect(
                self._finish_hide
            )
        except Exception:
            pass

        self.fade_animation.finished.connect(
            self._finish_hide
        )

        self.fade_animation.start()


    def _finish_hide(
        self
    ):

        try:
            self.fade_animation.finished.disconnect(
                self._finish_hide
            )
        except Exception:
            pass

        self.hide()

        self.alert_finished.emit()

