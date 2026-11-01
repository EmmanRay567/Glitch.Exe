import math
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
)


class HandTracker(QObject):

    # Smoothed index-fingertip position, emitted every frame while a
    # hand is visible (normalized 0..1, already mirrored). Drives the
    # holographic pointer and button hover.
    finger_moved = Signal(
        float,
        float
    )

    # Emitted only when a real pinch-selection is detected.
    pinch_detected = Signal(
        float,
        float
    )

    swipe_left = Signal()
    swipe_right = Signal()

    # Vertical swipes: move between HUD sections
    # (HOME, CHAT, CREATE, SEARCH, ...).
    swipe_up = Signal()
    swipe_down = Signal()

    # -1.0 .. 1.0 live vertical charge (negative = moving up).
    swipe_charge_vertical = Signal(float)

    # NEW: all 21 hand landmarks as [(x, y), ...] (normalized 0..1,
    # already mirrored to match the screen). Drives the hand hologram.
    landmarks_updated = Signal(list)

    # NEW: emitted once when the hand leaves the camera view.
    hand_lost = Signal()

    # NEW: -1.0 .. 1.0 live "swipe charge" (sign = screen direction the
    # hand is moving). Drives the chevrons that build before a swipe.
    swipe_charge = Signal(float)

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
        # FAST SWIPE DETECTION
        # =================================================

        self.motion_history = deque(
            maxlen=14
        )

        self.swipe_window_seconds = 0.30

        self.swipe_distance = 0.025

        self.horizontal_ratio = 1.05

        self.minimum_velocity = 0.07

        self.fast_swipe_velocity = 0.16

        self.swipe_cooldown = 0.28

        self.last_swipe_time = 0.0


        # =================================================
        # SWIPE CHARGE (visual feedback only)
        # =================================================

        # Hand speed (normalized screen widths / second) that maps
        # to a fully charged (1.0) indicator.
        self.charge_full_velocity = 0.45

        self._last_charge = 0.0

        self._last_charge_vertical = 0.0

        self._had_hand = False


        # =================================================
        # VERTICAL SWIPE (section change)
        # =================================================

        # Stricter than horizontal: hands drift up/down naturally,
        # and raising or dropping a hand must not change sections.
        self.vertical_ratio = 1.25

        self.vertical_swipe_distance = 0.06

        self.vertical_minimum_velocity = 0.20

        self.vertical_fast_velocity = 0.34

        # The hand must have been tracked this long before a vertical
        # swipe counts (stops "raising my hand into view" = swipe up).
        self.vertical_settle_s = 0.35

        # A vertical swipe is held this long and cancelled if the hand
        # leaves the frame (stops "dropping my hand" = swipe down).
        self.vertical_confirm_s = 0.12

        self._hand_seen_since = None

        self._pending_vertical = None


        # =================================================
        # SMOOTHING
        # =================================================

        self.x_smoothing = deque(
            maxlen=3
        )

        self.y_smoothing = deque(
            maxlen=3
        )


        # =================================================
        # PINCH-TO-SELECT
        # =================================================

        # Ratio of thumb-tip/index-tip distance to palm width.
        # This scales naturally when your hand is closer/farther away.
        self.pinch_close_ratio = 0.68

        # Must open farther than this before another click is allowed.
        self.pinch_release_ratio = 0.90

        self.pinch_active = False

        self.pinch_cooldown = 0.20

        self.last_pinch_time = 0.0


        # =================================================
        # FINGER POINTER (hover + aimed click)
        # =================================================

        # Smoothed index-fingertip position, emitted every frame via
        # finger_moved so the HUD can show a pointer and hover state.
        self._pointer = None

        # (time, x, y) samples of the smoothed pointer. When a pinch
        # fires, the fingertip has already drifted toward the thumb,
        # so the click is reported where the finger was a moment ago.
        self._pointer_history = deque(
            maxlen=40
        )

        self.pinch_lookback_s = 0.12


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

            min_hand_detection_confidence=0.40,

            min_hand_presence_confidence=0.40,

            min_tracking_confidence=0.40,
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


        # =================================================
        # SHARPER CAMERA CAPTURE
        # =================================================

        camera.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            1280
        )

        camera.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            720
        )

        camera.set(
            cv2.CAP_PROP_FPS,
            30
        )

        camera.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1
        )


        self.tracking_started.emit()

        timestamp_ms = 0


        try:

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

                        self.clear_motion_history()

                        self.pinch_active = False

                        self._pointer = None

                        self._pointer_history.clear()

                        self._hand_seen_since = None

                        self._pending_vertical = None

                        if self._had_hand:

                            self._had_hand = False

                            self.hand_lost.emit()

                        continue


                    landmarks = (
                        result.hand_landmarks[0]
                    )


                    # =========================================
                    # HAND HOLOGRAM FEED
                    # =========================================

                    self._had_hand = True

                    if self._hand_seen_since is None:

                        self._hand_seen_since = time.perf_counter()

                    self.flush_pending_vertical()

                    self.landmarks_updated.emit(
                        [
                            (
                                float(point.x),
                                float(point.y),
                            )
                            for point in landmarks
                        ]
                    )


                    # =========================================
                    # FINGER POINTER
                    # =========================================

                    self.update_pointer(
                        landmarks
                    )


                    # =========================================
                    # PINCH SELECT
                    # =========================================

                    pinch_now = (
                        self.detect_pinch(
                            landmarks
                        )
                    )


                    # While pinching, do not interpret the same
                    # hand movement as a page swipe.
                    if pinch_now:

                        self.clear_motion_history()

                        continue


                    # =========================================
                    # PALM CENTER FOR SWIPE
                    # =========================================

                    palm_indices = [
                        0,
                        5,
                        9,
                        13,
                        17,
                    ]


                    raw_x = sum(
                        float(
                            landmarks[index].x
                        )
                        for index in palm_indices
                    ) / len(
                        palm_indices
                    )


                    raw_y = sum(
                        float(
                            landmarks[index].y
                        )
                        for index in palm_indices
                    ) / len(
                        palm_indices
                    )


                    raw_x = max(
                        0.0,
                        min(
                            1.0,
                            raw_x
                        )
                    )


                    raw_y = max(
                        0.0,
                        min(
                            1.0,
                            raw_y
                        )
                    )


                    self.x_smoothing.append(
                        raw_x
                    )

                    self.y_smoothing.append(
                        raw_y
                    )


                    x = (
                        sum(
                            self.x_smoothing
                        )
                        / len(
                            self.x_smoothing
                        )
                    )


                    y = (
                        sum(
                            self.y_smoothing
                        )
                        / len(
                            self.y_smoothing
                        )
                    )


                    self.track_motion(
                        x,
                        y
                    )

        finally:

            camera.release()


    # =====================================================
    # FINGER POINTER
    # =====================================================

    def update_pointer(
        self,
        landmarks
    ):

        tip = landmarks[8]

        raw_x = max(
            0.0,
            min(
                1.0,
                float(tip.x)
            )
        )

        raw_y = max(
            0.0,
            min(
                1.0,
                float(tip.y)
            )
        )

        now = time.perf_counter()

        if self._pointer is None:

            x, y = raw_x, raw_y

        else:

            old_x, old_y = self._pointer

            speed = math.hypot(
                raw_x - old_x,
                raw_y - old_y
            )

            # Adaptive smoothing: heavy when the hand is nearly
            # still (kills jitter so hover is stable), light when
            # it moves fast (kills lag).
            blend = max(
                0.22,
                min(
                    0.85,
                    0.22 + speed * 14.0
                )
            )

            x = old_x + (raw_x - old_x) * blend

            y = old_y + (raw_y - old_y) * blend

        self._pointer = (x, y)

        self._pointer_history.append(
            (now, x, y)
        )

        self.finger_moved.emit(
            x,
            y
        )


    def pointer_before_pinch(
        self,
        now
    ):

        if not self._pointer_history:

            return None

        wanted = now - self.pinch_lookback_s

        best = min(
            self._pointer_history,
            key=lambda sample: abs(
                sample[0] - wanted
            )
        )

        return (
            best[1],
            best[2]
        )


    # =====================================================
    # PINCH DETECTION
    # =====================================================

    def detect_pinch(
        self,
        landmarks
    ):

        now = (
            time.perf_counter()
        )


        thumb_tip = (
            landmarks[4]
        )

        index_tip = (
            landmarks[8]
        )

        index_mcp = (
            landmarks[5]
        )

        pinky_mcp = (
            landmarks[17]
        )


        pinch_distance = math.hypot(
            float(
                index_tip.x
                - thumb_tip.x
            ),
            float(
                index_tip.y
                - thumb_tip.y
            )
        )


        palm_width = math.hypot(
            float(
                index_mcp.x
                - pinky_mcp.x
            ),
            float(
                index_mcp.y
                - pinky_mcp.y
            )
        )


        if palm_width <= 0.0001:

            return False


        pinch_ratio = (
            pinch_distance
            / palm_width
        )


        # Release gate: your fingers must separate before
        # another HUD selection can occur.
        if self.pinch_active:

            if (
                pinch_ratio
                >= self.pinch_release_ratio
            ):

                self.pinch_active = False

            return True


        if (
            pinch_ratio
            <= self.pinch_close_ratio
            and (
                now
                - self.last_pinch_time
                >= self.pinch_cooldown
            )
        ):

            self.pinch_active = True

            self.last_pinch_time = now


            aimed = self.pointer_before_pinch(
                now
            )

            if aimed is not None:

                self.pinch_detected.emit(
                    aimed[0],
                    aimed[1]
                )

                return True


            x = max(
                0.0,
                min(
                    1.0,
                    float(
                        index_tip.x
                    )
                )
            )


            y = max(
                0.0,
                min(
                    1.0,
                    float(
                        index_tip.y
                    )
                )
            )


            self.pinch_detected.emit(
                x,
                y
            )


            return True


        return False


    # =====================================================
    # SWIPE MOTION HISTORY
    # =====================================================

    def track_motion(
        self,
        x,
        y
    ):

        now = (
            time.perf_counter()
        )


        self.motion_history.append(
            (
                now,
                x,
                y,
            )
        )


        while (
            self.motion_history
            and (
                now
                - self.motion_history[0][0]
                > self.swipe_window_seconds
            )
        ):

            self.motion_history.popleft()


        self.emit_swipe_charge()


        self.detect_swipe_from_history(
            now
        )


    # =====================================================
    # SWIPE CHARGE (visual feedback)
    # =====================================================

    def emit_swipe_charge(self):

        charge = 0.0


        if len(self.motion_history) >= 3:

            start_time, start_x, start_y = (
                self.motion_history[0]
            )

            end_time, end_x, end_y = (
                self.motion_history[-1]
            )

            duration = (
                end_time
                - start_time
            )

            dx = (
                end_x
                - start_x
            )

            dy = (
                end_y
                - start_y
            )

            if (
                duration > 0.04
                and abs(dx)
                >= abs(dy)
                * self.horizontal_ratio
            ):

                velocity = (
                    dx
                    / duration
                )

                charge = max(
                    -1.0,
                    min(
                        1.0,
                        velocity
                        / self.charge_full_velocity
                    )
                )


        self._last_charge = charge

        self.swipe_charge.emit(
            charge
        )


        vertical = 0.0

        if len(self.motion_history) >= 3:

            start_time, start_x, start_y = self.motion_history[0]

            end_time, end_x, end_y = self.motion_history[-1]

            duration = end_time - start_time

            dx = end_x - start_x

            dy = end_y - start_y

            if (
                duration > 0.04
                and abs(dy) >= abs(dx) * self.vertical_ratio
            ):

                vertical = max(
                    -1.0,
                    min(
                        1.0,
                        (dy / duration) / (self.vertical_fast_velocity * 1.4)
                    )
                )

        if vertical != 0.0 or self._last_charge_vertical != 0.0:

            self._last_charge_vertical = vertical

            self.swipe_charge_vertical.emit(
                vertical
            )


    # =====================================================
    # SWIPE DETECTION
    # =====================================================

    def detect_swipe_from_history(
        self,
        now
    ):

        if (
            now
            - self.last_swipe_time
            < self.swipe_cooldown
        ):

            return


        if len(
            self.motion_history
        ) < 4:

            return


        start_time, start_x, start_y = (
            self.motion_history[0]
        )

        end_time, end_x, end_y = (
            self.motion_history[-1]
        )


        duration = (
            end_time
            - start_time
        )


        if duration <= 0:
            return


        dx = (
            end_x
            - start_x
        )

        dy = (
            end_y
            - start_y
        )


        abs_dx = abs(
            dx
        )

        abs_dy = abs(
            dy
        )


        velocity = (
            abs_dx
            / duration
        )


        horizontal_motion = (
            abs_dx
            >= (
                abs_dy
                * self.horizontal_ratio
            )
        )


        if not horizontal_motion:

            self.detect_vertical_swipe(
                now,
                dx,
                dy,
                duration
            )

            return


        normal_swipe = (
            abs_dx
            >= self.swipe_distance
            and velocity
            >= self.minimum_velocity
        )


        fast_swipe = (
            abs_dx
            >= 0.018
            and velocity
            >= self.fast_swipe_velocity
        )


        if not (
            normal_swipe
            or fast_swipe
        ):

            return


        xs = [
            point[1]
            for point in self.motion_history
        ]


        positive_motion = 0

        negative_motion = 0


        for index in range(
            1,
            len(xs)
        ):

            delta = (
                xs[index]
                - xs[index - 1]
            )


            if abs(
                delta
            ) < 0.0015:

                continue


            if delta > 0:

                positive_motion += 1

            else:

                negative_motion += 1


        total_direction_frames = (
            positive_motion
            + negative_motion
        )


        if total_direction_frames == 0:
            return


        direction_confidence = (
            max(
                positive_motion,
                negative_motion
            )
            / total_direction_frames
        )


        if direction_confidence < 0.65:
            return


        self.last_swipe_time = (
            now
        )


        # Camera frame is mirrored.
        if dx > 0:

            self.swipe_left.emit()

        else:

            self.swipe_right.emit()


        self.clear_motion_history()


    # =====================================================
    # VERTICAL SWIPE DETECTION
    # =====================================================

    def detect_vertical_swipe(
        self,
        now,
        dx,
        dy,
        duration
    ):

        if self._pending_vertical is not None:

            return

        if (
            self._hand_seen_since is None
            or now - self._hand_seen_since < self.vertical_settle_s
        ):

            return

        abs_dx = abs(dx)

        abs_dy = abs(dy)

        if abs_dy < abs_dx * self.vertical_ratio:

            return

        velocity = abs_dy / duration

        normal_swipe = (
            abs_dy >= self.vertical_swipe_distance
            and velocity >= self.vertical_minimum_velocity
        )

        fast_swipe = (
            abs_dy >= self.vertical_swipe_distance * 0.7
            and velocity >= self.vertical_fast_velocity
        )

        if not (normal_swipe or fast_swipe):

            return

        ys = [point[2] for point in self.motion_history]

        same = 0

        moving = 0

        for index in range(1, len(ys)):

            delta = ys[index] - ys[index - 1]

            if abs(delta) < 0.0015:

                continue

            moving += 1

            if (delta > 0) == (dy > 0):

                same += 1

        if moving == 0 or same / moving < 0.70:

            return

        self.last_swipe_time = now

        # Image y grows downward: negative dy = hand moved up.
        self._pending_vertical = (
            -1 if dy < 0 else 1,
            now,
        )

        self.clear_motion_history()


    def flush_pending_vertical(self):

        if self._pending_vertical is None:

            return

        direction, started = self._pending_vertical

        if time.perf_counter() - started < self.vertical_confirm_s:

            return

        self._pending_vertical = None

        if direction < 0:

            self.swipe_up.emit()

        else:

            self.swipe_down.emit()


    # =====================================================
    # CLEAR HISTORY
    # =====================================================

    def clear_motion_history(self):

        self.motion_history.clear()

        self.x_smoothing.clear()

        self.y_smoothing.clear()


        # Drop the charge indicator back to zero (only emit if it
        # was non-zero, so we don't spam signals every frame).
        if self._last_charge != 0.0:

            self._last_charge = 0.0

            self.swipe_charge.emit(
                0.0
            )

        if self._last_charge_vertical != 0.0:

            self._last_charge_vertical = 0.0

            self.swipe_charge_vertical.emit(
                0.0
            )


# =========================================================
# HAND TRACKING THREAD
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