"""
make_ui_sounds.py

GLITCH.EXE UI sound bank: reverbed 8-bit grid FX, built to sit inside
the dark grid ambience. Chiptune pulse/triangle voices and an 8-bit
noise channel play short phrases in the same dark D-minor palette as
the ambience, get crushed to a lo-fi bit depth and sample rate, then
wash out into a big, dark digital reverb. Original synthesis.

ONE_SOUND_FOR_ALL_TABS = "ui_home.wav" (default) gives every tab the
8-bit home sound (an octave lower). Set it to None to give each tab its own phrase.
PITCH_SHIFT moves everything down (default two octaves), GLITCH adds
stutters, a crush burst and a reversed grain, and GRID adds the grid
reacting underneath: an electric hum swell, data ticks and a low
scanner glide.

Run it in your audio folder (writes the files GLITCH loads):

    python make_ui_sounds.py

Needs numpy.
"""

import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44100

OUTPUT_DIR = Path(__file__).resolve().parent

# Every tab plays this sound. None = each tab gets its own phrase.
ONE_SOUND_FOR_ALL_TABS = "ui_home.wav"

VOLUME = 0.55           # peak level of each sound

PITCH_SHIFT = -12       # semitones: -12 = one octave lower

GLITCH = 0.0            # 0..1 stutters, crush bursts, reversed grains

GRID = 0.0              # 0..1 grid layer: electric hum swell, data ticks,
                        # a low scanner glide (same world as the ambience)

BITS = 5                # 8-bit grit: lower = crunchier (4-6 sounds right)

CRUSH_RATE = 11025      # lo-fi sample rate (lower = grittier)

REVERB = 0.65           # 0..1 wet amount (matches the ambience's space)

REVERB_SECONDS = 1.4    # length of the reverb tail

DARK = 0.7              # 0..1 darker reverb + softer top end

STEP = 0.032            # seconds per arpeggio step (8-bit speed)

SEED = 404


NOTES = {
    "D4": 293.66, "F4": 349.23, "G4": 392.00, "A4": 440.00, "Bb4": 466.16,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46, "G5": 783.99,
    "G#5": 830.61, "A5": 880.00, "C6": 1046.50, "D6": 1174.66, "E6": 1318.51,
}

# Each sound is a list of events:
#   ("pulse", note, steps, duty)     square-ish chip voice (duty 0.125/0.25/0.5)
#   ("tri", note, steps)             soft triangle (bass)
#   ("slide", from, to, steps, duty) pitch slide
#   ("noise", steps, short)          8-bit noise hit (short=True: metallic tick)
#   ("rest", steps)
# Events run one after another; ("+", event) layers on top of the previous.
SOUNDS = {
    "ui_home.wav":     [("pulse", "D5", 1, 0.25), ("pulse", "F5", 1, 0.25), ("pulse", "A5", 1, 0.25), ("pulse", "D6", 3, 0.25)],
    "ui_chat.wav":     [("pulse", "A5", 1, 0.125), ("rest", 1), ("pulse", "E6", 3, 0.125)],
    "ui_create.wav":   [("slide", "C5", "C6", 4, 0.25), ("pulse", "E6", 1, 0.125), ("pulse", "C6", 2, 0.125)],
    "ui_search.wav":   [("pulse", "C6", 1, 0.25), ("pulse", "A5", 1, 0.25), ("pulse", "F5", 1, 0.25), ("pulse", "C6", 2, 0.125)],
    "ui_code.wav":     [("noise", 1, True), ("pulse", "D5", 1, 0.5), ("rest", 1), ("pulse", "D5", 1, 0.5), ("+", ("noise", 1, True)), ("pulse", "A4", 2, 0.25)],
    "ui_apps.wav":     [("pulse", "D5", 1, 0.25), ("pulse", "A5", 1, 0.25), ("pulse", "D5", 1, 0.25), ("pulse", "A5", 2, 0.25)],
    "ui_settings.wav": [("tri", "D4", 4), ("+", ("pulse", "F4", 1, 0.5)), ("pulse", "A4", 3, 0.25)],
    "ui_system.wav":   [("pulse", "A4", 1, 0.25), ("pulse", "C5", 1, 0.25), ("pulse", "E5", 3, 0.25)],
    "ui_security.wav": [("noise", 2, False), ("+", ("slide", "G#5", "D5", 3, 0.5)), ("pulse", "D5", 2, 0.125)],
    "ui_career.wav":   [("pulse", "G4", 1, 0.25), ("pulse", "Bb4", 1, 0.25), ("pulse", "D5", 1, 0.25), ("pulse", "G5", 3, 0.25)],
}


