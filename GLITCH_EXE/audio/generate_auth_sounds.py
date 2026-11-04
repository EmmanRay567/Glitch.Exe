"""
generate_auth_sounds.py

The three biometric-scanner result sounds for GLITCH.EXE:

  auth_granted.wav   it's you (green / cyan)
                     the grid powering on, Tron style: a light-cycle
                     riser streaks past, a sub drop and disc zap hit,
                     then a big glossy detuned-saw chord opens up over
                     a pulsing octave bassline and glassy grid bleeps

  auth_denied.wav    not you / locked out (red)
                     a red lightsaber: ignition snap, then a low, angry,
                     unstable hum (cracked-crystal crackle, a slow swing)
                     that powers down

  auth_unknown.wav   no face / couldn't confirm (yellow)
                     an "unknown" query: two unresolved tones that bend
                     up like a question, then stutter and glitch out

Run it in your audio folder:

    python generate_auth_sounds.py

Writes the three WAVs next to this file (stereo, 16-bit, 44.1 kHz).
Needs numpy. Tweak the settings below and re-run to change them.
"""

import wave
from pathlib import Path

import numpy as np

try:
    import winsound
except ImportError:
    winsound = None


SAMPLE_RATE = 44100

OUT_DIR = Path(__file__).parent

# Set to "granted", "denied" or "unknown" to hear one after generating.
PREVIEW = "granted"


GRANTED = {
    "RISER": 0.5,         # seconds of light-cycle riser before the grid hits
    "TEMPO": 128,         # BPM of the pulsing bass / bleeps
    "CHORD": [146.83, 220.0, 293.66, 329.63, 369.99, 440.0],   # D add9 (heroic)
    "BRIGHTNESS": 0.75,   # 0..1 how far the synth filter opens
    "PULSE": 0.6,         # 0..1 how hard the chord pumps on the 16ths
    "BASS": 0.8,          # 0..1 pulsing octave bass level
    "BASS_STEPS": 8,      # how many 16th notes the bass pulses
    "CYCLE": 0.8,         # 0..1 light-cycle riser level
    "BLEEPS": 0.8,        # 0..1 grid bleeps level
    "REVERB": 0.4,        # 0..1
    "VOLUME": 0.6,        # peak level
    "SEED": 404,
}

DENIED = {
    "PITCH": 78.0,        # hum frequency (Hz); lower = more sinister
    "AGGRESSION": 0.7,    # 0..1 distortion / buzz
    "CRACKLE": 0.65,      # 0..1 unstable-crystal crackle
    "LENGTH": 2.1,        # seconds
    "REVERB": 0.25,
    "VOLUME": 0.32,
    "SEED": 66,
}

UNKNOWN = {
    "NOTE_1": 440.0,      # first tone (Hz)
    "NOTE_2": 622.25,     # second tone: a tritone up (unresolved)
    "BEND": 2.0,          # semitones the second tone bends up ("?")
    "GLITCH": 0.6,        # 0..1 stutter / bit crush at the end
    "REVERB": 0.4,
    "VOLUME": 0.55,
    "SEED": 7,
}


# =========================================================
# HELPERS
# =========================================================

def timeline(seconds):

    return np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE


def onepole_lowpass(signal, cutoff):

    """Simple one-pole low-pass; cutoff may be a per-sample array."""

    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), signal.shape)

    alpha = 1.0 - np.exp(-2 * np.pi * np.clip(cutoff, 10, SAMPLE_RATE / 2.2) / SAMPLE_RATE)

    out = np.empty_like(signal)

    y = 0.0

    for i in range(len(signal)):

        y += alpha[i] * (signal[i] - y)

        out[i] = y

    return out


def highpass(signal, cutoff):

    return signal - onepole_lowpass(signal, cutoff)


def reverb(signal, seconds, seed):

    """Decaying-noise convolution reverb (stereo-decorrelated)."""

    rng = np.random.default_rng(seed)

    length = int(seconds * SAMPLE_RATE)

    out = []

    for _ in range(2):

        ir = rng.normal(0, 1, length) * np.exp(-np.arange(length) / (SAMPLE_RATE * seconds / 5.0))

        ir[: int(0.015 * SAMPLE_RATE)] = 0

        ir /= np.sqrt(np.sum(ir ** 2))

        size = 1 << int(np.ceil(np.log2(len(signal) + length)))

        wet = np.fft.irfft(np.fft.rfft(signal, size) * np.fft.rfft(ir, size), size)

        out.append(wet[: len(signal)])

    return np.stack(out, axis=1)


def bitcrush(signal, bits=6, hold=4):

    """Fewer bits + sample-and-hold = 8-bit grit."""

    held = np.repeat(signal[::hold], hold)[: len(signal)]

    steps = 2 ** (bits - 1)

    return np.round(held * steps) / steps


