import sys
import winsound
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ui.main_window import GlitchWindow


# ======================================================
# AUDIO PATH
# ======================================================

BASE_DIR = Path(__file__).resolve().parent

HUM_FILE = (
    BASE_DIR
    / "audio"
    / "startup_hum.wav"
)


# ======================================================
# REACTOR AUDIO
# ======================================================

def start_reactor_hum():
    if HUM_FILE.exists():
        winsound.PlaySound(
            str(HUM_FILE),
            winsound.SND_FILENAME
            | winsound.SND_ASYNC
            | winsound.SND_LOOP
        )

    else:
        print(
            f"GLITCH AUDIO ERROR: "
            f"{HUM_FILE} not found."
        )


def stop_reactor_hum():
    winsound.PlaySound(
        None,
        0
    )


# ======================================================
# MAIN APPLICATION
# ======================================================

def main():
    app = QApplication(sys.argv)

    window = GlitchWindow()

    # Start reactor audio
    start_reactor_hum()

    # Stop audio when GLITCH closes
    app.aboutToQuit.connect(
        stop_reactor_hum
    )

    window.show()

    # Startup visual glitch
    QTimer.singleShot(
        250,
        lambda: window.reactor.trigger_glitch(
            1.1,
            18
        )
    )

    sys.exit(
        app.exec()
    )


# ======================================================
# LAUNCH
# ======================================================

if __name__ == "__main__":
    main()