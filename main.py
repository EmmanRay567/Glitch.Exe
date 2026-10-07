import sys

from PySide6.QtWidgets import QApplication, QLabel, QWidget
from PySide6.QtCore import Qt

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("GLITCH.EXE")
window.resize(1000, 650)

window.setStyleSheet("""
    QWidget {
        background-color: #020504;
    }
""")

label = QLabel("GLITCH.EXE", window)
label.setAlignment(Qt.AlignCenter)

label.setStyleSheet("""
    QLabel {
        color: #39ff78;
        font-size: 48px;
        font-weight: bold;
    }
""")

label.setGeometry(300, 250, 400, 100)

window.show()

sys.exit(app.exec())