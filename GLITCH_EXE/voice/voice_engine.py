"""
voice/voice_engine.py

GLITCH's voice.

Old flow:  wait for the whole AI reply -> render the whole reply to a WAV
           -> save -> play. Long replies meant several seconds of silence.

New flow:  text arrives (all at once via speak(), or word-by-word while
           the AI is still thinking via begin_stream()/feed()/end_stream())
           -> it is cut into sentences -> each sentence is sent to TTS as
           soon as it is complete -> audio is STREAMED straight to the
           speakers while the next sentence is already being rendered.

GLITCH starts talking after the first sentence instead of after the
whole answer, can be cut off instantly (stop(), or by talking over it via
VoiceListener's barge-in), and exposes its live output level so the
listener can tell your voice apart from its own echo.

Public interface kept: speak(text), stop(), speech_started,
speech_finished, voice_error.
"""

import os
import queue
import re
import threading
import time

import numpy as np
import sounddevice as sd

from dotenv import load_dotenv
from openai import OpenAI

from PySide6.QtCore import (
    QObject,
    Signal,
)


load_dotenv()


SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]*(?=\s)|\n+")


def _clean_for_speech(text):

    """Remove things a person wouldn't say out loud."""

    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)

    text = re.sub(r"https?://\S+", "the link on screen", text)

    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)

    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)

    text = text.replace("**", "").replace("__", "").replace("`", "")

    text = re.sub(r"(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", text)

    return re.sub(r"\s+", " ", text).strip()


