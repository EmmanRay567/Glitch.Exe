"""
tools/enroll_404.py

One-time (re-runnable) enrollment of the GLITCH owner.

Run from the project root, BEFORE launching GLITCH with auth enabled:

    python tools/enroll_404.py

Captures ~16 face samples (slight head movement for robustness) and
6 voice samples, then stores only embeddings in data/auth/owner_profile.npz.

Enrollment is deliberately a separate command-line tool, not part of the
lock screen, so nobody standing in front of a locked GLITCH can enroll
themselves.
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from services.biometric_engine import (
    AuthConfig,
    AuthDependencyError,
    FaceEngine,
    ProfileStore,
    SpeakerEngine,
    l2_normalize,
    record_audio,
    speech_present,
    template_score,
)


FACE_SAMPLES = 16
VOICE_SAMPLES = 6

FACE_PROMPTS = (
    "Look straight at the camera",
    "Slightly turn your head LEFT",
    "Slightly turn your head RIGHT",
    "Tilt your chin UP a little",
    "Tilt your chin DOWN a little",
)


def leave_one_out(vectors):

    scores = []

    for index in range(len(vectors)):

        others = np.delete(vectors, index, axis=0)

        scores.append(template_score(vectors[index], others))

    return np.asarray(scores)


def capture_faces(config, engine):

    import cv2

    camera = cv2.VideoCapture(config.camera_index)

    if not camera.isOpened():

        raise AuthDependencyError("Unable to open webcam.")

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window = "GLITCH ENROLLMENT  (SPACE = start, ESC = abort)"

    samples = []

    started = False
    last_capture = 0.0

    try:

        while len(samples) < FACE_SAMPLES:

            success, frame = camera.read()

            if not success:

                continue

            frame = cv2.flip(frame, 1)

            embedding, box = engine.embed(frame)

            height, width = frame.shape[:2]

            good = (
                embedding is not None
                and box[2] >= 0.20
            )

            if box is not None:

                x, y, w, h = box

                cv2.rectangle(
                    frame,
                    (int(x * width), int(y * height)),
                    (int((x + w) * width), int((y + h) * height)),
                    (120, 255, 57) if good else (60, 60, 255),
                    2,
                )

            if not started:

                text = "Press SPACE when ready"

            else:

                prompt = FACE_PROMPTS[
                    min(
                        len(samples) * len(FACE_PROMPTS) // FACE_SAMPLES,
                        len(FACE_PROMPTS) - 1,
                    )
                ]

                text = f"[{len(samples)}/{FACE_SAMPLES}] {prompt}"

                if (
                    good
                    and time.monotonic() - last_capture >= 0.6
                ):

                    samples.append(embedding)

                    last_capture = time.monotonic()

            if embedding is None:

                text += "   (no face found)"

            elif not good:

                text += "   (move closer)"

            cv2.putText(
                frame,
                text,
                (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (120, 255, 57),
                2,
            )

            cv2.imshow(window, frame)

            key = cv2.waitKey(1) & 0xFF

            if key == 27:

                raise KeyboardInterrupt

            if key == 32:

                started = True

    finally:

        camera.release()

        cv2.destroyAllWindows()

    return np.vstack(samples)


def capture_voice(config, speaker):

    print()
    print("VOICE ENROLLMENT")
    print("Say the same phrase each time, in your normal voice:")
    print('    "Glitch, it\'s 404."')
    print()

    samples = []

    attempts = 0

    while len(samples) < VOICE_SAMPLES and attempts < VOICE_SAMPLES * 3:

        attempts += 1

        for count in (3, 2, 1):

            print(f"  recording in {count}...", end="\r", flush=True)

            time.sleep(0.7)

        print(
            f"  >>> SPEAK NOW  ({len(samples) + 1}/{VOICE_SAMPLES})      "
        )

        audio = record_audio(
            config.voice_seconds,
            config.sample_rate,
        )

        if not speech_present(
            audio,
            config.sample_rate,
            config.min_speech_rms,
        ):

            print("      no speech detected, try again")

            continue

        embedding = speaker.embed(audio, config.sample_rate)

        if embedding is None:

            print("      too short / too quiet, try again")

            continue

        samples.append(embedding)

    if len(samples) < VOICE_SAMPLES:

        raise AuthDependencyError(
            "Could not capture enough clear voice samples."
        )

    return np.vstack(samples)


def main():

    config = AuthConfig.from_data_dir(PROJECT_ROOT / "data")

    store = ProfileStore(config)

    print("=== GLITCH OWNER ENROLLMENT ===")

    if store.exists():

        answer = input(
            "An owner profile already exists. Replace it? (type YES): "
        )

        if answer.strip() != "YES":

            print("Aborted.")

            return 1

    print("Loading models (first run downloads ~40 MB)...")

    try:

        face_engine = FaceEngine(config.models_dir)

        speaker = SpeakerEngine()

        input("\nFACE ENROLLMENT - press ENTER to open the camera...")

        face = capture_faces(config, face_engine)

        voice = capture_voice(config, speaker)

    except KeyboardInterrupt:

        print("\nAborted. Nothing was saved.")

        return 1

    except AuthDependencyError as error:

        print(f"\nERROR: {error}")

        return 2

    face_loo = leave_one_out(face)
    voice_loo = leave_one_out(voice)

    print()
    print("SELF-CONSISTENCY (how well you match yourself)")
    print(
        f"  face : min {face_loo.min():.2f}  median {np.median(face_loo):.2f}"
        f"   (threshold {config.face_threshold:.2f})"
    )
    print(
        f"  voice: min {voice_loo.min():.2f}  median {np.median(voice_loo):.2f}"
        f"   (threshold {config.voice_threshold:.2f})"
    )

    if face_loo.min() < config.face_threshold:

        print(
            "  WARNING: some face samples are weak. Better lighting / "
            "re-running enrollment will make logins more reliable."
        )

    if voice_loo.min() < config.voice_threshold:

        print(
            "  WARNING: some voice samples are weak. Try a quieter room "
            "and a consistent distance from the microphone."
        )

    store.save(face, voice)

    print(f"\nSaved owner profile to {config.profile_path}")

    return 0


if __name__ == "__main__":

    sys.exit(main())
