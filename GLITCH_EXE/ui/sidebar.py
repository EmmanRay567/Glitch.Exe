from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from PySide6.QtCore import Qt


class Sidebar(QWidget):

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

            QPushButton {
                background: rgba(0, 18, 10, 70);
                color: rgba(185, 255, 210, 190);

                border: 1px solid rgba(57, 255, 120, 55);
                border-radius: 8px;

                padding: 10px;
                text-align: left;

                font-size: 13px;
            }

            QPushButton:hover {
                background: rgba(20, 255, 100, 35);

                color: #39ff78;

                border: 1px solid rgba(57, 255, 120, 150);
            }

            QPushButton:pressed {
                background: rgba(57, 255, 120, 55);
            }
            """
        )


        # ==================================================
        # MAIN LAYOUT
        # ==================================================

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            10,
            10,
            10,
            10
        )

        layout.setSpacing(
            10
        )


        # ==================================================
        # LOGO
        # ==================================================

        logo = QLabel(
            "GLITCH.EXE"
        )

        logo.setStyleSheet(
            """
            color: #39ff78;
            font-size: 16px;
            font-weight: bold;
            letter-spacing: 2px;
            """
        )

        subtitle = QLabel(
            "P E R S O N A L   A I"
        )

        subtitle.setStyleSheet(
            """
            color: rgba(180, 255, 210, 120);
            font-size: 8px;
            letter-spacing: 3px;
            """
        )


        layout.addWidget(
            logo
        )

        layout.addWidget(
            subtitle
        )

        layout.addSpacing(
            12
        )


        # ==================================================
        # NAVIGATION
        # ==================================================

        self.home_button = QPushButton(
            "HOME"
        )

        self.chat_button = QPushButton(
            "CHAT"
        )

        self.create_button = QPushButton(
            "CREATE"
        )

        self.search_button = QPushButton(
            "SEARCH"
        )

        self.code_button = QPushButton(
            "CODE"
        )

        self.apps_button = QPushButton(
            "APPS"
        )

        self.settings_button = QPushButton(
            "SETTINGS"
        )


        buttons = [
            self.home_button,
            self.chat_button,
            self.create_button,
            self.search_button,
            self.code_button,
            self.apps_button,
            self.settings_button,
        ]

        for button in buttons:

            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            layout.addWidget(
                button
            )


        layout.addStretch()


        # ==================================================
        # ACTIVE BUTTON
        # ==================================================

        self.home_button.setStyleSheet(
            """
            QPushButton {
                background: rgba(57, 255, 120, 35);

                color: #39ff78;

                border: 1px solid rgba(57, 255, 120, 190);
                border-radius: 8px;

                padding: 10px;

                text-align: left;

                font-size: 13px;
            }

            QPushButton:hover {
                background: rgba(57, 255, 120, 55);
            }
            """
        )