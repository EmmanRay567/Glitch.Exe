from datetime import datetime

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
)


class SecurityFindingsOverlay(
    QWidget
):

    closed = Signal()

    def __init__(
        self,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.panel = QFrame(
            self
        )

        self.panel.setStyleSheet(
            """
            QFrame {
                background: rgba(1, 9, 6, 246);
                border: 1px solid rgba(57,255,120,150);
                border-radius: 8px;
            }
            """
        )

        layout = QVBoxLayout(
            self.panel
        )

        layout.setContentsMargins(
            20,
            16,
            20,
            18
        )

        layout.setSpacing(
            8
        )

        header = QHBoxLayout()

        title = QLabel(
            (
                "SECURITY FINDINGS // "
                "ACTIVE INTELLIGENCE"
            )
        )

        title.setStyleSheet(
            """
            color: #39ff78;
            font-family: Consolas;
            font-size: 16px;
            font-weight: bold;
            letter-spacing: 2px;
            border: none;
            background: transparent;
            """
        )

        self.close_button = QPushButton(
            "CLOSE // X"
        )

        self.close_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.close_button.setStyleSheet(
            """
            QPushButton {
                color: #9dffb9;
                background: rgba(57,255,120,18);
                border: 1px solid rgba(57,255,120,100);
                border-radius: 5px;
                padding: 6px 10px;
                font-family: Consolas;
                font-weight: bold;
            }

            QPushButton:hover {
                background: rgba(57,255,120,45);
            }
            """
        )

        self.close_button.clicked.connect(
            self.close_overlay
        )

        header.addWidget(
            title,
            1
        )

        header.addWidget(
            self.close_button
        )

        self.subtitle = QLabel(
            (
                "NUMBERED FINDINGS // "
                "FIRST SEEN // LAST SEEN // "
                "PATH // REASONS"
            )
        )

        self.subtitle.setStyleSheet(
            """
            color: rgba(170,255,195,155);
            font-family: Consolas;
            font-size: 9px;
            border: none;
            background: transparent;
            """
        )

        self.text = QPlainTextEdit()

        self.text.setReadOnly(
            True
        )

        self.text.setStyleSheet(
            """
            QPlainTextEdit {
                color: #b9ffd0;
                background: rgba(0, 15, 8, 190);
                border: 1px solid rgba(57,255,120,55);
                border-radius: 6px;
                padding: 12px;
                font-family: Consolas;
                font-size: 11px;
                selection-background-color:
                    rgba(57,255,120,60);
            }
            """
        )

        self.command_hint = QLabel(
            (
                "VOICE/TYPE // "
                "SHOW FINDING 1 // "
                "RESOLVE FINDING 1 // "
                "QUARANTINE FINDING 1 // "
                "TERMINATE FINDING 1 // "
                "BLOCK FINDING 1"
            )
        )

        self.command_hint.setWordWrap(
            True
        )

        self.command_hint.setStyleSheet(
            """
            color: rgba(57,255,120,175);
            font-family: Consolas;
            font-size: 9px;
            font-weight: bold;
            border: none;
            background: transparent;
            """
        )

        layout.addLayout(
            header
        )

        layout.addWidget(
            self.subtitle
        )

        layout.addWidget(
            self.text,
            1
        )

        layout.addWidget(
            self.command_hint
        )

        self.hide()

    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        margin_x = max(
            90,
            int(
                self.width()
                * 0.14
            )
        )

        margin_y = max(
            70,
            int(
                self.height()
                * 0.10
            )
        )

        self.panel.setGeometry(
            margin_x,
            margin_y,

            max(
                640,
                self.width()
                - margin_x * 2
            ),

            max(
                420,
                self.height()
                - margin_y * 2
            ),
        )

    @staticmethod
    def _stamp(
        value
    ):

        try:

            return (
                datetime
                .fromtimestamp(
                    float(
                        value
                    )
                )
                .strftime(
                    "%Y-%m-%d %I:%M:%S %p"
                )
            )

        except Exception:

            return "UNKNOWN"

    def show_findings(
        self,
        findings,
        history=None,
        selected_index=None
    ):

        findings = list(
            findings
            or []
        )

        history = list(
            history
            or []
        )

        lines = []

        if not findings:

            lines.extend(
                [
                    "ACTIVE FINDINGS // 0",
                    "",
                    (
                        "No unresolved security findings "
                        "are currently stored."
                    ),
                ]
            )

        else:

            lines.append(
                (
                    "ACTIVE FINDINGS // "
                    f"{len(findings)}"
                )
            )

            lines.append(
                "=" * 74
            )

            for (
                index,
                finding
            ) in enumerate(
                findings,
                start=1
            ):

                selected = (
                    "  <== SELECTED"
                    if selected_index == index
                    else ""
                )

                severity = str(
                    finding.get(
                        "severity"
                    )
                    or "REVIEW"
                ).upper()

                score = int(
                    finding.get(
                        "risk_score"
                    )
                    or 0
                )

                name = str(
                    finding.get(
                        "process_name"
                    )
                    or "UNKNOWN"
                )

                pid = finding.get(
                    "pid"
                )

                path = str(
                    finding.get(
                        "process_path"
                    )
                    or "UNKNOWN"
                )

                reasons = (
                    finding.get(
                        "reasons"
                    )
                    or []
                )

                lines.append(
                    (
                        f"FINDING {index} // "
                        f"{severity} // "
                        f"RISK {score}"
                        f"{selected}"
                    )
                )

                lines.append(
                    (
                        f"PROCESS // {name} // "
                        "PID "
                        f"{pid if pid is not None else 'UNKNOWN'}"
                    )
                )

                lines.append(
                    f"PATH // {path}"
                )

                lines.append(
                    (
                        "FIRST SEEN // "
                        + self._stamp(
                            finding.get(
                                "first_seen"
                            )
                        )
                    )
                )

                lines.append(
                    (
                        "LAST SEEN  // "
                        + self._stamp(
                            finding.get(
                                "last_seen"
                            )
                        )
                    )
                )

                if reasons:

                    for reason in reasons:

                        lines.append(
                            f"REASON // {reason}"
                        )

                else:

                    lines.append(
                        (
                            "REASON // "
                            "No reason data available"
                        )
                    )

                lines.append(
                    "-" * 74
                )

        if history:

            lines.append(
                ""
            )

            lines.append(
                "RECENT SECURITY HISTORY"
            )

            lines.append(
                "=" * 74
            )

            for event in history[:8]:

                stamp = self._stamp(
                    event.get(
                        "last_seen"
                    )
                )

                severity = str(
                    event.get(
                        "severity"
                    )
                    or "INFO"
                ).upper()

                process = str(
                    event.get(
                        "process_name"
                    )
                    or "SYSTEM"
                )

                title = str(
                    event.get(
                        "title"
                    )
                    or
                    event.get(
                        "event_type"
                    )
                    or "EVENT"
                )

                lines.append(
                    (
                        f"{stamp} // "
                        f"{severity:<10} // "
                        f"{process:<18} // "
                        f"{title}"
                    )
                )

        self.text.setPlainText(
            "\n".join(
                lines
            )
        )

        self.show()

        self.raise_()

    def close_overlay(
        self
    ):

        self.hide()

        self.closed.emit()
