import time
from pathlib import Path

import cv2
import mediapipe as mp

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
)


class HandTracker(QObject):

    finger_moved = Signal(
        float,
        float
    )

    pinch_detected = Signal(
        float,
        float
    )

    # NEW
    swipe_left = Signal()
    swipe_right = Signal()

    tracking_started = Signal()
    tracking_stopped = Signal()
    tracking_error = Signal(str)


    def __init__(self):

        super().__init__()

        self.running = False


        self.base_dir = (
            Path(__file__)
            .resolve()
            .parent
        )


        self.model_path = (
            self.base_dir
            / "hand_landmarker.task"
        )


        # =================================================
        # PROXIMITY
        # =================================================

        self.proximity_active = False

        self.last_proximity_time = 0.0

        self.proximity_cooldown = 0.45


        # =================================================
        # SWIPE
        # =================================================

        self.swipe_start_x = None

        self.swipe_start_y = None

        self.swipe_start_time = None


        # Finger must travel about 22%
        # of camera width.
        self.swipe_distance = 0.05


        # Mostly horizontal movement.
        self.swipe_vertical_tolerance = 0.05


        # Must happen fairly quickly.
        self.swipe_max_duration = 0.90


        # Prevent double-page switching.
        self.swipe_cooldown = 0.75

        self.last_swipe_time = 0.0


    # =====================================================
    # START
    # =====================================================

    def start(self):

        if self.running:

            return


        if not self.model_path.exists():

            self.tracking_error.emit(
                "hand_landmarker.task not found."
            )

            return


        self.running = True


        try:

            self._tracking_loop()

        except Exception as error:

            self.tracking_error.emit(
                str(error)
            )

        finally:

            self.running = False

            self.tracking_stopped.emit()


    # =====================================================
    # STOP
    # =====================================================

    def stop(self):

        self.running = False


    # =====================================================
    # TRACKING LOOP
    # =====================================================

    def _tracking_loop(self):

        BaseOptions = (
            mp.tasks.BaseOptions
        )

        HandLandmarker = (
            mp.tasks.vision.HandLandmarker
        )

        HandLandmarkerOptions = (
            mp.tasks.vision.HandLandmarkerOptions
        )

        RunningMode = (
            mp.tasks.vision.RunningMode
        )


        options = HandLandmarkerOptions(

            base_options=BaseOptions(
                model_asset_path=str(
                    self.model_path
                )
            ),

            running_mode=RunningMode.VIDEO,

            num_hands=1,

            min_hand_detection_confidence=0.55,

            min_hand_presence_confidence=0.55,

            min_tracking_confidence=0.55,
        )


        camera = (
            cv2.VideoCapture(
                0
            )
        )


        if not camera.isOpened():

            raise RuntimeError(
                "Unable to open webcam."
            )


        camera.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            640
        )

        camera.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            480
        )


        self.tracking_started.emit()


        timestamp_ms = 0


        with HandLandmarker.create_from_options(
            options
        ) as landmarker:

            while self.running:

                success, frame = (
                    camera.read()
                )


                if not success:

                    continue


                frame = cv2.flip(
                    frame,
                    1
                )


                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )


                mp_image = mp.Image(
                    image_format=(
                        mp.ImageFormat.SRGB
                    ),
                    data=rgb_frame
                )


                timestamp_ms += 33


                result = (
                    landmarker
                    .detect_for_video(
                        mp_image,
                        timestamp_ms
                    )
                )


                if not result.hand_landmarks:

                    self.reset_swipe()

                    continue


                landmarks = (
                    result.hand_landmarks[0]
                )


                index_tip = (
                    landmarks[8]
                )


                x = float(
                    index_tip.x
                )

                y = float(
                    index_tip.y
                )


                x = max(
                    0.0,
                    min(
                        1.0,
                        x
                    )
                )


                y = max(
                    0.0,
                    min(
                        1.0,
                        y
                    )
                )


                # =================================================
                # NORMAL CURSOR
                # =================================================

                self.finger_moved.emit(
                    x,
                    y
                )


                # =================================================
                # SWIPE
                # =================================================

                self.detect_swipe(
                    x,
                    y
                )


                # =================================================
                # EXISTING REACTOR PROXIMITY
                # =================================================

                self.detect_proximity(
                    x,
                    y
                )


        camera.release()


    # =====================================================
    # SWIPE DETECTION
    # =====================================================

    def detect_swipe(
        self,
        x,
        y
    ):

        now = (
            time.perf_counter()
        )


        if self.swipe_start_x is None:

            self.swipe_start_x = x

            self.swipe_start_y = y

            self.swipe_start_time = now

            return


        elapsed = (
            now
            - self.swipe_start_time
        )


        dx = (
            x
            - self.swipe_start_x
        )


        dy = abs(
            y
            - self.swipe_start_y
        )


        cooldown_ready = (
            now
            - self.last_swipe_time

            >= self.swipe_cooldown
        )


        if (
            cooldown_ready

            and elapsed
            <= self.swipe_max_duration

            and abs(dx)
            >= self.swipe_distance

            and dy
            <= self.swipe_vertical_tolerance
        ):

            self.last_swipe_time = (
                now
            )


            # Because webcam image is mirrored,
            # positive X corresponds to screen-right.
            if dx > 0:

                self.swipe_right.emit()

            else:

                self.swipe_left.emit()


            self.reset_swipe()

            return


        # Restart baseline if movement took too long.
        if (
            elapsed
            > self.swipe_max_duration
        ):

            self.swipe_start_x = x

            self.swipe_start_y = y

            self.swipe_start_time = now


    def reset_swipe(self):

        self.swipe_start_x = None

        self.swipe_start_y = None

        self.swipe_start_time = None


    # =====================================================
    # EXISTING PROXIMITY
    # =====================================================

    def detect_proximity(
        self,
        x,
        y
    ):

        now = (
            time.perf_counter()
        )


        in_zone = (

            0.30 < x < 0.70

            and

            0.20 < y < 0.80
        )


        if in_zone:

            if not self.proximity_active:

                if (
                    now
                    - self.last_proximity_time

                    >= self.proximity_cooldown
                ):

                    self.last_proximity_time = (
                        now
                    )


                    self.pinch_detected.emit(
                        x,
                        y
                    )


                self.proximity_active = True


        else:

            self.proximity_active = False


# =========================================================
# THREAD
# =========================================================

class HandTrackingThread(QThread):

    def __init__(
        self,
        tracker
    ):

        super().__init__()

        self.tracker = (
            tracker
        )


    def run(self):

        self.tracker.start()