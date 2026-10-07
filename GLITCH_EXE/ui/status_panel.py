from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from PySide6.QtCore import Qt


class StatusPanel(QWidget):

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
        # MAIN LAYOUT
        # ==================================================

        self.layout = QVBoxLayout(self)

        self.layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        self.layout.setSpacing(
            12
        )


        # ==================================================
        # TITLE
        # ==================================================

        title = QLabel(
            "SYSTEM STATUS"
        )

        title.setStyleSheet(
            """
            color: #d8ffe5;

            font-size: 13px;
            font-weight: bold;

            letter-spacing: 3px;
            """
        )

        self.layout.addWidget(
            title
        )


        # ==================================================
        # STATUS ITEMS
        # ==================================================

        (
            self.core_status
        ) = self.create_status_row(
            "CORE AI"
        )

        (
            self.voice_status
        ) = self.create_status_row(
            "VOICE ENGINE"
        )

        (
            self.memory_status
        ) = self.create_status_row(
            "MEMORY"
        )

        (
            self.gesture_status
        ) = self.create_status_row(
            "GESTURES"
        )

        (
            self.health_status
        ) = self.create_status_row(
            "SYSTEM HEALTH"
        )


        self.layout.addStretch()


    # ======================================================
    # CREATE STATUS ROW
    # ======================================================

    def create_status_row(
        self,
        name
    ):

        container = QWidget()

        container.setStyleSheet(
            """
            QWidget {
                background: rgba(0, 18, 10, 45);

                border: 1px solid rgba(57, 255, 120, 20);

                border-radius: 6px;
            }
            """
        )

        row = QHBoxLayout(
            container
        )

        row.setContentsMargins(
            5,
            4,
            5,
            4
        )


        dot = QLabel(
            "●"
        )

        dot.setStyleSheet(
            """
            color: #39ff78;
            border: none;
            background: transparent;
            """
        )


        name_label = QLabel(
            name
        )

        name_label.setStyleSheet(
            """
            color: rgba(185, 255, 210, 190);
            font-size: 10px;
            border: none;
            background: transparent;
            """
        )


        status_label = QLabel(
            "ONLINE"
        )

        status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        status_label.setStyleSheet(
            """
            color: #39ff78;
            font-size: 10px;
            border: none;
            background: transparent;
            """
        )


        row.addWidget(
            dot
        )

        row.addWidget(
            name_label
        )

        row.addStretch()

        row.addWidget(
            status_label
        )


        self.layout.addWidget(
            container
        )

        return status_label


    # ======================================================
    # STATUS SETTERS
    # ======================================================

    def set_core_status(
        self,
        value
    ):

        self.core_status.setText(
            value
        )


    def set_voice_status(
        self,
        value
    ):

        self.voice_status.setText(
            value
        )


    def set_memory_status(
        self,
        value
    ):

        self.memory_status.setText(
            value
        )


    def set_gesture_status(
        self,
        value
    ):

        self.gesture_status.setText(
            value
        )


    def set_health_status(
        self,
        value
    ):

        self.health_status.setText(
            value
        )