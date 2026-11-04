"""
voice/voice_listener.py

GLITCH's ears.

Improvements over the original:

  * Always on. The microphone stays open while GLITCH talks instead of
    being shut off and reopened after every reply, so there's no dead
    half-second where your first words get lost.
  * Barge-in. While GLITCH is speaking you can simply talk over it: if
    the mic hears a voice clearly louder than GLITCH's own echo, it
    emits barge_in (main window stops the speech) and records what you
    say. Works best with headphones; with speakers it self-calibrates
    to the echo level.
  * Pre-roll. The ~0.35 s of audio before speech is detected is kept,
    so the first syllable ("Glitch...") isn't clipped.
  * Adaptive noise floor. The trigger level follows the room's
    background noise (fans, AC) instead of a fixed number.
  * Non-blocking transcription on its own thread, so listening never
    stalls while a sentence is being transcribed.
  * Recognition hints ("GLITCH", "404", ...) so the wake word is heard
    reliably, and filtering of the junk transcripts speech-to-text
    produces from short noises ("Thank you.", "you").

Public interface kept: start(), stop(), transcript_ready,
listening_started, listening_stopped, voice_error.
New: barge_in, user_speaking(bool), set_assistant_speaking(bool),
set_echo_reference(callable).
"""

import io
import os
import queue
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf

from dotenv import load_dotenv
from openai import OpenAI

from PySide6.QtCore import (
    QObject,
    Signal,
)


# Things speech-to-text tends to "hear" in a cough, click or breath.
JUNK_TRANSCRIPTS = {
    "", ".", "you", "you.", "thank you.", "thank you", "thanks.",
    "thanks for watching.", "thanks for watching!", "bye.", "bye",
    "uh", "um", "hmm", "hmm.", "mm", "oh", "ah", "so", "okay.",
}


