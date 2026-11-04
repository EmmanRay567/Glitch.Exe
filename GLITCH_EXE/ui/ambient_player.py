"""
ui/ambient_player.py

Plays audio/grid_ambience.wav on a seamless loop for as long as GLITCH
is open, with smooth fades and automatic "ducking":

  * fades in when started, fades out when stopped
  * drops to a whisper while GLITCH is talking or while you are
    speaking to it, so it never drowns the voice or confuses the mic
  * volume adjustable at runtime

Uses QSoundEffect, which loads the WAV into memory and loops it
sample-accurately (no gap at the loop point).
"""

import time
import wave
from pathlib import Path

import numpy as np

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtMultimedia import QSoundEffect


class AmbientPlayer(QObject):

    FADE_STEP_MS = 40

    def __init__(self, wav_path, volume=0.35, duck_volume=0.08, parent=None, duck_fade=0.12):

        super().__init__(parent)

        self.path = Path(wav_path)

        self.volume = float(volume)

        self.duck_volume = float(duck_volume)

        self._ducked_reasons = set()

        self.duck_fade = float(duck_fade)

        # Loudness envelope of the loop (20 ms steps), so the voice
        # listener can tell the ambience apart from your voice.
        self._envelope = None

        self._loop_seconds = 0.0

        self._play_started = None

        self._load_envelope()

        self._current = 0.0

        self._target = 0.0

        self._effect = QSoundEffect(self)

        # PySide6 wants a plain int here; QSoundEffect.Loop.Infinite == -2.
        infinite = getattr(QSoundEffect.Loop.Infinite, "value", -2)

        self._effect.setLoopCount(int(infinite))

        self._effect.setVolume(0.0)

        if self.path.exists():

            self._effect.setSource(QUrl.fromLocalFile(str(self.path)))

        else:

            print(f"AMBIENCE // {self.path} not found: run generate_grid_ambience.py")

        self._fade = QTimer(self)

        self._fade.setInterval(self.FADE_STEP_MS)

        self._fade.timeout.connect(self._step)

    # -----------------------------------------------------

    def start(self, fade_seconds=2.5):

        if not self.path.exists():

            return

        if not self._effect.isPlaying():

            self._effect.play()

            self._play_started = time.perf_counter()

        self._fade_to(self._level(), fade_seconds)

    def stop(self, fade_seconds=1.0):

        self._fade_to(0.0, fade_seconds, stop_after=True)

    def set_volume(self, volume):

        self.volume = max(0.0, min(1.0, float(volume)))

        self._fade_to(self._level(), 0.3)

    def duck(self, reason, active):

        """duck("speaking", True) ... duck("speaking", False)."""

        if active:

            self._ducked_reasons.add(reason)

        else:

            self._ducked_reasons.discard(reason)

        if self._effect.isPlaying():

            # Duck fast (gets out of the way before the first word),
            # come back slowly.
            self._fade_to(self._level(), self.duck_fade if active else 1.2)

    def output_level(self):

        """Approximate RMS the ambience is putting out right now
        (0..1). Used as an echo reference by the voice listener."""

        if self._envelope is None or self._play_started is None or not self._effect.isPlaying():

            return 0.0

        position = (time.perf_counter() - self._play_started) % self._loop_seconds

        index = min(len(self._envelope) - 1, int(position / 0.02))

        # Look a little either side: playback timing is approximate.
        window = self._envelope[max(0, index - 3): index + 4]

        return float(window.max()) * self._effect.volume()

    def _load_envelope(self):

        try:

            with wave.open(str(self.path), "rb") as wav:

                rate = wav.getframerate()

                channels = wav.getnchannels()

                frames = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")

            mono = frames.reshape(-1, channels).mean(axis=1) / 32768.0

            step = int(rate * 0.02)

            usable = len(mono) // step * step

            blocks = mono[:usable].reshape(-1, step)

            self._envelope = np.sqrt((blocks ** 2).mean(axis=1))

            self._loop_seconds = len(mono) / rate

        except Exception as error:

            print("AMBIENCE // could not analyse loop:", error)

            self._envelope = None

    # -----------------------------------------------------

    def _level(self):

        return self.duck_volume if self._ducked_reasons else self.volume

    def _fade_to(self, target, seconds, stop_after=False):

        self._target = target

        self._stop_after = stop_after

        steps = max(1, int(seconds * 1000 / self.FADE_STEP_MS))

        self._delta = (target - self._current) / steps

        self._fade.start()

    def _step(self):

        self._current += self._delta

        if (self._delta >= 0 and self._current >= self._target) or (self._delta < 0 and self._current <= self._target):

            self._current = self._target

            self._fade.stop()

            if self._stop_after and self._current <= 0.0:

                self._effect.stop()

        self._effect.setVolume(max(0.0, min(1.0, self._current)))