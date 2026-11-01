"""
services/auth_session.py

Qt wrapper around the biometric engine.

AuthWorker   runs camera-based face verification on its own thread and
             streams live preview frames and match scores.
AuthSession  owns the thread, the brute-force lockout, and re-emits
             everything on the GUI thread for the lock-screen overlay.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

from services.biometric_engine import (
    AuditLog,
    AuthConfig,
    AuthDependencyError,
    FaceEngine,
    LockoutStore,
    ProfileStore,
    template_score,
)


# Reasons that count toward the brute-force lockout.
MISMATCH_REASONS = ("FACE_MISMATCH",)


@dataclass
class AuthResult:

    granted: bool = False

    # GRANTED, FACE_MISMATCH, NO_FACE, NO_PROFILE, FAULT, CANCELLED
    reason: str = ""

    detail: str = ""

    face_ok: bool = False
    voice_ok: bool = False

    face_score: float = 0.0
    voice_score: float = 0.0

    @property
    def counts_as_failure(self) -> bool:

        return self.reason in MISMATCH_REASONS


# =========================================================
# WORKER (runs on its own QThread)
# =========================================================

class AuthWorker(QObject):

    stage_changed = Signal(str, str)         # BOOT | FACE | VOICE, message
    preview_frame = Signal(QImage)           # mirrored camera frame
    face_status = Signal(float, bool, object)  # score, face present, box
    voice_level = Signal(float)
    factor_result = Signal(str, bool, float)   # FACE | VOICE, ok, score
    completed = Signal(object)               # AuthResult

    def __init__(self, config: AuthConfig):

        super().__init__()

        self.config = config

        self._stop = False

        self._audit = AuditLog(config)

    def request_stop(self):

        self._stop = True

    # -----------------------------------------------------

    @Slot()
    def run(self):

        try:

            result = self._authenticate()

        except AuthDependencyError as error:

            result = AuthResult(
                reason="FAULT",
                detail=str(error),
            )

        except Exception as error:

            result = AuthResult(
                reason="FAULT",
                detail=f"{type(error).__name__}: {error}",
            )

        self._audit.write(
            event="AUTH_ATTEMPT",
            granted=result.granted,
            reason=result.reason,
            face_score=round(result.face_score, 3),
            voice_score=round(result.voice_score, 3),
            detail=result.detail,
        )

        self.completed.emit(result)

    # -----------------------------------------------------

    def _authenticate(self) -> AuthResult:

        config = self.config

        profile = ProfileStore(
            config
        ).load()


        if profile is None:

            return AuthResult(
                reason="NO_PROFILE",
                detail=(
                    "Owner face profile not found. "
                    "Run tools/enroll_404.py to enroll the owner."
                ),
            )


        self.stage_changed.emit(
            "BOOT",
            "LOADING FACE RECOGNITION MODEL"
        )


        face_engine = FaceEngine(
            config.models_dir
        )


        if self._stop:

            return AuthResult(
                reason="CANCELLED"
            )


        # ----------------------------- FACE ONLY

        self.stage_changed.emit(
            "FACE",
            "ACQUIRING FACIAL BIOMETRICS"
        )


        (
            face_ok,
            face_score,
            face_seen,
            last_frame
        ) = self._scan_face(
            face_engine,
            profile.face,
        )


        self.factor_result.emit(
            "FACE",
            face_ok,
            face_score
        )


        if self._stop:

            return AuthResult(
                reason="CANCELLED"
            )


        # Keep legacy voice fields marked successful so older
        # UI/main-window code that still reads them does not fail.
        result = AuthResult(
            face_ok=face_ok,
            voice_ok=True,
            face_score=face_score,
            voice_score=1.0,
        )


        if not face_ok:

            if face_seen:

                result.reason = (
                    "FACE_MISMATCH"
                )

                self._audit.save_snapshot(
                    last_frame
                )

            else:

                result.reason = (
                    "NO_FACE"
                )


            return result


        # Face passed -> immediate access.
        result.granted = True
        result.reason = "GRANTED"

        return result


    # -----------------------------------------------------

    def _scan_face(self, engine: FaceEngine, templates):

        import cv2

        config = self.config

        # Prefer DirectShow on Windows for laptop webcams.
        camera = cv2.VideoCapture(
            config.camera_index,
            cv2.CAP_DSHOW
        )

        if not camera.isOpened():

            camera.release()

            camera = cv2.VideoCapture(
                config.camera_index
            )


        if not camera.isOpened():

            raise AuthDependencyError(
                "Unable to open webcam. "
                "Check Windows camera permissions and make sure "
                "another application is not using the camera."
            )

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        scores = []

        seen = False
        last_frame = None
        passed = False
        final_score = 0.0

        deadline = time.monotonic() + config.face_timeout_s

        try:

            # Let auto-exposure settle and immediately feed
            # preview frames to the holographic auth overlay.
            for _ in range(12):

                success, warm_frame = camera.read()

                if success:

                    self._emit_preview(
                        warm_frame
                    )

            while time.monotonic() < deadline and not self._stop:

                success, frame = camera.read()

                if not success:

                    continue

                last_frame = frame

                embedding, box = engine.embed(frame)

                mirrored_box = None

                if (
                    embedding is not None
                    and box[2] >= config.min_face_width
                ):

                    seen = True

                    score = template_score(embedding, templates)

                    scores.append(score)

                    mirrored_box = (
                        1.0 - (box[0] + box[2]),
                        box[1],
                        box[2],
                        box[3],
                    )

                    self.face_status.emit(score, True, mirrored_box)

                else:

                    # Face lost / too small: restart the rolling window.
                    scores.clear()

                    self.face_status.emit(0.0, False, None)

                self._emit_preview(frame)

                needed = config.face_frames_required

                if len(scores) >= needed:

                    recent = np.asarray(scores[-needed:])

                    hits = float(np.mean(recent >= config.face_threshold))

                    final_score = float(np.median(recent))

                    if hits >= 0.8:

                        passed = True

                        break

        finally:

            camera.release()

        if not passed and scores:

            final_score = float(np.median(scores[-config.face_frames_required:]))

        return passed, final_score, seen, last_frame

    def _emit_preview(self, frame_bgr):

        import cv2

        small = cv2.resize(frame_bgr, (480, 360))

        rgb = cv2.cvtColor(cv2.flip(small, 1), cv2.COLOR_BGR2RGB)

        height, width = rgb.shape[:2]

        image = QImage(
            rgb.data,
            width,
            height,
            width * 3,
            QImage.Format.Format_RGB888,
        ).copy()

        self.preview_frame.emit(image)



# =========================================================
# SESSION (lives on the GUI thread)
# =========================================================

class AuthSession(QObject):

    stage_changed = Signal(str, str)
    preview_frame = Signal(QImage)
    face_status = Signal(float, bool, object)
    voice_level = Signal(float)
    factor_result = Signal(str, bool, float)

    granted = Signal(object)       # AuthResult
    denied = Signal(object)        # AuthResult
    lockdown = Signal(int)         # seconds remaining

    def __init__(self, data_dir, parent=None):

        super().__init__(parent)

        self.config = AuthConfig.from_data_dir(data_dir)

        self.lockout = LockoutStore(self.config)

        self._thread: Optional[QThread] = None
        self._worker: Optional[AuthWorker] = None

    @property
    def busy(self) -> bool:

        return self._thread is not None

    def has_profile(self) -> bool:

        return ProfileStore(self.config).exists()

    # -----------------------------------------------------

    def begin(self):

        if self._thread is not None:

            return

        remaining = self.lockout.remaining()

        if remaining > 0:

            self.lockdown.emit(int(math.ceil(remaining)))

            return

        thread = QThread(self)

        worker = AuthWorker(self.config)

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.stage_changed.connect(self.stage_changed)
        worker.preview_frame.connect(self.preview_frame)
        worker.face_status.connect(self.face_status)
        worker.voice_level.connect(self.voice_level)
        worker.factor_result.connect(self.factor_result)

        worker.completed.connect(self._on_completed)
        worker.completed.connect(thread.quit)

        thread.finished.connect(self._cleanup)

        self._thread = thread
        self._worker = worker

        thread.start()

    def _on_completed(self, result: AuthResult):

        if result.granted:

            self.lockout.clear()

            self.granted.emit(result)

            return

        tripped = False

        if result.counts_as_failure:

            tripped = self.lockout.record_failure()

        self.denied.emit(result)

        if tripped:

            self.lockdown.emit(
                int(math.ceil(self.lockout.remaining()))
            )

    def _cleanup(self):

        if self._worker is not None:

            self._worker.deleteLater()

        if self._thread is not None:

            self._thread.deleteLater()

        self._worker = None
        self._thread = None

    def shutdown(self):

        if self._worker is not None:

            self._worker.request_stop()

        if self._thread is not None:

            self._thread.quit()

            self._thread.wait(4000)