rate = SAMPLE_RATE


# ======================================================
# CHIP VOICES
# ======================================================

def step_len(steps):

    return int(steps * STEP * rate)


def chip_env(length, release=0.6):

    x = np.arange(length) / max(1, length)

    attack = np.minimum(1, np.arange(length) / (0.002 * rate))

    decay = np.where(x < 1 - release, 1.0, np.cos((x - (1 - release)) / release * np.pi / 2) ** 2)

    return attack * decay


def pulse(freq, length, duty):

    phase = np.cumsum(np.broadcast_to(freq, (length,)) / rate)

    return np.where((phase % 1.0) < duty, 1.0, -1.0) * chip_env(length) * 0.5


def triangle(freq, length):

    phase = np.cumsum(np.broadcast_to(freq, (length,)) / rate)

    tri = 2 * np.abs(2 * (phase % 1.0) - 1) - 1

    tri = np.round(tri * 8) / 8          # NES-style stepped triangle

    return tri * chip_env(length, 0.5) * 0.6


def noise(length, short):

    """8-bit noise channel (15-bit LFSR); short=True is the metallic mode."""

    register = 1

    period = 8 if short else 4

    out = np.empty(length)

    value = 1.0

    for i in range(length):

        if i % period == 0:

            tap = 6 if short else 1

            bit = (register ^ (register >> tap)) & 1

            register = (register >> 1) | (bit << 14)

            value = 1.0 if register & 1 else -1.0

        out[i] = value

    return out * chip_env(length, 0.8) * 0.3


def note_hz(name):

    return NOTES[name] * 2 ** (PITCH_SHIFT / 12)


def render_event(event):

    kind = event[0]

    if kind == "pulse":

        _, note, steps, duty = event

        return pulse(note_hz(note), step_len(steps), duty)

    if kind == "tri":

        _, note, steps = event

        return triangle(note_hz(note), step_len(steps))

    if kind == "slide":

        _, start, end, steps, duty = event

        length = step_len(steps)

        freq = note_hz(start) * (NOTES[end] / NOTES[start]) ** (np.arange(length) / length)

        return pulse(freq, length, duty)

    if kind == "noise":

        _, steps, short = event

        return noise(step_len(steps), short)

    return np.zeros(step_len(event[1]))


def render_phrase(events):

    out = np.zeros(int(4 * rate))

    cursor = 0

    last_start = 0

    part = np.zeros(0)

    for event in events:

        layered = event[0] == "+"

        if layered:

            event = event[1]

        part = render_event(event)

        start = last_start if layered else cursor

        out[start: start + len(part)] += part

        if not layered:

            last_start = cursor

            cursor += len(part)

    end = max(cursor, last_start + len(part))

    return out[:end]


# ======================================================
# LO-FI + REVERB
# ======================================================

def crush(signal):

    hold = max(1, int(round(rate / CRUSH_RATE)))

    held = np.repeat(signal[::hold], hold)[: len(signal)]

    held = np.pad(held, (0, len(signal) - len(held)), mode="edge")

    levels = 2 ** (BITS - 1)

    return np.round(held * levels) / levels


def soften(signal, cutoff):

    alpha = 1 - np.exp(-2 * np.pi * cutoff / rate)

    out = np.empty_like(signal)

    state = 0.0

    for i in range(len(signal)):

        state += alpha * (signal[i] - state)

        out[i] = state

    return out


def dark_reverb(signal, seconds, seed):

    ir_rng = np.random.default_rng(seed)

    length = int(seconds * rate)

    ir = ir_rng.normal(0, 1, length) * np.exp(-np.arange(length) / (rate * seconds / 5.5))

    ir[: int(0.012 * rate)] = 0

    spectrum = np.fft.rfft(ir)

    freqs = np.fft.rfftfreq(length, 1 / rate)

    spectrum *= 1 / (1 + (freqs / (6000 * (1 - 0.75 * DARK) + 400)) ** 2)

    ir = np.fft.irfft(spectrum, length)

    ir /= np.sqrt(np.sum(ir ** 2))

    total = len(signal) + length

    size = 1 << int(np.ceil(np.log2(total)))

    wet = np.fft.irfft(np.fft.rfft(signal, size) * np.fft.rfft(ir, size), size)

    return wet[:total]


