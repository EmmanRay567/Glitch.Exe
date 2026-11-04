from pathlib import Path


# ======================================================
# GLITCH.EXE // LEGACY STARTUP HUM
# ======================================================
#
# The old reactor / buzzing startup hum has been disabled.
#
# GLITCH now uses:
#
#     audio/grid_ambience.wav
#
# through AmbientPlayer in ui/main_window.py.
#
# This file is intentionally kept as a harmless placeholder
# so any old imports or project references do not break.
# ======================================================


AUDIO_DIR = Path(__file__).parent

GRID_AMBIENCE_FILE = (
    AUDIO_DIR
    / "grid_ambience.wav"
)


def startup_hum_enabled():
    """
    Legacy compatibility helper.

    The old generated reactor hum is permanently disabled.
    """

    return False


def get_ambience_path():
    """
    Return the active GLITCH ambience file.
    """

    return GRID_AMBIENCE_FILE


def main():
    print(
        "GLITCH.EXE // LEGACY STARTUP HUM DISABLED"
    )

    print(
        f"ACTIVE AMBIENCE // {GRID_AMBIENCE_FILE}"
    )


if __name__ == "__main__":
    main()