class VoiceListener(QObject):

    transcript_ready = Signal(str)

    listening_started = Signal()
    listening_stopped = Signal()

    voice_error = Signal(str)

    # You started talking while GLITCH was speaking.
    barge_in = Signal()

    # True when your speech starts, False when it ends (HUD feedback).
    user_speaking = Signal(bool)


    def __init__(self):

        super().__init__()

        load_dotenv()

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:

            raise RuntimeError(
                "OPENAI_API_KEY not found."
            )


        self.client = OpenAI(
            api_key=api_key
        )

        self.transcribe_model = os.getenv(
            "GLITCH_STT_MODEL",
            "gpt-4o-mini-transcribe"
        )

        # Words the recogniser should expect. Add your own in .env as
        # GLITCH_STT_HINTS="Serato, Ableton, ...".
        extra_hints = os.getenv(
            "GLITCH_STT_HINTS",
            "Serato, Spotify, Visual Studio"
        )

        # Written as a sentence: a bare word list is what the recogniser
        # tends to "hear" back on silence or background noise.
        self.recognition_hints = (
            "The user, 404, is talking to their AI assistant named Glitch "
            f"(GLITCH.EXE). Words that may come up: {extra_hints}."
        )

        self._hint_words = {
            word.strip(".,()!?\"'").lower()
            for word in (
                self.recognition_hints
                + " GLITCH, Glitch, 404, GLITCH.EXE, "
                + extra_hints
            ).split()
            if word.strip(".,()!?\"'")
        }

        self.debug = os.getenv("GLITCH_VOICE_DEBUG") == "1"


        self.running = False

        self.sample_rate = 16000

        self.channels = 1

        # 30 ms blocks.
        self.block_size = 480


        # ----------------------------------------------
        # Speech detection
        # ----------------------------------------------

        # Minimum trigger level; the live level is
        # max(energy_threshold, noise_floor * noise_multiplier).
        self.energy_threshold = 0.008

        self.noise_multiplier = 3.0

        # Consecutive loud blocks needed to start (ignores clicks).
        self.start_blocks = 2

        # How long a pause ends your sentence. Lower = GLITCH replies
        # sooner; too low and it may cut you off mid-thought.
        self.silence_seconds = float(
            os.getenv("GLITCH_SILENCE_SECONDS", "0.65")
        )

        self.minimum_speech_seconds = 0.25

        self.maximum_speech_seconds = 25.0

        self.preroll_seconds = 0.35


        # ----------------------------------------------
        # Barge-in (talking over GLITCH)
        # ----------------------------------------------

        self.barge_in_enabled = True

        # Absolute minimum level for barge-in while GLITCH speaks.
        self.barge_in_min_rms = 0.025

        # How much louder than the estimated echo your voice must be.
        self.barge_in_echo_margin = 3.0

        # Margin over GLITCH's own background sound (ambience) when
        # deciding whether YOU started talking.
        self.background_echo_margin = 2.2

        # How long you must keep talking before GLITCH yields.
        self.barge_in_hold_seconds = 0.4

        # Ignore barge-in for the first moment of every GLITCH reply:
        # the room's echo of the first word is the most likely thing
        # to be mistaken for you.
        self.barge_in_grace_seconds = 0.7

        # After GLITCH stops, keep the stricter gate this long so the
        # room's echo tail isn't recorded.
        self.echo_tail_seconds = 0.4


        self._stop_event = None

        self._thread = None

        self._assistant_speaking = False

        self._assistant_stopped_at = 0.0

        self._echo_reference = None

        # Estimated mic level per unit of GLITCH output (speaker -> mic).
        self._echo_coupling = 0.5

        self._assistant_started_at = 0.0

        self._transcribe_queue = queue.Queue()

        self._transcriber = None

    # =====================================================
    # CONFIGURATION FROM THE MAIN WINDOW
    # =====================================================

    def set_assistant_speaking(
        self,
        speaking
    ):

        speaking = bool(speaking)

        if self._assistant_speaking and not speaking:

            self._assistant_stopped_at = time.time()

        if speaking and not self._assistant_speaking:

            self._assistant_started_at = time.time()

        self._assistant_speaking = speaking


    def set_echo_reference(
        self,
        level_function
    ):

        """level_function() -> current RMS of GLITCH's voice output."""

        self._echo_reference = level_function

    # =====================================================
    # START
    # =====================================================

    def start(self):

        if (
            self.running
            and self._thread is not None
            and self._thread.is_alive()
        ):

            print(
                "VOICE LISTENER ALREADY RUNNING"
            )

            return


        print(
            "VOICE LISTENER START REQUESTED"
        )


        self.running = True

        # Each run has its own stop flag, so a slow-to-exit old thread
        # can never keep consuming audio alongside a new one.
        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._listen_loop,
            args=(self._stop_event,),
            daemon=True
        )

        self._thread.start()

        if self._transcriber is None or not self._transcriber.is_alive():

            self._transcriber = threading.Thread(
                target=self._transcribe_loop,
                daemon=True
            )

            self._transcriber.start()

    # =====================================================
    # STOP
    # =====================================================

    def stop(self):

        print(
            "VOICE LISTENER STOP REQUESTED"
        )

        self.running = False

        if self._stop_event is not None:

            self._stop_event.set()

    # =====================================================
    # LISTEN LOOP
    # =====================================================

    def _listen_loop(
        self,
        stop_event
    ):

        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):

            if status and self.debug:

                print("VOICE INPUT STATUS:", status)

            audio_queue.put(indata.copy())

        try:

            print(
                "VOICE LISTENER THREAD STARTED // INPUT DEVICE:",
                sd.default.device
            )

            if self.debug:

                print(sd.query_devices())


            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self.block_size,
                callback=callback,
            ):

                self.listening_started.emit()

                self._run_detector(
                    audio_queue,
                    stop_event
                )

        except Exception as error:

            print(
                "VOICE LISTENER CRASHED:",
                error
            )

            self.voice_error.emit(
                str(
                    error
                )
            )

        finally:

            if self._stop_event is stop_event:

                self.running = False

            print(
                "VOICE LISTENER THREAD STOPPED"
            )

            self.listening_stopped.emit()


    def _run_detector(
        self,
        audio_queue,
        stop_event
    ):

        block_seconds = self.block_size / self.sample_rate

        preroll = deque(
            maxlen=max(1, int(self.preroll_seconds / block_seconds))
        )

        noise_floor = self.energy_threshold / self.noise_multiplier

        recording = []

        speaking = False

        loud_run = 0

        speech_start = 0.0

        last_voice = 0.0

        barge_window = deque(
            maxlen=max(2, int(0.4 / block_seconds))
        )

        # Speech timing runs on the audio's own clock (blocks heard),
        # so a busy CPU or a queue backlog can't distort durations.
        clock = 0.0

        while not stop_event.is_set():

            try:

                chunk = audio_queue.get(timeout=0.25)

            except queue.Empty:

                continue

            rms = float(np.sqrt(np.mean(np.square(chunk))))

            clock += len(chunk) / self.sample_rate

            now = clock

            in_echo_mode = (
                self._assistant_speaking
                or time.time() - self._assistant_stopped_at
                < self.echo_tail_seconds
            )

            # -------------------------------------------------
            # While GLITCH talks: only a clear barge-in counts.
            # -------------------------------------------------

            if in_echo_mode and not speaking:

                preroll.append(chunk)

                in_grace = (
                    time.time() - self._assistant_started_at
                    < self.barge_in_grace_seconds
                )

                if not (self.barge_in_enabled and self._assistant_speaking) or in_grace:

                    barge_window.clear()

                    continue

                output = 0.0

                if self._echo_reference is not None:

                    try:

                        output = float(self._echo_reference())

                    except Exception:

                        output = 0.0

                gate = max(
                    self.barge_in_min_rms,
                    noise_floor * self.noise_multiplier * 1.8,
                    self._echo_coupling * output * self.barge_in_echo_margin,
                )

                loud = rms > gate

                barge_window.append(loud)

                # Learn how much of GLITCH's own voice reaches the mic
                # (only from blocks that don't look like you talking).
                if not loud and output > 0.01:

                    ratio = rms / output

                    rate = 0.05 if ratio > self._echo_coupling else 0.02

                    self._echo_coupling += (ratio - self._echo_coupling) * rate

                    self._echo_coupling = min(max(self._echo_coupling, 0.0), 3.0)

                needed = max(2, int(self.barge_in_hold_seconds / block_seconds))

                if sum(barge_window) >= needed:

                    if self.debug:

                        print(f"BARGE-IN // mic {rms:.4f} gate {gate:.4f}")

                    barge_window.clear()

                    self.barge_in.emit()

                    # Treat GLITCH as silent from here; start recording
                    # you immediately, keeping what was just said.
                    self._assistant_speaking = False

                    self._assistant_stopped_at = 0.0

                    speaking = True

                    speech_start = now - len(preroll) * block_seconds

                    last_voice = now

                    recording = list(preroll)

                    preroll.clear()

                    self.user_speaking.emit(True)

                continue

            # -------------------------------------------------
            # Normal listening.
            # -------------------------------------------------

            # Never more than 2.5x the configured threshold, however
            # noisy the room gets.
            threshold = min(
                max(
                    self.energy_threshold,
                    noise_floor * self.noise_multiplier
                ),
                self.energy_threshold * 2.5
            )

            # Sounds GLITCH itself is playing (background ambience)
            # reach the mic too. Stay above their estimated echo so
            # they never count as you talking.
            output = 0.0

            if self._echo_reference is not None:

                try:

                    output = float(self._echo_reference())

                except Exception:

                    output = 0.0

            if output > 0.0:

                threshold = max(
                    threshold,
                    self._echo_coupling * output * self.background_echo_margin
                )

            if self.debug and rms > threshold * 0.5:

                print(f"MIC LEVEL: {rms:.5f} (threshold {threshold:.5f})")

            loud = rms >= threshold

            if not speaking:

                preroll.append(chunk)

                if loud:

                    loud_run += 1

                else:

                    loud_run = 0

                    # Track the room's background noise: follow it down
                    # quickly, up only slowly, so soft speech can't
                    # gradually raise the trigger above your voice.
                    rate = 0.05 if rms < noise_floor else 0.003

                    noise_floor += (rms - noise_floor) * rate

                    # Keep learning how much of GLITCH's own sound
                    # reaches the mic (from quiet, non-speech blocks).
                    if output > 0.005:

                        ratio = rms / output

                        learn = 0.02 if ratio > self._echo_coupling else 0.005

                        self._echo_coupling += (ratio - self._echo_coupling) * learn

                        self._echo_coupling = min(max(self._echo_coupling, 0.0), 3.0)

                if loud_run >= self.start_blocks:

                    speaking = True

                    loud_run = 0

                    recording = list(preroll)

                    preroll.clear()

                    speech_start = now - len(recording) * block_seconds

                    last_voice = now

                    self.user_speaking.emit(True)

                    print("GLITCH // voice detected")

                continue

            recording.append(chunk)

            if loud:

                last_voice = now

            duration = now - speech_start

            ended = now - last_voice >= self.silence_seconds

            too_long = duration >= self.maximum_speech_seconds

            if not (ended or too_long):

                continue

            speaking = False

            self.user_speaking.emit(False)

            if self.debug:

                print(f"VOICE SEGMENT ENDED // {duration:.2f} sec")

            spoken = duration - (now - last_voice)

            if spoken >= self.minimum_speech_seconds and recording:

                audio = np.concatenate(recording, axis=0)

                self._transcribe_queue.put(
                    (audio, spoken)
                )

            recording = []

    # =====================================================
    # TRANSCRIBE (own thread)
    # =====================================================

    def _is_prompt_echo(
        self,
        text
    ):

        words = [
            word.strip(".,()!?\"'").lower()
            for word in text.split()
            if word.strip(".,()!?\"'")
        ]

        if len(words) < 3:

            return False

        from_hints = sum(1 for word in words if word in self._hint_words)

        ratio = from_hints / len(words)

        # Every word comes from the hint text, or nearly every word in
        # a long string: that's an echo, not you.
        return ratio == 1.0 or (len(words) >= 6 and ratio >= 0.85)


    def _transcribe_loop(self):

        while True:

            audio, spoken = self._transcribe_queue.get()

            try:

                self._transcribe(audio, spoken)

            except Exception as error:

                print("TRANSCRIPTION ERROR:", error)

                self.voice_error.emit(str(error))


    def _transcribe(
        self,
        audio,
        spoken_seconds=1.0
    ):

        buffer = io.BytesIO()

        sf.write(
            buffer,
            audio,
            self.sample_rate,
            format="WAV",
            subtype="PCM_16",
        )

        buffer.seek(0)

        buffer.name = "speech.wav"

        transcript = (
            self.client
            .audio
            .transcriptions
            .create(
                model=self.transcribe_model,
                file=buffer,
                prompt=self.recognition_hints,
            )
        )

        text = (
            (transcript.text or "")
            .strip()
        )

        if text.lower() in JUNK_TRANSCRIPTS and spoken_seconds < 1.2:

            if self.debug:

                print("GLITCH IGNORED (noise):", repr(text))

            return

        if self._is_prompt_echo(text):

            # The recogniser "heard" its own hint text in background
            # noise. Never let that through: it contains "Glitch" and
            # would wake GLITCH by itself.
            if self.debug:

                print("GLITCH IGNORED (prompt echo):", repr(text))

            return

        print("GLITCH HEARD:", repr(text))

        if text:

            self.transcript_ready.emit(
                text
            )