def pan(mono, position):

    """position -1 (left) .. +1 (right), equal power."""

    angle = (position + 1) * np.pi / 4

    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)


def place(target, sound, start):

    i = int(start * SAMPLE_RATE)

    end = min(len(target), i + len(sound))

    if end > i:

        target[i:end] += sound[: end - i]


def finish(stereo, volume, tail_fade=0.08):

    fade = int(tail_fade * SAMPLE_RATE)

    stereo[-fade:] *= np.linspace(1, 0, fade)[:, None]

    stereo[: 64] *= np.linspace(0, 1, 64)[:, None]

    stereo = np.tanh(stereo * 1.1)

    return stereo * volume / (np.max(np.abs(stereo)) or 1)


def write(name, stereo):

    path = OUT_DIR / name

    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")

    with wave.open(str(path), "w") as wav:

        wav.setnchannels(2)

        wav.setsampwidth(2)

        wav.setframerate(SAMPLE_RATE)

        wav.writeframes(pcm.tobytes())

    print(f"Created: {path}  ({len(stereo) / SAMPLE_RATE:.1f} s)")

    return path


# =========================================================
# GRANTED: Tron grid power-up
# =========================================================

def svf_lowpass(signal, cutoff, resonance=0.3):

    """Resonant 2-pole low-pass (the classic analog-synth sweep)."""

    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), signal.shape)

    f = 2 * np.sin(np.pi * np.clip(cutoff, 20, SAMPLE_RATE / 6) / SAMPLE_RATE)

    q = 1.0 - resonance

    low = band = 0.0

    out = np.empty_like(signal)

    for i in range(len(signal)):

        high = signal[i] - low - q * band

        band += f[i] * high

        low += f[i] * band

        out[i] = low

    return out


def supersaw(freq, t, voices=5, spread=0.012, seed=0):

    """Several detuned saws per note: the big glossy grid synth."""

    rng = np.random.default_rng(seed)

    total = np.zeros_like(t)

    for v in range(voices):

        detune = 1 + spread * (v - (voices - 1) / 2) / ((voices - 1) / 2 or 1)

        total += 2 * ((freq * detune * t + rng.random()) % 1.0) - 1

    return total / voices


