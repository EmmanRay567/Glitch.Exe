import math
import random
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 44100
OUTPUT_DIR = Path(__file__).resolve().parent


def clamp(value):
    return max(-1.0, min(1.0, value))


def generate_grid_sound(
    filename,
    start_frequency,
    end_frequency,
    duration=0.16,
    secondary_frequency=None,
):
    total_samples = int(
        SAMPLE_RATE * duration
    )

    samples = []

    phase = 0.0
    secondary_phase = 0.0

    for i in range(total_samples):

        t = i / SAMPLE_RATE

        progress = (
            t / duration
        )

        # ==============================================
        # FREQUENCY SWEEP
        # ==============================================

        frequency = (
            start_frequency
            + (
                end_frequency
                - start_frequency
            )
            * progress
        )

        phase += (
            2
            * math.pi
            * frequency
            / SAMPLE_RATE
        )

        main_tone = math.sin(
            phase
        )


        # ==============================================
        # SECOND DIGITAL TONE
        # ==============================================

        secondary = 0.0

        if secondary_frequency:

            secondary_phase += (
                2
                * math.pi
                * secondary_frequency
                / SAMPLE_RATE
            )

            secondary = math.sin(
                secondary_phase
            )


        # ==============================================
        # FAST ATTACK / DECAY
        # ==============================================

        attack = min(
            1.0,
            t / 0.008
        )

        decay = (
            1.0
            - progress
        ) ** 2.2

        envelope = (
            attack
            * decay
        )


        # ==============================================
        # DIGITAL GLITCH TEXTURE
        # ==============================================

        glitch = 0.0

        # Tiny bursts rather than harsh static
        if (
            0.035
            < t
            < 0.055
        ):

            glitch = (
                random.uniform(
                    -1.0,
                    1.0
                )
                * 0.07
            )


        if (
            0.095
            < t
            < 0.108
        ):

            glitch += (
                random.uniform(
                    -1.0,
                    1.0
                )
                * 0.045
            )


        # ==============================================
        # MIX
        # ==============================================

        sample = (
            main_tone * 0.50
            + secondary * 0.16
            + glitch
        )

        sample *= envelope


        # ==============================================
        # LIGHT BITCRUSH CHARACTER
        # ==============================================

        crushed = (
            round(
                sample * 48
            )
            / 48
        )

        sample = (
            sample * 0.78
            + crushed * 0.22
        )


        # ==============================================
        # SOFT DISTORTION
        # ==============================================

        sample = math.tanh(
            sample * 1.25
        )

        sample *= 0.55

        sample = clamp(
            sample
        )


        samples.append(
            struct.pack(
                "<h",
                int(
                    sample * 32767
                )
            )
        )


    output_path = (
        OUTPUT_DIR
        / filename
    )


    with wave.open(
        str(output_path),
        "w"
    ) as wav:

        wav.setnchannels(
            1
        )

        wav.setsampwidth(
            2
        )

        wav.setframerate(
            SAMPLE_RATE
        )

        wav.writeframes(
            b"".join(samples)
        )


    print(
        f"Created: {output_path.name}"
    )


# ======================================================
# GLITCH.EXE UI SOUND SET
# ======================================================

generate_grid_sound(
    "ui_home.wav",
    420,
    300,
    secondary_frequency=170
)

generate_grid_sound(
    "ui_chat.wav",
    520,
    360,
    secondary_frequency=230
)

generate_grid_sound(
    "ui_create.wav",
    360,
    620,
    secondary_frequency=240
)

generate_grid_sound(
    "ui_search.wav",
    650,
    400,
    secondary_frequency=310
)

generate_grid_sound(
    "ui_code.wav",
    330,
    220,
    secondary_frequency=145
)

generate_grid_sound(
    "ui_apps.wav",
    470,
    290,
    secondary_frequency=190
)

generate_grid_sound(
    "ui_settings.wav",
    390,
    330,
    secondary_frequency=165
)


print(
    "GLITCH.EXE UI sound bank complete."
)
