import wave
import math
import random
import struct
from pathlib import Path
import winsound


# ======================================================
# SETTINGS
# ======================================================

SAMPLE_RATE = 44100
DURATION = 8.0

OUTPUT_FILE = Path(__file__).parent / "startup_hum.wav"


def clamp(value):
    return max(-1.0, min(1.0, value))


# ======================================================
# GENERATE MAIN REACTOR HUM
# ======================================================

samples = []

total_samples = int(
    SAMPLE_RATE * DURATION
)

for i in range(total_samples):

    t = i / SAMPLE_RATE

    # --------------------------------------------------
    # STARTUP FADE-IN
    # --------------------------------------------------

    fade_in = min(
        1.0,
        t / 0.12
    )

    # --------------------------------------------------
    # MAIN LOW REACTOR TONES
    # --------------------------------------------------

    fundamental = math.sin(
        2 * math.pi * 115 * t
    )

    harmonic_1 = math.sin(
        2 * math.pi * 230 * t
    )

    harmonic_2 = math.sin(
        2 * math.pi * 345 * t
    )

    harmonic_3 = math.sin(
        2 * math.pi * 460 * t
    )

    # --------------------------------------------------
    # SLOW ENERGY MOVEMENT
    # --------------------------------------------------

    slow_modulation = (
        0.88
        + 0.07
        * math.sin(
            2 * math.pi * 3.2 * t
        )
        + 0.04
        * math.sin(
            2 * math.pi * 6.7 * t
        )
    )

    # --------------------------------------------------
    # ELECTRICAL TEXTURE
    # --------------------------------------------------

    electric = (
        math.sin(
            2 * math.pi * 620 * t
        )
        * 0.010
    )

    noise = (
        random.uniform(
            -1.0,
            1.0
        )
        * 0.010
    )

    # --------------------------------------------------
    # STARTUP SURGE
    # --------------------------------------------------

    surge = 0.0

    if t < 0.65:

        surge_progress = (
            t / 0.65
        )

        surge_frequency = (
            70
            + surge_progress * 420
        )

        surge_envelope = (
            1.0
            - surge_progress
        )

        surge = (
            math.sin(
                2
                * math.pi
                * surge_frequency
                * t
            )
            * surge_envelope
            * 0.52
        )

    # --------------------------------------------------
    # STARTUP LOW BOOM
    # --------------------------------------------------

    boom = 0.0

    if t < 0.35:

        boom_envelope = (
            1.0
            - t / 0.35
        )

        boom = (
            math.sin(
                2 * math.pi * 70 * t
            )
            * boom_envelope
            * 0.40
        )

    # --------------------------------------------------
    # MIX EVERYTHING
    # --------------------------------------------------

    sample = (
        fundamental * 0.48
        + harmonic_1 * 0.21
        + harmonic_2 * 0.10
        + harmonic_3 * 0.03
        + electric
        + noise
        + surge
        + boom
    )

    sample *= slow_modulation
    sample *= fade_in

    # Warm saturation
    sample = math.tanh(
        sample * 1.25
    )

    # Overall volume
    sample *= 0.65

    samples.append(sample)


# ======================================================
# SOFT GLITCH DISTORTION
# ======================================================

glitch_samples = samples.copy()


# ------------------------------------------------------
# LIGHT BITCRUSH
# ------------------------------------------------------

BIT_LEVELS = 128

for i in range(len(glitch_samples)):

    sample = glitch_samples[i]

    crushed = round(
        sample * BIT_LEVELS
    ) / BIT_LEVELS

    glitch_samples[i] = (
        sample * 0.90
        + crushed * 0.10
    )


# ------------------------------------------------------
# MICRO GLITCHES
# ------------------------------------------------------

number_of_glitches = 12

