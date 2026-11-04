import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from ui.main_window import GlitchWindow


# ======================================================
# GLITCH.EXE // APPLICATION ENTRY POINT
# ======================================================
#
# The old winsound reactor hum has been completely removed.
#
# Continuous ambience is now owned by ui/main_window.py:
#
#     audio/grid_ambience.wav
#
# through AmbientPlayer.
# ======================================================


def main():

    app = QApplication(
        sys.argv
    )

    window = GlitchWindow()

    window.show()

    # ==================================================
    # STARTUP VISUAL GLITCH
    # ==================================================

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
