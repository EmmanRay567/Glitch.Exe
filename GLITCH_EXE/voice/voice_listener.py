import os
import queue
import tempfile
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

from dotenv import load_dotenv
from openai import OpenAI

from PySide6.QtCore import (
    QObject,
    Signal,
)


class VoiceListener(QObject):

    transcript_ready = Signal(str)

    listening_started = Signal()
    listening_stopped = Signal()

    voice_error = Signal(str)


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


        self.running = False

        self.sample_rate = 16000

        self.channels = 1


        # Lowered for easier testing
        self.energy_threshold = 0.008

        self.silence_seconds = 0.8

        self.minimum_speech_seconds = 0.25


        self.audio_queue = queue.Queue()


    # =====================================================
    # START
    # =====================================================

    def start(self):

        if self.running:

            print(
                "VOICE LISTENER ALREADY RUNNING"
            )

            return


        print(
            "VOICE LISTENER START REQUESTED"
        )


        self.running = True


        thread = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )

        thread.start()


    # =====================================================
    # STOP
    # =====================================================

    def stop(self):

        print(
            "VOICE LISTENER STOP REQUESTED"
        )

        self.running = False


    # =====================================================
    # MICROPHONE CALLBACK
    # =====================================================

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status
    ):

        if status:

            print(
                "VOICE INPUT STATUS:",
                status
            )


        self.audio_queue.put(
            indata.copy()
        )


    # =====================================================
    # LISTEN LOOP
    # =====================================================

    def _listen_loop(self):

        try:

            print(
                "VOICE LISTENER THREAD STARTED"
            )


            print(
                "DEFAULT INPUT DEVICE:",
                sd.default.device
            )


            print(
                "AVAILABLE DEVICES:"
            )


            print(
                sd.query_devices()
            )


            self.listening_started.emit()


            with sd.InputStream(

                samplerate=self.sample_rate,

                channels=self.channels,

                dtype="float32",

                callback=self._audio_callback

            ):

                print(
                    "MICROPHONE STREAM OPEN"
                )


                recording = []

                speaking = False

                speech_start_time = None

                last_voice_time = None


                while self.running:

                    try:

                        chunk = self.audio_queue.get(
                            timeout=0.25
                        )

                    except queue.Empty:

                        continue


                    rms = float(

                        np.sqrt(

                            np.mean(

                                np.square(
                                    chunk
                                )
                            )
                        )
                    )


                    # Print louder audio activity
                    if rms > 0.003:

                        print(
                            f"MIC LEVEL: {rms:.5f}"
                        )


                    current_time = (
                        time.time()
                    )


                    # =====================================
                    # VOICE START
                    # =====================================

                    if rms >= self.energy_threshold:

                        if not speaking:

                            speaking = True

                            recording = []

                            speech_start_time = (
                                current_time
                            )


                            print(
                                "VOICE DETECTED"
                            )


                        last_voice_time = (
                            current_time
                        )


                    # =====================================
                    # RECORD WHILE SPEAKING
                    # =====================================

                    if speaking:

                        recording.append(
                            chunk
                        )


                    # =====================================
                    # END AFTER SILENCE
                    # =====================================

                    if (

                        speaking

                        and last_voice_time is not None

                        and (

                            current_time
                            - last_voice_time

                        ) >= self.silence_seconds

                    ):

                        duration = (

                            current_time
                            - speech_start_time
                        )


                        speaking = False


                        print(
                            f"VOICE SEGMENT ENDED // "
                            f"{duration:.2f} sec"
                        )


                        if (

                            duration
                            >= self.minimum_speech_seconds

                            and recording

                        ):

                            audio = np.concatenate(
                                recording,
                                axis=0
                            )


                            print(
                                "SENDING AUDIO TO TRANSCRIPTION..."
                            )


                            self._transcribe(
                                audio
                            )


                        recording = []

                        speech_start_time = None

                        last_voice_time = None


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

            self.running = False

            print(
                "VOICE LISTENER THREAD STOPPED"
            )

            self.listening_stopped.emit()


    # =====================================================
    # TRANSCRIBE
    # =====================================================

    def _transcribe(
        self,
        audio
    ):

        temp_path = None


        try:

            with tempfile.NamedTemporaryFile(

                suffix=".wav",

                delete=False

            ) as temp_file:

                temp_path = (
                    temp_file.name
                )


            sf.write(

                temp_path,

                audio,

                self.sample_rate
            )


            print(
                "TEMP AUDIO SAVED:",
                temp_path
            )


            with open(
                temp_path,
                "rb"
            ) as audio_file:

                transcript = (

                    self.client
                    .audio
                    .transcriptions
                    .create(

                        model=
                            "gpt-4o-mini-transcribe",

                        file=
                            audio_file
                    )
                )


            text = (

                transcript.text
                .strip()
            )


            print(
                "TRANSCRIPTION RESULT:",
                repr(text)
            )


            if text:

                self.transcript_ready.emit(
                    text
                )


        except Exception as error:

            print(
                "TRANSCRIPTION ERROR:",
                error
            )


            self.voice_error.emit(
                str(
                    error
                )
            )


        finally:

            if (
                temp_path
                and os.path.exists(
                    temp_path
                )
            ):

                try:

                    os.remove(
                        temp_path
                    )

                except Exception:

                    pass