for _ in range(number_of_glitches):

    start = random.randint(
        int(SAMPLE_RATE * 0.8),
        len(glitch_samples) - 3000
    )

    glitch_length = random.randint(
        180,
        900
    )

    effect_type = random.choice(
        [
            "dropout",
            "repeat",
            "distort"
        ]
    )

    # --------------------------------------------------
    # SMOOTH DROPOUT
    # --------------------------------------------------

    if effect_type == "dropout":

        for j in range(
            start,
            min(
                start + glitch_length,
                len(glitch_samples)
            )
        ):

            position = (
                j - start
            ) / glitch_length

            smooth_env = (
                0.5
                - 0.5
                * math.cos(
                    2
                    * math.pi
                    * position
                )
            )

            reduction = (
                1.0
                - smooth_env * 0.45
            )

            glitch_samples[j] *= reduction

    # --------------------------------------------------
    # SOFT DIGITAL STUTTER
    # --------------------------------------------------

    elif effect_type == "repeat":

        source_start = max(
            0,
            start - 220
        )

        for j in range(glitch_length):

            target = start + j

            if target >= len(glitch_samples):
                break

            source = (
                source_start
                + (j % 220)
            )

            glitch_samples[target] = (
                glitch_samples[target] * 0.60
                + glitch_samples[source] * 0.40
            )

    # --------------------------------------------------
    # WARM DISTORTION
    # --------------------------------------------------

    elif effect_type == "distort":

        for j in range(
            start,
            min(
                start + glitch_length,
                len(glitch_samples)
            )
        ):

            original = glitch_samples[j]

            distorted = math.tanh(
                original * 1.7
            )

            # Blend instead of replacing the sound
            glitch_samples[j] = (
                original * 0.55
                + distorted * 0.45
            )


# ======================================================
# SOFT LOW-PITCH DIGITAL PULSES
# ======================================================

for _ in range(10):

    start = random.randint(
        int(SAMPLE_RATE * 0.7),
        len(glitch_samples) - 500
    )

    spike_length = random.randint(
        120,
        320
    )

    spike_frequency = random.choice(
        [
            160,
            190,
            220,
            260
        ]
    )

    for j in range(spike_length):

        index = start + j

        if index >= len(glitch_samples):
            break

        spike_t = (
            j / SAMPLE_RATE
        )

        # Smooth entrance AND exit
        envelope = math.sin(
            math.pi
            * j
            / spike_length
        )

        spike = (
            math.sin(
                2
                * math.pi
                * spike_frequency
                * spike_t
            )
            * envelope
            * 0.035
        )

        glitch_samples[index] += spike


# ======================================================
# REVERB
# ======================================================

reverb_samples = glitch_samples.copy()

delays = [
    (0.08, 0.24),
    (0.16, 0.18),
    (0.28, 0.12),
    (0.42, 0.08),
    (0.60, 0.05),
]

for delay_seconds, gain in delays:

    delay_samples = int(
        delay_seconds
        * SAMPLE_RATE
    )

    for i in range(
        delay_samples,
        len(glitch_samples)
    ):

        reverb_samples[i] += (
            glitch_samples[
                i - delay_samples
            ]
            * gain
        )


# ======================================================
# FINAL SOFT LIMITER
# ======================================================

for i in range(
    len(reverb_samples)
):

    reverb_samples[i] = math.tanh(
        reverb_samples[i]
        * 0.84
    )


# ======================================================
# CONVERT TO 16-BIT PCM
# ======================================================

frames = []

for sample in reverb_samples:

    sample = clamp(sample)

    pcm = int(
        sample * 32767
    )

    frames.append(
        struct.pack(
            "<h",
            pcm
        )
    )


# ======================================================
# WRITE WAV FILE
# ======================================================

with wave.open(
    str(OUTPUT_FILE),
    "w"
) as wav:

    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(
        SAMPLE_RATE
    )

    wav.writeframes(
        b"".join(frames)
    )


print(
    f"Created: {OUTPUT_FILE}"
)


# ======================================================
# TEST THE SOUND
# ======================================================

print(
    "Playing GLITCH.EXE reactor..."
)

winsound.PlaySound(
    str(OUTPUT_FILE),
    winsound.SND_FILENAME
)

print(
    "Playback finished."
)