def make_granted():

    cfg = GRANTED

    rng = np.random.default_rng(cfg["SEED"])

    hit = cfg["RISER"]                       # the moment the grid switches on

    step = 60.0 / cfg["TEMPO"] / 4           # one 16th note

    total = hit + 2.3

    n = int(total * SAMPLE_RATE)

    t = np.arange(n) / SAMPLE_RATE

    out = np.zeros((n, 2))

    # ---- 1. light-cycle riser: a buzzing engine streaking past L -> R
    tr = timeline(hit + 0.06)

    progress = tr / tr[-1]

    pitch = 55 * (1 + 1.7 * progress ** 1.6)

    phase = np.cumsum(pitch) / SAMPLE_RATE

    engine = 2 * (phase % 1.0) - 1

    engine *= 0.75 + 0.25 * np.sin(2 * np.pi * (25 + 45 * progress) * tr)   # bike buzz

    engine = svf_lowpass(engine, 250 + 3200 * progress ** 2, 0.45)

    whoosh = onepole_lowpass(rng.normal(0, 1, len(tr)), 400 + 7000 * progress ** 2)

    riser = (engine * 0.5 + whoosh * 0.18) * progress ** 1.8 * cfg["CYCLE"]

    for k, side in enumerate((-1, 1)):

        out[: len(tr), k] += riser * np.sqrt(0.5 + 0.5 * side * (2 * progress - 1))

    # ---- 2. impact: sub drop + a "disc" zap sweeping down
    tz = timeline(0.5)

    sub = np.sin(2 * np.pi * np.cumsum(42 + 70 * np.exp(-tz * 22)) / SAMPLE_RATE) * np.exp(-tz * 6)

    place(out, pan(sub * 0.9, 0), hit)

    tz = timeline(0.12)

    zap_f = 3200 * np.exp(-tz * 28) + 180

    zap = np.sign(np.sin(2 * np.pi * np.cumsum(zap_f) / SAMPLE_RATE)) * np.exp(-tz * 26)

    place(out, pan(onepole_lowpass(zap, 5000) * 0.18, 0), hit)

    # ---- 3. the grid powers on: big supersaw chord, filter opening
    ta = np.clip(t - hit, 0, None)

    on = (t >= hit).astype(float)

    chord = cfg["CHORD"]

    amp = on * np.clip(ta / 0.015, 0, 1) * np.exp(-np.clip(ta - 0.25, 0, None) * 1.3)

    cutoff = 350 + cfg["BRIGHTNESS"] * 5200 * np.clip(ta / 0.3, 0, 1) ** 0.7 * np.exp(-np.clip(ta - 0.35, 0, None) * 1.4)

    # Pump on every 16th, like the pulsing grid.
    pump = 1 - cfg["PULSE"] * 0.5 * np.exp(-((ta % step) / 0.035))

    for side in range(2):

        pad = sum(
            supersaw(freq, t, seed=cfg["SEED"] + side * 31 + i)
            for i, freq in enumerate(chord)
        ) / len(chord)

        pad = svf_lowpass(pad, cutoff, 0.35)

        out[:, side] += pad * amp * pump * 0.9

    # ---- 4. pulsing octave bassline (D2 / D3 on 16ths)
    root = chord[0] / 2

    for k in range(cfg["BASS_STEPS"]):

        tb = timeline(step * 0.9)

        freq = root * (2 if k % 2 else 1)

        note = supersaw(freq, tb, voices=3, spread=0.006, seed=k)

        note = svf_lowpass(note, 300 + 1800 * np.exp(-tb * 30), 0.4)

        note *= np.clip(tb / 0.004, 0, 1) * np.exp(-tb * 9)

        fade = 1 - 0.6 * k / cfg["BASS_STEPS"]

        place(out, pan(note * 0.5 * cfg["BASS"] * fade, 0), hit + k * step)

    # ---- 5. glassy grid bleeps bouncing left / right
    bleeps = [(2, 1760.0), (3, 1318.51), (5, 2349.32), (7, 1760.0), (10, 2959.96)]

    for k, (index, freq) in enumerate(bleeps):

        tb = timeline(0.09)

        bleep = np.sign(np.sin(2 * np.pi * freq * tb)) * 0.5 + np.sin(2 * np.pi * freq * 2 * tb) * 0.5

        bleep = onepole_lowpass(bleep, 6000) * np.exp(-tb * 38)

        place(out, pan(bleep * 0.11 * cfg["BLEEPS"], -0.8 if k % 2 else 0.8), hit + index * step)

        # Grid echo.
        place(out, pan(bleep * 0.05 * cfg["BLEEPS"], 0.8 if k % 2 else -0.8), hit + index * step + step * 1.5)

    # ---- the big digital space
    mono = out.mean(axis=1)

    out += reverb(mono, 2.4, cfg["SEED"]) * cfg["REVERB"]

    return finish(out, cfg["VOLUME"], tail_fade=0.15)


# =========================================================
# DENIED: red lightsaber hum
# =========================================================

def make_denied():

    cfg = DENIED

    rng = np.random.default_rng(cfg["SEED"])

    length = cfg["LENGTH"]

    t = timeline(length)

    n = len(t)

    f0 = cfg["PITCH"]

    # ---- pitch: ignition rise, a slow menacing swing, power-down drop
    ignite = 0.16

    swing = np.exp(-((t - length * 0.45) / 0.22) ** 2)      # one slow swing

    pitch = f0 * (
        0.55 + 0.45 * (1 - np.exp(-np.clip(t, 0, None) / (ignite / 3)))
    ) * (1 + 0.07 * swing)

    retract = length - 0.35

    pitch *= 1 - 0.45 * np.clip((t - retract) / 0.35, 0, 1) ** 1.5

    # Unstable crystal: the pitch never sits still.
    jitter = onepole_lowpass(rng.normal(0, 1, n), 8) * 0.9

    pitch *= 1 + 0.012 * jitter

    phase = 2 * np.pi * np.cumsum(pitch) / SAMPLE_RATE

    # ---- the hum: detuned saws (beating), a motor sine, a buzz
    saw_a = 2 * ((phase / (2 * np.pi)) % 1.0) - 1

    saw_b = 2 * ((phase * 1.013 / (2 * np.pi)) % 1.0) - 1

    motor = np.sin(phase) + 0.5 * np.sin(2 * phase + 0.3)

    buzz = np.sign(np.sin(3 * phase)) * 0.35

    hum = 0.45 * (saw_a + saw_b) + 0.8 * motor + cfg["AGGRESSION"] * buzz

    # Brighter while swinging, darker at rest.
    hum = onepole_lowpass(hum, 900 + 1800 * swing + 600 * cfg["AGGRESSION"])

    hum = np.tanh(hum * (0.9 + 1.4 * cfg["AGGRESSION"])) * 0.9

    # ---- crackle: the cracked-crystal spit and fizz
    crackle = np.zeros(n)

    count = int(cfg["CRACKLE"] * 26 * length)

    for _ in range(count):

        start = rng.uniform(0.05, length - 0.3)

        size = int(rng.uniform(0.004, 0.03) * SAMPLE_RATE)

        i = int(start * SAMPLE_RATE)

        grain = rng.normal(0, 1, size) * np.exp(-np.linspace(0, 6, size))

        crackle[i:i + size] += grain * rng.uniform(0.3, 1.0)

    crackle = highpass(crackle, 2500) * cfg["CRACKLE"] * 0.45

    # Crackle also chokes the hum for a split second.
    choke = 1 - 0.35 * np.clip(onepole_lowpass(np.abs(crackle), 40) * 6, 0, 1)

    # ---- ignition snap-hiss
    snap = np.zeros(n)

    k = int(0.22 * SAMPLE_RATE)

    hiss = rng.normal(0, 1, k) * np.exp(-np.linspace(0, 7, k))

    snap[:k] = onepole_lowpass(hiss, np.linspace(9000, 1500, k)) * 0.9

    # ---- envelope: punch in, sustain, power down
    env = np.clip(t / 0.03, 0, 1)

    env *= np.where(t > retract, np.clip(1 - (t - retract) / 0.35, 0, 1) ** 1.3, 1.0)

    env *= 0.85 + 0.15 * swing

    mono = hum * env * choke + crackle * env + snap

    # Width: right channel very slightly delayed + its own crackle.
    delay = int(0.0006 * SAMPLE_RATE)

    right = np.concatenate([np.zeros(delay), mono[:-delay]])

    out = np.stack([mono, right], axis=1)

    out += reverb(mono, 1.2, cfg["SEED"]) * cfg["REVERB"]

    return finish(out, cfg["VOLUME"], tail_fade=0.05)