def glitchify(signal, seed):

    """Digital damage: retriggered stutters, a heavy crush burst and a
    reversed grain. Every edit is windowed, so it glitches without
    clicking."""

    if GLITCH <= 0 or len(signal) < rate * 0.05:

        return signal

    rng = np.random.default_rng(seed)

    out = signal.copy()

    length = len(out)

    # 1) Stutter: the opening blip retriggers fast ("a-a-a-...").
    grain = int(0.022 * rate)

    repeats = 2 + int(round(2 * GLITCH))

    piece = signal[:grain] * np.hanning(grain)

    stutter = np.concatenate([piece * (0.9 ** k) for k in range(repeats)])

    out = np.concatenate([stutter, out])

    length = len(out)

    # 2) Crush burst: a short stretch drops to 3-bit, low sample rate.
    if GLITCH > 0.3:

        start = int(rng.uniform(0.35, 0.65) * length)

        span = int(rng.uniform(0.025, 0.05) * rate)

        segment = out[start: start + span]

        hold = 14

        held = np.repeat(segment[::hold], hold)[: len(segment)]

        held = np.round(held * 4) / 4

        window = np.hanning(len(segment))

        out[start: start + span] = segment * (1 - window) + held * window

    # 3) Reversed grain near the end of the phrase.
    if GLITCH > 0.5:

        span = int(0.03 * rate)

        start = int(rng.uniform(0.55, 0.8) * length)

        start = min(start, length - span)

        window = np.hanning(span)

        out[start: start + span] = out[start: start + span] * (1 - window) + out[start: start + span][::-1] * window

    return out


def grid_layer(length, seed):

    """The grid itself reacting: a quick electric hum swell, a few data
    ticks and a low scanner glide, all in the ambience's dark D."""

    rng = np.random.default_rng(seed)

    t = np.arange(length) / rate

    # Electric hum (D1/D2 family) that swells in and fades.
    hum = np.zeros(length)

    for freq, gain in ((36.7, 1.0), (73.4, 0.6), (110.0, 0.3), (146.8, 0.15)):

        hum += np.sin(2 * np.pi * freq * t) * gain

    hum *= np.minimum(1, t / 0.035) * np.exp(-t * 4.5) * 0.35

    # Low scanner glide falling under the phrase.
    glide_f = 220 * np.exp(-t * 2.2) + 90

    glide = np.sin(np.cumsum(2 * np.pi * glide_f / rate)) * np.exp(-((t - 0.12) / 0.12) ** 2) * 0.18

    # Data ticks scattered across the first part.
    ticks = np.zeros(length)

    for _ in range(int(3 + 4 * GRID)):

        at = int(rng.uniform(0.0, 0.35) * rate)

        n = int(0.005 * rate)

        if at + n >= length:

            continue

        tt = np.arange(n) / rate

        ticks[at: at + n] += np.sin(2 * np.pi * rng.choice([900, 1200, 1500]) * tt) * np.exp(-tt * 800) * 0.25

    return (hum + glide + ticks) * GRID


def build(events, index):

    phrase = glitchify(render_phrase(events), SEED + 100 + index)

    if GRID > 0:

        padded = np.zeros(len(phrase) + int(0.35 * rate))

        padded[: len(phrase)] = phrase

        phrase = padded + grid_layer(len(padded), SEED + 200 + index)

    dry = soften(crush(phrase), 7000 * (1 - 0.45 * DARK))

    wet = dark_reverb(dry, REVERB_SECONDS, SEED + index)

    out = np.zeros(len(wet))

    out[: len(dry)] += dry * (1 - 0.35 * REVERB)

    out += wet * REVERB * 0.9

    tail = int(0.25 * rate)

    out[-tail:] *= np.linspace(1, 0, tail) ** 2

    level = np.abs(out)

    keep = np.nonzero(level > 0.002 * level.max())[0]

    out = out[: keep[-1] + 1] if len(keep) else out

    return np.tanh(out * 1.3)


def write(filename, signal):

    signal = signal / (np.max(np.abs(signal)) or 1) * VOLUME

    pcm = (np.clip(signal, -1, 1) * 32767).astype("<i2")

    path = OUTPUT_DIR / filename

    with wave.open(str(path), "w") as wav:

        wav.setnchannels(1)

        wav.setsampwidth(2)

        wav.setframerate(rate)

        wav.writeframes(pcm.tobytes())

    print(f"Created: {path.name}  ({len(signal) / rate:.2f} s)")


names = list(SOUNDS)

if ONE_SOUND_FOR_ALL_TABS:

    chosen = ONE_SOUND_FOR_ALL_TABS

    sound = build(SOUNDS[chosen], names.index(chosen))

    for filename in names:

        write(filename, sound)

else:

    for index, filename in enumerate(names):

        write(filename, build(SOUNDS[filename], index))


print("GLITCH.EXE UI sound bank complete (reverbed 8-bit grid).")