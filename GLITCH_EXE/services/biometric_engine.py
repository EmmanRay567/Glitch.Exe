"""
services/biometric_engine.py

Pure-Python (no Qt) biometric core for GLITCH.EXE owner authentication.

Single-factor camera authentication for GLITCH.EXE:

    FACE   OpenCV YuNet detector + SFace recognizer (128-d embeddings).
           Runs on CPU, no dlib / no CMake, works on Windows out of the box.

Only embeddings are stored (data/auth/owner_profile.npz) - never raw
photos. Everything stays on this machine.

Fail-closed: any missing model, missing profile, or broken camera results
in ACCESS DENIED, never in access.

Mirror-safe: every face is embedded in BOTH orientations (as captured and
mirrored) and the better match counts, so a profile enrolled from a mirrored
selfie view and a login from the raw camera feed (or the reverse) agree.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np


OWNER_ID = "404"


class AuthDependencyError(RuntimeError):
    """A model / package / device needed for authentication is missing."""


# =========================================================
# CONFIG
# =========================================================

@dataclass
class AuthConfig:

    auth_dir: Path

    # Cosine similarity needed against enrolled templates.
    face_threshold: float = 0.42

    # Face must match on >= 80% of the last N frames.
    face_frames_required: int = 4
    face_timeout_s: float = 12
    min_face_width: float = 0.08     # fraction of frame width

    # Legacy voice settings: unused (voice is disabled) but kept so older
    # code that still reads them does not crash.
    voice_threshold: float = 0.75
    voice_seconds: float = 3.5
    sample_rate: int = 16000
    min_speech_rms: float = 0.012

    camera_index: int = 0

    # Brute-force protection.
    max_failures: int = 3
    lockout_seconds: int = 60         # doubles on every repeat lockout
    max_lockout_seconds: int = 900

    save_intruder_snapshots: bool = True

    @classmethod
    def from_data_dir(cls, data_dir) -> "AuthConfig":

        auth_dir = Path(data_dir) / "auth"
        auth_dir.mkdir(parents=True, exist_ok=True)

        return cls(auth_dir=auth_dir)

    @property
    def models_dir(self) -> Path:

        path = self.auth_dir / "models"
        path.mkdir(exist_ok=True)

        return path

    @property
    def profile_path(self) -> Path:

        return self.auth_dir / "owner_profile.npz"

    @property
    def log_path(self) -> Path:

        return self.auth_dir / "auth_log.jsonl"

    @property
    def lockout_path(self) -> Path:

        return self.auth_dir / "lockout.json"

    @property
    def intruder_dir(self) -> Path:

        path = self.auth_dir / "intruders"
        path.mkdir(exist_ok=True)

        return path


# =========================================================
# MATH
# =========================================================

def l2_normalize(vector) -> np.ndarray:

    vector = np.asarray(vector, dtype=np.float32).reshape(-1)

    norm = float(np.linalg.norm(vector))

    return vector / norm if norm > 1e-9 else vector


def template_score(embedding, templates, top_k: int = 3) -> float:
    """
    Mean of the top-k cosine similarities to the enrolled templates.

    `embedding` may be one vector (D,) or several views (V, D), e.g. the
    as-captured and mirrored face. With several views the best view wins.
    """

    templates = np.asarray(templates, dtype=np.float32)

    views = np.asarray(embedding, dtype=np.float32)

    if views.ndim == 1:

        views = views[None, :]

    best = -1.0

    for view in views:

        sims = templates @ l2_normalize(view)

        k = max(1, min(top_k, len(sims)))

        best = max(best, float(np.sort(sims)[-k:].mean()))

    return best


# =========================================================
# PROFILE STORE
# =========================================================

@dataclass
class OwnerProfile:

    face: np.ndarray      # (N, 128)
    voice: np.ndarray     # (M, 256) - empty when voice is not enrolled
    created: float


class ProfileStore:

    def __init__(self, config: AuthConfig):

        self.path = config.profile_path

    def exists(self) -> bool:

        return self.path.exists()

    def load(self) -> Optional[OwnerProfile]:

        if not self.path.exists():

            return None

        try:

            with np.load(self.path, allow_pickle=False) as data:

                face = np.asarray(data["face"], dtype=np.float32)

                voice = (
                    np.asarray(data["voice"], dtype=np.float32)
                    if "voice" in data.files
                    else np.zeros((0, 256), np.float32)
                )

                created = (
                    float(data["created"])
                    if "created" in data.files
                    else 0.0
                )

        except Exception as error:

            raise AuthDependencyError(
                f"Owner profile is unreadable ({error}). "
                "Re-run the enrollment tool."
            )

        if face.ndim != 2 or len(face) < 3:

            raise AuthDependencyError(
                "Owner profile has too few face samples. "
                "Re-run the enrollment tool."
            )

        if voice.ndim != 2:

            voice = np.zeros((0, 256), np.float32)

        return OwnerProfile(
            face=np.vstack([l2_normalize(row) for row in face]),
            voice=(
                np.vstack([l2_normalize(row) for row in voice])
                if len(voice)
                else np.zeros((0, 256), np.float32)
            ),
            created=created,
        )

    def save(self, face, voice=None) -> None:

        np.savez_compressed(
            self.path,
            face=np.asarray(face, dtype=np.float32),
            voice=np.asarray(
                voice if voice is not None else np.zeros((0, 256)),
                dtype=np.float32,
            ),
            created=np.float64(time.time()),
        )


# =========================================================
# FACE
# =========================================================

FACE_MODELS = {

    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        100_000,
    ),

    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        20_000_000,
    ),
}


def ensure_model(models_dir: Path, name: str) -> Path:

    path = Path(models_dir) / name

    url, min_bytes = FACE_MODELS[name]

    if path.exists() and path.stat().st_size >= min_bytes:

        return path

    temp = path.with_suffix(".part")

    try:

        with urllib.request.urlopen(url, timeout=60) as response:

            temp.write_bytes(response.read())

        if temp.stat().st_size < min_bytes:

            raise RuntimeError("download was truncated")

        temp.replace(path)

    except Exception as error:

        if temp.exists():

            temp.unlink()

        raise AuthDependencyError(
            f"Could not download {name} ({error}). "
            f"Download it manually from {url} and place it in {models_dir}"
        )

    return path


class FaceEngine:

    def __init__(self, models_dir: Path):

        try:

            import cv2

        except ImportError as error:

            raise AuthDependencyError(f"OpenCV is required: {error}")

        self.cv2 = cv2

        detector_path = ensure_model(
            models_dir,
            "face_detection_yunet_2023mar.onnx",
        )

        recognizer_path = ensure_model(
            models_dir,
            "face_recognition_sface_2021dec.onnx",
        )

        self.detector = cv2.FaceDetectorYN.create(
            str(detector_path),
            "",
            (320, 320),
            0.85,     # score threshold
            0.3,      # NMS threshold
            50,
        )

        self.recognizer = cv2.FaceRecognizerSF.create(
            str(recognizer_path),
            "",
        )

    def embed(self, frame_bgr):
        """
        Returns (embedding, box) for the largest face, or (None, None).

        embedding has shape (2, 128): the face as captured and its mirror
        image. template_score() takes the better view; enrollment stores
        both. box is (x, y, w, h) normalized to the frame (not mirrored).
        """

        height, width = frame_bgr.shape[:2]

        self.detector.setInputSize((width, height))

        _, faces = self.detector.detect(frame_bgr)

        if faces is None or len(faces) == 0:

            return None, None

        face = max(faces, key=lambda f: float(f[2]) * float(f[3]))

        aligned = self.recognizer.alignCrop(frame_bgr, face)

        feature = self.recognizer.feature(aligned)

        mirrored = self.recognizer.feature(self.cv2.flip(aligned, 1))

        box = (
            float(face[0]) / width,
            float(face[1]) / height,
            float(face[2]) / width,
            float(face[3]) / height,
        )

        embedding = np.vstack(
            [l2_normalize(feature), l2_normalize(mirrored)]
        )

        return embedding, box


# =========================================================
# VOICE
# =========================================================

class SpeakerEngine:

    def __init__(self):

        try:

            from resemblyzer import VoiceEncoder, preprocess_wav

        except ImportError as error:

            raise AuthDependencyError(
                "Resemblyzer is required for voice authentication "
                f"({error}). See auth_patch.md for install steps."
            )

        self._preprocess = preprocess_wav

        self.encoder = VoiceEncoder(device="cpu", verbose=False)

    def embed(self, audio: np.ndarray, sample_rate: int):

        wav = self._preprocess(
            np.asarray(audio, dtype=np.float32),
            source_sr=sample_rate,
        )

        # Need at least ~1 s of actual speech after silence trimming.
        if len(wav) < sample_rate * 1.0:

            return None

        return l2_normalize(self.encoder.embed_utterance(wav))


def record_audio(
    seconds: float,
    sample_rate: int,
    on_level: Optional[Callable[[float], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> np.ndarray:

    try:

        import sounddevice as sd

    except ImportError as error:

        raise AuthDependencyError(
            f"sounddevice is required for the microphone: {error}"
        )

    chunk = int(sample_rate * 0.1)

    chunks = []

    try:

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        ) as stream:

            for _ in range(int(round(seconds / 0.1))):

                if should_stop is not None and should_stop():

                    break

                data, _overflow = stream.read(chunk)

                mono = data[:, 0].copy()

                chunks.append(mono)

                if on_level is not None:

                    on_level(float(np.sqrt(np.mean(mono ** 2))))

    except AuthDependencyError:

        raise

    except Exception as error:

        raise AuthDependencyError(f"Unable to open microphone: {error}")

    if not chunks:

        return np.zeros(0, dtype=np.float32)

    return np.concatenate(chunks)


def speech_present(audio: np.ndarray, sample_rate: int, min_rms: float) -> bool:

    window = int(sample_rate * 0.1)

    if len(audio) < window:

        return False

    count = len(audio) // window

    frames = audio[: count * window].reshape(count, window)

    rms = np.sqrt(np.mean(frames ** 2, axis=1))

    # At least ~0.4 s of frames above the floor.
    return int(np.sum(rms >= min_rms)) >= 4


# =========================================================
# AUDIT LOG / SNAPSHOTS
# =========================================================

class AuditLog:

    def __init__(self, config: AuthConfig):

        self.config = config

    def write(self, **fields) -> None:

        fields["time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        try:

            with open(
                self.config.log_path,
                "a",
                encoding="utf-8",
            ) as file:

                file.write(json.dumps(fields) + "\n")

        except Exception:

            pass

    def save_snapshot(self, frame_bgr) -> Optional[str]:

        if not self.config.save_intruder_snapshots or frame_bgr is None:

            return None

        try:

            import cv2

            path = (
                self.config.intruder_dir
                / time.strftime("intruder_%Y%m%d_%H%M%S.jpg")
            )

            cv2.imwrite(str(path), frame_bgr)

            return str(path)

        except Exception:

            return None


# =========================================================
# LOCKOUT (persisted so restarting the app does not reset it)
# =========================================================

class LockoutStore:

    def __init__(self, config: AuthConfig):

        self.config = config

        self.failures = 0
        self.trips = 0
        self.locked_until = 0.0

        self._load()

    def _load(self) -> None:

        try:

            data = json.loads(
                self.config.lockout_path.read_text(encoding="utf-8")
            )

            self.failures = int(data.get("failures", 0))
            self.trips = int(data.get("trips", 0))
            self.locked_until = float(data.get("locked_until", 0.0))

        except Exception:

            pass

    def _save(self) -> None:

        try:

            self.config.lockout_path.write_text(
                json.dumps(
                    {
                        "failures": self.failures,
                        "trips": self.trips,
                        "locked_until": self.locked_until,
                    }
                ),
                encoding="utf-8",
            )

        except Exception:

            pass

    def remaining(self) -> float:

        return max(0.0, self.locked_until - time.time())

    def record_failure(self) -> bool:
        """Returns True if this failure triggered a lockout."""

        self.failures += 1

        tripped = False

        if self.failures >= self.config.max_failures:

            self.trips += 1

            seconds = min(
                self.config.lockout_seconds * (2 ** (self.trips - 1)),
                self.config.max_lockout_seconds,
            )

            self.locked_until = time.time() + seconds

            self.failures = 0

            tripped = True

        self._save()

        return tripped

    def clear(self) -> None:

        self.failures = 0
        self.trips = 0
        self.locked_until = 0.0

        self._save()