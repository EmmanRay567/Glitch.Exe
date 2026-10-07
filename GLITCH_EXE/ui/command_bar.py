from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)

from PySide6.QtCore import (
    Signal,
    Qt,
)


class CommandBar(QWidget):

    commandSubmitted = Signal(str)


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
            """
        )


        # ==================================================
        # LAYOUT
        # ==================================================

        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            5,
            5,
            5,
            5
        )

        layout.setSpacing(
            12
        )


        # ==================================================
        # MICROPHONE BUTTON
        # ==================================================

        self.mic_button = QPushButton(
            "◎"
        )

        self.mic_button.setFixedSize(
            42,
            42
        )

        self.mic_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.mic_button.setStyleSheet(
            """
            QPushButton {
                color: #39ff78;

                background: rgba(0, 40, 20, 70);

                border: 1px solid rgba(57, 255, 120, 130);

                border-radius: 21px;

                font-size: 17px;
            }

            QPushButton:hover {
                background: rgba(57, 255, 120, 45);

                border: 1px solid #39ff78;
            }
            """
        )


        # ==================================================
        # INPUT
        # ==================================================

        self.input_field = QLineEdit()

        self.input_field.setPlaceholderText(
            "Type or speak to GLITCH.EXE..."
        )

        self.input_field.setStyleSheet(
            """
            QLineEdit {
                color: #caffd9;

                background: rgba(0, 14, 7, 35);

                border: none;
                border-bottom: 1px solid rgba(57, 255, 120, 55);

                padding: 10px;

                font-size: 13px;
            }

            QLineEdit:focus {
                border-bottom: 1px solid rgba(57, 255, 120, 200);

                background: rgba(0, 30, 15, 45);
            }
            """
        )


        # ==================================================
        # SEND BUTTON
        # ==================================================

        self.send_button = QPushButton(
            "➤"
        )

        self.send_button.setFixedSize(
            42,
            42
        )

        self.send_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.send_button.setStyleSheet(
            """
            QPushButton {
                color: #39ff78;

                background: rgba(0, 40, 20, 70);

                border: 1px solid rgba(57, 255, 120, 130);

                border-radius: 21px;

                font-size: 18px;
            }

            QPushButton:hover {
                background: rgba(57, 255, 120, 45);

                border: 1px solid #39ff78;
            }

            QPushButton:pressed {
                background: rgba(57, 255, 120, 80);
            }
            """
        )


        layout.addWidget(
            self.mic_button
        )

        layout.addWidget(
            self.input_field,
            1
        )

        layout.addWidget(
            self.send_button
        )


        # ==================================================
        # CONNECTIONS
        # ==================================================

        self.send_button.clicked.connect(
            self.submit_command
        )

        self.input_field.returnPressed.connect(
            self.submit_command
        )


    # ======================================================
    # SUBMIT
    # ======================================================

    def submit_command(self):

        message = (
            self.input_field
            .text()
            .strip()
        )

        if not message:
            return

        self.commandSubmitted.emit(
            message
        )

        self.input_field.clear()