# =========================================================
# UNKNOWN: unresolved query
# =========================================================

def make_unknown():

    cfg = UNKNOWN

    rng = np.random.default_rng(cfg["SEED"])

    total = 1.5

    out = np.zeros((int(total * SAMPLE_RATE), 2))

    def tone(freq_curve, seconds):

        t = timeline(seconds)

        f = np.broadcast_to(freq_curve(t), t.shape)

        vibrato = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t)

        phase = 2 * np.pi * np.cumsum(f * vibrato) / SAMPLE_RATE

        # Soft square/triangle mix: digital but not harsh.
        triangle = 2 / np.pi * np.arcsin(np.sin(phase))

        square = np.tanh(3 * np.sin(phase))

        wave_ = 0.6 * triangle + 0.4 * square

        env = np.clip(t / 0.012, 0, 1) * np.exp(-t * 3.2)

        return onepole_lowpass(wave_ * env, 2600)

    # ---- note 1: a short questioning tone
    first = tone(lambda t: cfg["NOTE_1"] * np.ones_like(t), 0.22)

    place(out, pan(first * 0.32, -0.25), 0.0)

    # ---- note 2: tritone up, then bends upward at the end like "?"
    bend = 2 ** (cfg["BEND"] / 12)

    def rising(t):

        lift = np.clip((t - 0.12) / 0.2, 0, 1) ** 2

        return cfg["NOTE_2"] * (1 + (bend - 1) * lift)

    second = tone(rising, 0.42)

    place(out, pan(second * 0.32, 0.25), 0.2)

    # ---- glitch: stutter a slice of the bend, crushed, fading away
    if cfg["GLITCH"] > 0:

        grain = second[int(0.24 * SAMPLE_RATE): int(0.285 * SAMPLE_RATE)]

        grain = grain * np.hanning(len(grain))

        for r in range(4):

            crushed = (1 - cfg["GLITCH"]) * grain + cfg["GLITCH"] * bitcrush(grain, 5 - r % 2, 3 + r)

            place(out, pan(crushed * 0.3 * 0.62 ** r, 0.6 if r % 2 else -0.6), 0.64 + r * 0.06)

    # ---- low scanning murmur underneath (searching... nothing)
    t = timeline(0.9)

    murmur = onepole_lowpass(rng.normal(0, 1, len(t)), 300 + 500 * np.sin(np.pi * t / t[-1]))

    murmur *= np.sin(np.pi * t / t[-1]) ** 2 * 0.25

    place(out, pan(murmur, 0), 0.0)

    mono = out.mean(axis=1)

    out += reverb(mono, 1.3, cfg["SEED"]) * cfg["REVERB"]

    return finish(out, cfg["VOLUME"])


# =========================================================

if __name__ == "__main__":

    files = {
        "granted": write("auth_granted.wav", make_granted()),
        "denied": write("auth_denied.wav", make_denied()),
        "unknown": write("auth_unknown.wav", make_unknown()),
    }

    if winsound is not None and PREVIEW in files:

        winsound.PlaySound(str(files[PREVIEW]), winsound.SND_FILENAME)
