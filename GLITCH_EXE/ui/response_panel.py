from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
)

from PySide6.QtCore import Qt


class ResponsePanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
            }

            QLabel {
                background: transparent;
            }
            """
        )


        # ==================================================
        # LAYOUT
        # ==================================================

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            10,
            5,
            10,
            5
        )

        layout.setSpacing(
            5
        )


        # ==================================================
        # TITLE
        # ==================================================

        self.title_label = QLabel(
            "GLITCH.EXE RESPONSE"
        )

        self.title_label.setStyleSheet(
            """
            color: #39ff78;

            font-size: 11px;
            font-weight: bold;

            letter-spacing: 2px;
            """
        )


        # ==================================================
        # RESPONSE
        # ==================================================

        self.response_label = QLabel(
            "SYSTEM READY"
        )

        self.response_label.setWordWrap(
            True
        )

        self.response_label.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        self.response_label.setStyleSheet(
            """
            color: rgba(205, 255, 220, 220);

            font-size: 13px;

            background: rgba(0, 15, 8, 35);

            border: 1px solid rgba(57, 255, 120, 25);

            border-radius: 10px;

            padding: 10px;
            """
        )


        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.response_label
        )


    # ======================================================
    # SET RESPONSE
    # ======================================================

    def set_response(
        self,
        text
    ):

        self.response_label.setText(
            text
        )