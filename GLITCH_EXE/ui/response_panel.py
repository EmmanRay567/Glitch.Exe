from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QPlainTextEdit,
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

        self.response_label = QPlainTextEdit()

        self.response_label.setReadOnly(
            True
        )

        self.response_label.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.response_label.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.response_label.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.response_label.setStyleSheet(
            """
            QPlainTextEdit {
                color: rgba(205, 255, 220, 220);
                font-size: 13px;
                font-family: Consolas;

                background: rgba(0, 15, 8, 35);

                border:
                    1px solid
                    rgba(57, 255, 120, 25);

                border-radius: 10px;
                padding: 10px;
            }

            QScrollBar:vertical {
                background: rgba(0, 10, 6, 80);
                width: 8px;
                margin: 4px 2px 4px 2px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: rgba(57, 255, 120, 110);
                min-height: 24px;
                border-radius: 4px;
            }

            QScrollBar::handle:vertical:hover {
                background: rgba(57, 255, 120, 180);
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            """
        )

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.response_label,
            1
        )


    def set_response(
        self,
        text
    ):

        self.response_label.setPlainText(
            str(text)
        )

        self.response_label.verticalScrollBar().setValue(
            0
        )
