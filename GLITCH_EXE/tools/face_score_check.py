"""
tools/face_score_check.py

"Why won't GLITCH let me in?" - run this from the project root:

    python tools/face_score_check.py              # live scores for ~10 s
    python tools/face_score_check.py --reset-lockout

It prints
  * whether a lockout is active (and clears it with --reset-lockout)
  * the last few login attempts and why they were refused
  * your live match score against the enrolled profile, frame by frame,
    and a suggested threshold

It never grants access to anything; it only reads the camera and the profile.
"""

import json
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
    LockoutStore,
    ProfileStore,
    template_score,
)


def main():

    config = AuthConfig.from_data_dir(PROJECT_ROOT / "data")

    lockout = LockoutStore(config)

    if "--reset-lockout" in sys.argv:

        lockout.clear()

        print("Lockout cleared.")

    remaining = lockout.remaining()

    print(
        f"Lockout : {'ACTIVE for %d more seconds' % remaining if remaining else 'none'}"
        f"  (failed attempts counted: {lockout.failures}, lockouts so far: {lockout.trips})"
    )

    if config.log_path.exists():

        print("\nLast login attempts (data/auth/auth_log.jsonl):")

        for line in config.log_path.read_text(encoding="utf-8").splitlines()[-6:]:

            try:

                entry = json.loads(line)

            except Exception:

                continue

            print(
                f"  {entry.get('time')}  granted={entry.get('granted')}  "
                f"reason={entry.get('reason')}  face={entry.get('face_score')}  "
                f"{entry.get('detail') or ''}"
            )

    else:

        print("\nNo login attempts logged yet.")

    try:

        profile = ProfileStore(config).load()

        if profile is None:

            print("\nNo owner profile found - run tools/enroll_404.py first.")

            return 1

        print(
            f"\nProfile : {len(profile.face)} face templates, "
            f"threshold {config.face_threshold:.2f}"
        )

        engine = FaceEngine(config.models_dir)

    except AuthDependencyError as error:

        print(f"\nERROR: {error}")

        return 2

    import cv2

    camera = cv2.VideoCapture(config.camera_index)

    if not camera.isOpened():

        print("ERROR: cannot open the camera (is GLITCH or another app using it?)")

        return 2

    print("\nLook at the camera normally for 10 seconds...\n")

    scores = []

    started = time.time()

    try:

        for _ in range(5):

            camera.read()

        while time.time() - started < 10.0:

            ok, frame = camera.read()

            if not ok:

                continue

            embedding, box = engine.embed(frame)

            if embedding is None:

                print("  no face found", end="\r")

                continue

            if box[2] < config.min_face_width:

                print(f"  face too small ({box[2]:.2f} of frame width)", end="\r")

                continue

            score = template_score(embedding, profile.face)

            scores.append(score)

            verdict = "PASS" if score >= config.face_threshold else "below threshold"

            print(f"  score {score:.2f}  {verdict}      ", end="\r")

    finally:

        camera.release()

    print()

    if not scores:

        print("\nNo usable face frames. Check lighting / distance, or lower min_face_width.")

        return 1

    scores = np.asarray(scores)

    passing = float(np.mean(scores >= config.face_threshold))

    print(
        f"\n{len(scores)} frames   min {scores.min():.2f}   "
        f"median {np.median(scores):.2f}   max {scores.max():.2f}   "
        f"passing {passing * 100:.0f}%"
    )

    if passing >= 0.8:

        print("You should get in. If GLITCH still refuses, check the log above.")

    else:

        suggestion = max(0.30, float(np.percentile(scores, 10)) - 0.05)

        print(
            "Your scores are too low for the current threshold.\n"
            f"  1. Best fix: re-run  python tools/enroll_404.py  in the lighting you normally use.\n"
            f"  2. Or lower face_threshold in AuthConfig to about {suggestion:.2f} "
            "(never below 0.30)."
        )

    return 0


if __name__ == "__main__":

    sys.exit(main())
