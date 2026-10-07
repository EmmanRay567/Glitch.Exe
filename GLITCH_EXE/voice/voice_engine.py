import os
import tempfile
import threading

from dotenv import load_dotenv
from openai import OpenAI

from PySide6.QtCore import (
    QObject,
    Signal,
    QUrl,
)

from PySide6.QtMultimedia import (
    QMediaPlayer,
    QAudioOutput,
)


load_dotenv()


class VoiceEngine(QObject):

    # Sent from background generation thread
    audio_ready = Signal(str)

    # Useful for the HUD later
    speech_started = Signal()
    speech_finished = Signal()

    voice_error = Signal(str)


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


        # ==================================================
        # GLITCH VOICE
        # ==================================================

        self.voice = "onyx"

        self.instructions = """
You are the voice of GLITCH.EXE, a futuristic personal AI system.

Speak with a smooth, polished and intelligent voice.

Voice characteristics:
- medium-low vocal register
- calm and controlled
- sophisticated
- slightly futuristic
- subtle synthetic quality
- slightly mysterious
- warm and approachable
- confident without sounding arrogant
- relaxed speaking pace
- crisp articulation
- occasional subtle dry humor

The voice should feel cinematic and advanced,
like an AI integrated into a high-tech command system.

Do not sound like a generic robot.

Do not imitate any existing fictional AI character.

GLITCH.EXE should have its own identity:
part intelligent assistant,
part cybernetic system,
part creative technology companion.

Keep responses natural and conversational.
"""


        # ==================================================
        # QT AUDIO SYSTEM
        # ==================================================

        self.audio_output = QAudioOutput()

        self.audio_output.setVolume(
            1.0
        )

        self.player = QMediaPlayer()

        self.player.setAudioOutput(
            self.audio_output
        )


        # ==================================================
        # INTERNAL STATE
        # ==================================================

        self.current_audio_file = None

        self._is_generating = False


        # ==================================================
        # SIGNAL CONNECTIONS
        # ==================================================

        self.audio_ready.connect(
            self._play_audio
        )

        self.player.mediaStatusChanged.connect(
            self._media_status_changed
        )


    # ======================================================
    # SPEAK
    # ======================================================

    def speak(
        self,
        text
    ):

        if not text:
            return

        text = text.strip()

        if not text:
            return


        # Stop previous voice
        if (
            self.player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.stop()


        # Prevent duplicate generation
        if self._is_generating:
            return


        self._is_generating = True


        voice_thread = threading.Thread(
            target=self._generate_voice,
            args=(text,),
            daemon=True
        )

        voice_thread.start()


    # ======================================================
    # GENERATE SPEECH
    # ======================================================

    def _generate_voice(
        self,
        text
    ):

        temp_path = None

        try:

            # ----------------------------------------------
            # CREATE TEMP FILE
            # ----------------------------------------------

            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".wav"
            )

            temp_path = temp_file.name

            temp_file.close()


            # ----------------------------------------------
            # OPENAI TTS
            # ----------------------------------------------

            response = (
                self.client.audio.speech.create(
                    model="gpt-4o-mini-tts",
                    voice=self.voice,
                    input=text,
                    instructions=self.instructions,
                    response_format="wav"
                )
            )


            # ----------------------------------------------
            # SAVE WAV
            # ----------------------------------------------

            response.write_to_file(
                temp_path
            )


            # ----------------------------------------------
            # SEND TO QT THREAD
            # ----------------------------------------------

            self.audio_ready.emit(
                temp_path
            )


        except Exception as error:

            self.voice_error.emit(
                str(error)
            )

            print(
                f"GLITCH VOICE ERROR: {error}"
            )

            if temp_path:

                try:
                    os.remove(
                        temp_path
                    )

                except OSError:
                    pass


        finally:

            self._is_generating = False


    # ======================================================
    # PLAY INSIDE GLITCH.EXE
    # ======================================================

    def _play_audio(
        self,
        audio_path
    ):

        self.current_audio_file = (
            audio_path
        )

        audio_url = QUrl.fromLocalFile(
            audio_path
        )

        self.player.setSource(
            audio_url
        )

        self.player.play()

        self.speech_started.emit()


    # ======================================================
    # WATCH PLAYBACK
    # ======================================================

    def _media_status_changed(
        self,
        status
    ):

        if (
            status
            == QMediaPlayer.MediaStatus.EndOfMedia
        ):

            self.speech_finished.emit()

            self._cleanup_audio_file()


    # ======================================================
    # CLEAN TEMP FILE
    # ======================================================

    def _cleanup_audio_file(
        self
    ):

        if not self.current_audio_file:
            return

        old_file = (
            self.current_audio_file
        )

        self.current_audio_file = None


        # Release the file before deleting it
        self.player.setSource(
            QUrl()
        )

        try:

            os.remove(
                old_file
            )

        except OSError:
            pass


    # ======================================================
    # STOP SPEECH
    # ======================================================

    def stop(
        self
    ):

        self.player.stop()

        self.speech_finished.emit()

        self._cleanup_audio_file()