class VoiceEngine(QObject):

    # Legacy signal (the old WAV pipeline). Kept so old connections
    # don't break; no longer emitted.
    audio_ready = Signal(str)

    speech_started = Signal()
    speech_finished = Signal()

    voice_error = Signal(str)

    # Internal: worker threads report here; the slots run on the Qt
    # thread and decide (by generation number) whether the public
    # speech_started / speech_finished signals should fire. This keeps
    # "started" and "finished" strictly paired and in order, so the
    # main window can never get stuck thinking GLITCH is still talking.
    _playback_started = Signal(int)
    _playback_ended = Signal(int)

    SAMPLE_RATE = 24000

    # Very short sentences ("Sir." / "Right.") are merged with the next
    # one so the voice doesn't sound chopped up.
    MIN_CHUNK_CHARS = 28

    def __init__(self):

        super().__init__()

        # ==================================================
        # OPENAI
        # ==================================================

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY was not found in .env"
            )

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = os.getenv(
            "GLITCH_TTS_MODEL",
            "gpt-4o-mini-tts"
        )

        # ==================================================
        # GLITCH VOICE
        # ==================================================

        self.voice = os.getenv(
            "GLITCH_VOICE",
            "onyx"
        )

        self.instructions = """
You are the voice of GLITCH, a personal AI talking with the person who
built it. You know them well. This is a conversation, not an announcement.

Delivery:
- medium-low register, calm and controlled, crisp articulation
- warm, quietly confident, never arrogant
- natural conversational pace: a touch quicker on routine replies,
  slower and more deliberate on anything important
- let dry humour land through understatement and timing, not by
  changing voice
- natural small pauses at commas and between sentences, like someone
  thinking while they speak
- when addressing them as "sir", say it lightly, not formally
- a subtle polished, slightly synthetic sheen; never robotic, never
  sing-song, never like a radio announcer

GLITCH has its own identity. Do not imitate any existing fictional AI
character.
"""

        # ==================================================
        # INTERNAL STATE
        # ==================================================

        self._lock = threading.RLock()

        # Every utterance gets a generation number; bumping it cancels
        # whatever older threads are still doing.
        self._generation = 0

        self._text_queue = None

        self._buffer = ""

        self._in_code_block = False

        self._code_announced = False

        self._first_chunk = True

        self._stream = None

        self._speaking = False

        self._active = False

        self._level = 0.0

        self._level_time = 0.0

        # What the outside world has been told (speech_started sent
        # without a matching speech_finished yet).
        self._public_speaking = False

        self._playback_started.connect(
            self._on_playback_started
        )

        self._playback_ended.connect(
            self._on_playback_ended
        )

        print(
            f"GLITCH VOICE // ready (voice={self.voice}, model={self.model})"
        )

    # ======================================================
    # PUBLIC API
    # ======================================================

    def speak(
        self,
        text
    ):

        """Say a complete piece of text (interrupts anything playing)."""

        if not text or not str(text).strip():
            return

        self.begin_stream()

        self.feed(str(text))

        self.end_stream()


    def begin_stream(self):

        """Start an utterance whose text will arrive in pieces."""

        self._cancel(emit_finished=True)

        with self._lock:

            self._generation += 1

            generation = self._generation

            self._text_queue = queue.Queue()

            self._buffer = ""

            self._in_code_block = False

            self._code_announced = False

            self._first_chunk = True

            self._active = True

            text_queue = self._text_queue

        pcm_queue = queue.Queue(maxsize=400)

        threading.Thread(
            target=self._produce_audio,
            args=(generation, text_queue, pcm_queue),
            daemon=True,
        ).start()

        threading.Thread(
            target=self._play_audio_stream,
            args=(generation, pcm_queue),
            daemon=True,
        ).start()


    def feed(
        self,
        text
    ):

        """Add more text to the current utterance (e.g. AI deltas)."""

        if not text:
            return

        with self._lock:

            if self._text_queue is None:

                return

            self._buffer += self._strip_code(text)

            self._emit_complete_sentences(final=False)


    def end_stream(self):

        """No more text is coming; speak whatever is left."""

        with self._lock:

            if self._text_queue is None:

                return

            self._emit_complete_sentences(final=True)

            self._text_queue.put(None)

            self._text_queue = None


    def stop(
        self
    ):

        """Stop talking immediately."""

        self._cancel(emit_finished=True)


    def is_speaking(self):

        return self._speaking


    def output_level(self):

        """RMS (0..1) of what GLITCH is playing right now. Used by the
        listener to tell your voice apart from GLITCH's own echo."""

        if time.time() - self._level_time > 0.2:

            return 0.0

        return self._level

    # ======================================================
    # TEXT -> SENTENCE CHUNKS
    # ======================================================

    def _strip_code(
        self,
        text
    ):

        """Don't read code aloud. Point at the screen instead."""

        out = []

        pieces = text.split("```")

        for index, piece in enumerate(pieces):

            if index > 0:

                self._in_code_block = not self._in_code_block

                if self._in_code_block and not self._code_announced:

                    self._code_announced = True

                    out.append(" I've put the code on screen. ")

            if not self._in_code_block:

                out.append(piece)

        return "".join(out)


    def _emit_complete_sentences(
        self,
        final
    ):

        while True:

            match = SENTENCE_END.search(self._buffer)

            if not match:

                break

            end = match.end()

            candidate = self._buffer[:end]

            # Merge tiny sentences with the next one (except the very
            # first, which should play as fast as possible).
            if (
                not self._first_chunk
                and len(candidate.strip()) < self.MIN_CHUNK_CHARS
                and not final
            ):

                next_match = SENTENCE_END.search(self._buffer, end)

                if not next_match:

                    break

                end = next_match.end()

                candidate = self._buffer[:end]

            self._buffer = self._buffer[end:]

            self._queue_chunk(candidate)

        if final:

            leftover = self._buffer

            self._buffer = ""

            self._queue_chunk(leftover)


    def _queue_chunk(
        self,
        text
    ):

        cleaned = _clean_for_speech(text)

        if not cleaned or not re.search(r"\w", cleaned):

            return

        self._first_chunk = False

        self._text_queue.put(cleaned)

    # ======================================================
    # TTS PRODUCER (network -> PCM queue)
    # ======================================================

    def _current(
        self,
        generation
    ):

        return generation == self._generation


    def _produce_audio(
        self,
        generation,
        text_queue,
        pcm_queue
    ):

        try:

            while self._current(generation):

                try:

                    chunk = text_queue.get(timeout=0.25)

                except queue.Empty:

                    continue

                if chunk is None:

                    break

                print(f"GLITCH VOICE // speaking: {chunk[:60]!r}")

                with (
                    self.client.audio.speech
                    .with_streaming_response
                    .create(
                        model=self.model,
                        voice=self.voice,
                        input=chunk,
                        instructions=self.instructions,
                        response_format="pcm",
                    )
                ) as response:

                    leftover = b""

                    for data in response.iter_bytes(4800):

                        if not self._current(generation):

                            break

                        data = leftover + data

                        cut = len(data) - (len(data) % 2)

                        leftover = data[cut:]

                        if cut and not self._put(
                            pcm_queue, data[:cut], generation
                        ):

                            break

        except Exception as error:

            if self._current(generation):

                print(f"GLITCH VOICE ERROR: {error}")

                self.voice_error.emit(str(error))

        finally:

            try:

                pcm_queue.put(None, timeout=1.0)

            except queue.Full:

                pass


    def _put(
        self,
        target_queue,
        item,
        generation
    ):

        """Blocking put that gives up if the utterance is cancelled."""

        while self._current(generation):

            try:

                target_queue.put(item, timeout=0.2)

                return True

            except queue.Full:

                continue

        return False

    # ======================================================
    # PLAYBACK CONSUMER (PCM queue -> speakers)
    # ======================================================

    def _play_audio_stream(
        self,
        generation,
        pcm_queue
    ):

        stream = None

        rate = self.SAMPLE_RATE

        started = False

        try:

            while self._current(generation):

                try:

                    data = pcm_queue.get(timeout=0.25)

                except queue.Empty:

                    continue

                if data is None or not self._current(generation):

                    break

                if stream is None:

                    stream, rate = self._open_output()

                    with self._lock:

                        if not self._current(generation):

                            break

                        self._stream = stream

                    stream.start()

                    started = True

                    self._speaking = True

                    self._playback_started.emit(generation)

                samples = np.frombuffer(data, dtype=np.int16)

                if samples.size:

                    self._level = float(
                        np.sqrt(np.mean((samples / 32768.0) ** 2))
                    )

                    self._level_time = time.time()

                if rate != self.SAMPLE_RATE and samples.size:

                    data = self._resample(samples, rate).tobytes()

                stream.write(data)

            if stream is not None and self._current(generation):

                # Let the last buffered audio finish playing.
                stream.stop()

        except Exception as error:

            if self._current(generation):

                print(f"GLITCH PLAYBACK ERROR: {error}")

                self.voice_error.emit(str(error))

        finally:

            if stream is not None:

                try:

                    stream.close()

                except Exception:

                    pass

            with self._lock:

                if self._current(generation):

                    if self._stream is stream:

                        self._stream = None

                    self._speaking = False

                    self._active = False

            self._level = 0.0

            self._playback_ended.emit(generation)


    def _open_output(self):

        """Open the speakers at 24 kHz, or at the device's own rate
        (with resampling) if the device refuses 24 kHz."""

        try:

            return (
                sd.RawOutputStream(
                    samplerate=self.SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    latency="low",
                ),
                self.SAMPLE_RATE,
            )

        except Exception as error:

            device = sd.query_devices(kind="output")

            rate = int(device.get("default_samplerate") or 48000)

            print(
                f"GLITCH VOICE // output refused {self.SAMPLE_RATE} Hz "
                f"({error}); using {rate} Hz on '{device.get('name')}'"
            )

            return (
                sd.RawOutputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="int16",
                    latency="low",
                ),
                rate,
            )


    def _resample(
        self,
        samples,
        rate
    ):

        count = max(1, int(round(samples.size * rate / self.SAMPLE_RATE)))

        positions = np.linspace(0, samples.size - 1, count)

        return np.interp(
            positions,
            np.arange(samples.size),
            samples.astype(np.float32),
        ).astype(np.int16)

    # ======================================================
    # PUBLIC SPEAKING STATE (runs on the Qt thread)
    # ======================================================

    def _on_playback_started(
        self,
        generation
    ):

        if generation != self._generation:

            return

        if not self._public_speaking:

            self._public_speaking = True

            self.speech_started.emit()


    def _on_playback_ended(
        self,
        generation
    ):

        if generation != self._generation:

            return

        if self._public_speaking:

            self._public_speaking = False

            self.speech_finished.emit()

    # ======================================================
    # CANCEL
    # ======================================================

    def _cancel(
        self,
        emit_finished
    ):

        with self._lock:

            self._generation += 1

            stream = self._stream

            self._stream = None

            if self._text_queue is not None:

                self._text_queue.put(None)

                self._text_queue = None

            self._buffer = ""

            self._speaking = False

            self._active = False

        if stream is not None:

            try:

                stream.abort()

            except Exception:

                pass

        self._level = 0.0

        if emit_finished and self._public_speaking:

            self._public_speaking = False

            self.speech_finished.emit()