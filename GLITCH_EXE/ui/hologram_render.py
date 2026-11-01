"""
ui/hologram_render.py

Turns the live webcam frame into a holographic "digital twin" of the person
in front of the camera. Pure numpy + OpenCV (no Qt), so it is easy to test.

    upper body   the user's own camera image rebuilt as a hologram:
                 topographic iso-lines + edge contours + scanlines + a
                 travelling scan band, masked to the person's silhouette

    lower body   a wireframe "extrusion" of the user's own silhouette:
                 cross-section rings, meridian lines and arms, sized from the
                 measured shoulder width and centred where the user sits, fading
                 into the projector base

Silhouette source, best first:
    MODEL        MediaPipe selfie segmenter (selfie_segmenter.tflite, ~250 KB,
                 downloaded in the background the first time; optional)
    FACE-GUIDED  OpenCV's built-in Haar face detector sizes + places a
                 head-and-shoulders silhouette on the person
    ESTIMATED    a generic centred head-and-shoulders silhouette

render() returns an RGBA uint8 array (H, W, 4), straight (non-premultiplied)
alpha, ready for QImage.Format_RGBA8888.
"""

from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

import numpy as np

import cv2


SEGMENTER_URL = (
    "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)

GREEN = (57, 255, 120)
HOT = (200, 255, 235)


def _smoothstep(edge0, edge1, x):

    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)

    return t * t * (3.0 - 2.0 * t)


class HologramRenderer:

    W = 340
    H = 500
    BUST_H = 360

    def __init__(
        self,
        segmenter_model=None,
        auto_download=True,
    ):

        self.segmenter_model = (
            Path(segmenter_model) if segmenter_model else None
        )

        self._segmenter = None
        self._segmenter_failed = False
        self._download_started = False

        self._clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(6, 6),
        )

        self._cascade = None

        try:

            self._cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades
                + "haarcascade_frontalface_default.xml"
            )

            if self._cascade.empty():

                self._cascade = None

        except Exception:

            self._cascade = None

        self._rng = np.random.default_rng()

        self._frame_index = 0

        self._face = None            # smoothed (x, y, w, h) in bust space
        self._seg_mask = None        # last model mask, float32 0..1
        self._prior_cache = None

        self.last_info = {
            "mode": "ESTIMATED",
            "face_box": None,
            "shoulder_px": self.W * 0.7,
            "body_cx": self.W / 2,
        }

        if (
            auto_download
            and self.segmenter_model is not None
            and not self.segmenter_model.exists()
        ):

            self._start_download()

    # =====================================================
    # LIFECYCLE
    # =====================================================

    def reset(self):
        """Forget the previous person (call at the start of a new scan)."""

        self._face = None
        self._seg_mask = None
        self._frame_index = 0

    def close(self):

        segmenter = self._segmenter

        self._segmenter = None

        if segmenter is not None:

            try:

                segmenter.close()

            except Exception:

                pass

    def _start_download(self):

        if self._download_started:

            return

        self._download_started = True

        target = self.segmenter_model

        def work():

            try:

                target.parent.mkdir(parents=True, exist_ok=True)

                temp = target.with_suffix(".part")

                with urllib.request.urlopen(
                    SEGMENTER_URL,
                    timeout=30,
                ) as response:

                    data = response.read()

                if len(data) < 50_000:

                    return

                temp.write_bytes(data)

                temp.replace(target)

            except Exception:

                pass

        threading.Thread(target=work, daemon=True).start()

    # =====================================================
    # SILHOUETTE
    # =====================================================

    def _ensure_segmenter(self):

        if (
            self._segmenter is not None
            or self._segmenter_failed
            or self.segmenter_model is None
            or not self.segmenter_model.exists()
        ):

            return

        try:

            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            options = vision.ImageSegmenterOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=str(self.segmenter_model)
                ),
                running_mode=vision.RunningMode.IMAGE,
                output_category_mask=False,
                output_confidence_masks=True,
            )

            self._segmenter = vision.ImageSegmenter.create_from_options(
                options
            )

            self._mp = mp

        except Exception:

            self._segmenter_failed = True

    def _model_mask(self, bust_rgb):

        self._ensure_segmenter()

        if self._segmenter is None:

            return None

        try:

            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(bust_rgb),
            )

            result = self._segmenter.segment(image)

            masks = result.confidence_masks

            if not masks:

                return None

            # Person probability is the last category.
            mask = np.asarray(
                masks[-1].numpy_view(),
                dtype=np.float32,
            ).copy()

            if mask.shape != (self.BUST_H, self.W):

                mask = cv2.resize(mask, (self.W, self.BUST_H))

            # Different model builds disagree on which channel is the
            # person. The person is nearly always centred, so if the border
            # is "more person" than the centre, invert.
            centre = float(mask[
                self.BUST_H // 4: 3 * self.BUST_H // 4,
                self.W // 4: 3 * self.W // 4,
            ].mean())

            border = float(
                np.concatenate(
                    [
                        mask[:, :20].ravel(),
                        mask[:, -20:].ravel(),
                    ]
                ).mean()
            )

            if border > centre:

                mask = 1.0 - mask

            return _smoothstep(0.35, 0.75, mask).astype(np.float32)

        except Exception:

            self._segmenter_failed = True

            return None

    def _detect_face(self, bust_rgb):

        if self._cascade is None:

            return None

        try:

            gray = cv2.cvtColor(bust_rgb, cv2.COLOR_RGB2GRAY)

            small = cv2.resize(gray, (self.W // 2, self.BUST_H // 2))

            faces = self._cascade.detectMultiScale(
                small,
                scaleFactor=1.15,
                minNeighbors=5,
                minSize=(34, 34),
            )

            if len(faces) == 0:

                return None

            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])

            return (float(x * 2), float(y * 2), float(w * 2), float(h * 2))

        except Exception:

            return None

    def _update_face(self, detected):

        if detected is None:

            return

        if self._face is None:

            self._face = detected

            return

        a = 0.35

        self._face = tuple(
            old + (new - old) * a
            for old, new in zip(self._face, detected)
        )

    def _prior_mask(self):
        """Head-and-shoulders silhouette sized from the face box."""

        W, BH = self.W, self.BUST_H

        if self._face is None:

            fx, fy, fw, fh = W * 0.5 - 52, BH * 0.14, 104.0, 128.0

        else:

            fx, fy, fw, fh = self._face

        cx = fx + fw / 2
        cy = fy + fh / 2

        mask = np.zeros((BH, W), np.float32)

        # Head.
        cv2.ellipse(
            mask,
            (int(cx), int(cy - 0.05 * fh)),
            (max(4, int(0.64 * fw)), max(4, int(0.80 * fh))),
            0, 0, 360, 1.0, -1,
        )

        # Neck.
        cv2.rectangle(
            mask,
            (int(cx - 0.30 * fw), int(cy + 0.4 * fh)),
            (int(cx + 0.30 * fw), int(cy + 1.2 * fh)),
            1.0,
            -1,
        )

        # Shoulders / chest.
        cv2.ellipse(
            mask,
            (int(cx), int(fy + fh + 1.30 * fh)),
            (max(8, int(1.65 * fw)), max(8, int(1.05 * fh))),
            0, 0, 360, 1.0, -1,
        )

        return cv2.GaussianBlur(mask, (0, 0), 6)

    def _silhouette(self, bust_rgb):
        """Returns (mask, mode)."""

        if bust_rgb is None:

            return self._prior_mask(), "ESTIMATED"

        # Model mask every 2nd frame (it is the expensive part).
        if self._frame_index % 2 == 0:

            fresh = self._model_mask(bust_rgb)

            if fresh is not None:

                if self._seg_mask is None:

                    self._seg_mask = fresh

                else:

                    self._seg_mask = 0.55 * self._seg_mask + 0.45 * fresh

        if self._seg_mask is not None and self._segmenter is not None:

            return cv2.GaussianBlur(self._seg_mask, (0, 0), 2.0), "MODEL"

        if self._frame_index % 4 == 0:

            self._update_face(self._detect_face(bust_rgb))

        mode = "FACE-GUIDED" if self._face is not None else "ESTIMATED"

        return self._prior_mask(), mode

    # =====================================================
    # BODY METRICS
    # =====================================================

    def _body_metrics(self, mask):

        W, BH = self.W, self.BUST_H

        band = mask[BH - 40: BH - 6] > 0.5

        widths = band.sum(axis=1).astype(np.float32)

        valid = widths > 0.2 * W

        if not np.any(valid):

            return W / 2.0, W * 0.72

        shoulder = float(np.median(widths[valid]))

        xs = np.arange(W, dtype=np.float32)[None, :]

        centres = (band * xs).sum(axis=1)[valid] / widths[valid]

        return (
            float(np.clip(np.median(centres), W * 0.3, W * 0.7)),
            float(np.clip(shoulder, W * 0.45, W * 0.96)),
        )

    # =====================================================
    # RENDER
    # =====================================================

    def _crop_bust(self, frame_rgb):

        if frame_rgb is None:

            return None

        h, w = frame_rgb.shape[:2]

        target = self.W / self.BUST_H

        if w / h > target:

            cw = int(h * target)

            x0 = (w - cw) // 2

            crop = frame_rgb[:, x0: x0 + cw]

        else:

            ch = int(w / target)

            y0 = max(0, (h - ch) // 3)

            crop = frame_rgb[y0: y0 + ch, :]

        return cv2.resize(
            crop,
            (self.W, self.BUST_H),
            interpolation=cv2.INTER_AREA,
        )

    def render(
        self,
        frame_rgb,
        t,
        tint=GREEN,
        reveal=1.0,
        glitch=0.0,
        flash=0.0,
        dissolve=0.0,
    ):

        W, H, BH = self.W, self.H, self.BUST_H

        self._frame_index += 1

        bust = self._crop_bust(frame_rgb)

        mask, mode = self._silhouette(bust)

        body_cx, shoulder = self._body_metrics(mask)

        # ------------------------------------------------
        # Upper body: iso-lines + edges of the real image
        # ------------------------------------------------

        if bust is not None:

            gray = cv2.cvtColor(bust, cv2.COLOR_RGB2GRAY)

            gray = self._clahe.apply(gray)

            blur = cv2.GaussianBlur(gray, (5, 5), 0)

            luminance = blur.astype(np.float32) / 255.0

            edges = cv2.Canny(blur, 40, 110).astype(np.float32) / 255.0

            edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))

        else:

            ramp = np.linspace(0.85, 0.25, BH, dtype=np.float32)[:, None]

            luminance = np.repeat(ramp, W, axis=1)

            blur = (luminance * 255).astype(np.uint8)

            outline = cv2.Canny(
                (mask * 255).astype(np.uint8),
                40,
                120,
            )

            edges = outline.astype(np.float32) / 255.0

        levels = (blur // 26).astype(np.int16)

        iso = np.zeros_like(luminance)

        iso[:, 1:] = np.maximum(
            iso[:, 1:],
            (levels[:, 1:] != levels[:, :-1]).astype(np.float32),
        )

        iso[1:, :] = np.maximum(
            iso[1:, :],
            (levels[1:, :] != levels[:-1, :]).astype(np.float32),
        )

        bust_i = 0.28 * luminance + 0.42 * iso + 1.0 * edges

        bust_i *= (0.04 + 0.96 * mask)

        # Dissolve into the projector below the chest.
        rows_b = np.arange(BH, dtype=np.float32)[:, None]

        bust_i *= 1.0 - 0.75 * _smoothstep(0.70 * BH, BH, rows_b)

        canvas = np.zeros((H, W), np.float32)

        canvas[:BH] = bust_i

        # ------------------------------------------------
        # Lower body: wireframe extrusion of the silhouette
        # ------------------------------------------------

        wire = np.zeros((H, W), np.uint8)

        top = BH - 34

        span = float(H - 8 - top)

        def width_at(y):

            s = _smoothstep(0.0, 1.0, (y - top) / span)

            return shoulder * (1.0 - 0.34 * s)

        ring_ys = list(range(top, H - 8, 12))

        for y in ring_ys:

            s = (y - top) / span

            fade = max(0.0, 1.0 - s) ** 0.9

            half = width_at(y) / 2.0

            ry = max(2, int(half * 0.10))

            centre = (int(body_cx), int(y))

            cv2.ellipse(
                wire, centre, (int(half), ry), 0, 0, 180,
                int(235 * fade), 1, cv2.LINE_AA,
            )

            cv2.ellipse(
                wire, centre, (int(half), ry), 0, 180, 360,
                int(90 * fade), 1, cv2.LINE_AA,
            )

        for u in (-0.95, -0.5, 0.0, 0.5, 0.95):

            for a, b in zip(ring_ys[:-1], ring_ys[1:]):

                s = (a - top) / span

                fade = max(0.0, 1.0 - s) ** 1.1

                cv2.line(
                    wire,
                    (int(body_cx + u * width_at(a) / 2), a),
                    (int(body_cx + u * width_at(b) / 2), b),
                    int(120 * fade),
                    1,
                    cv2.LINE_AA,
                )

        # Arms hanging from the measured shoulder line.
        shoulder_y = BH - 26

        for side in (-1, 1):

            joints = [
                (body_cx + side * shoulder * 0.47, shoulder_y),
                (body_cx + side * shoulder * 0.55, shoulder_y + (H - BH) * 0.42),
                (body_cx + side * shoulder * 0.47, H - 14),
            ]

            for k in range(2):

                fade = 1.0 - 0.45 * k

                p1 = (int(joints[k][0]), int(joints[k][1]))
                p2 = (int(joints[k + 1][0]), int(joints[k + 1][1]))

                cv2.line(wire, p1, p2, int(210 * fade), 2, cv2.LINE_AA)

            for k, joint in enumerate(joints):

                cv2.circle(
                    wire,
                    (int(joint[0]), int(joint[1])),
                    3,
                    int(255 * (1.0 - 0.3 * k)),
                    -1,
                    cv2.LINE_AA,
                )

        wire_f = wire.astype(np.float32) / 255.0

        glow = cv2.GaussianBlur(wire_f, (0, 0), 3.0)

        # ------------------------------------------------
        # Combine + hologram treatment
        # ------------------------------------------------

        intensity = canvas + 0.95 * wire_f + 0.6 * glow

        support = np.clip(intensity * 3.0, 0.0, 1.0)

        rows = np.arange(H, dtype=np.float32)[:, None]

        # Scanlines + interlace flicker.
        scan = np.where((np.arange(H) % 3) == 0, 0.62, 1.0).astype(
            np.float32
        )[:, None]

        scan = scan * (0.93 + 0.07 * np.sin(t * 38.0 + rows * 0.45))

        intensity = intensity * scan

        # Travelling scan band.
        sweep_y = ((t * 110.0) % (H + 180.0)) - 90.0

        band = np.exp(-(((rows - sweep_y) / 15.0) ** 2))

        intensity = intensity + 0.55 * band * support

        # Reveal: the figure is scanned up out of the projector base.
        if reveal < 1.0:

            edge_y = H * (1.0 - float(reveal))

            visible = np.clip((rows - edge_y) / 10.0, 0.0, 1.0)

            line = np.exp(-(((rows - edge_y) / 3.0) ** 2))

            intensity = intensity * visible + 1.1 * line * 0.5

        intensity = np.clip(intensity, 0.0, 1.5)

        alpha = np.clip(intensity ** 0.85 * 1.05, 0.0, 1.0)

        base = np.array(tint, np.float32)[None, None, :]

        hot = np.array(HOT, np.float32)[None, None, :]

        rgb = (
            base * (intensity[..., None] ** 0.9)
            + hot * np.clip(intensity - 0.75, 0.0, 1.0)[..., None] * 0.9
        )

        if flash > 0.0:

            rgb = rgb + (255.0 - rgb) * (0.65 * flash)

            alpha = np.clip(alpha + 0.30 * flash * support, 0.0, 1.0)

        rgb = np.clip(rgb, 0.0, 255.0)

        out = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)

        # ------------------------------------------------
        # Glitch / dissolve (alerts)
        # ------------------------------------------------

        if glitch > 0.0:

            count = int(2 + 9 * glitch)

            for _ in range(count):

                y0 = int(self._rng.integers(0, H - 12))

                band_h = int(self._rng.integers(3, 22))

                dx = int(self._rng.integers(-26, 27) * glitch)

                out[y0: y0 + band_h] = np.roll(
                    out[y0: y0 + band_h],
                    dx,
                    axis=1,
                )

        if dissolve > 0.0:

            blocks = self._rng.random((H // 5 + 1, W // 5 + 1))

            keep = np.kron(
                blocks > dissolve * 0.92,
                np.ones((5, 5)),
            )[:H, :W]

            out[..., 3] = (out[..., 3] * keep).astype(np.uint8)

        # ------------------------------------------------
        # Info for the UI
        # ------------------------------------------------

        face_box = None

        if self._face is not None and mode != "ESTIMATED":

            face_box = tuple(float(v) for v in self._face)

        self.last_info = {
            "mode": mode,
            "face_box": face_box,
            "shoulder_px": shoulder,
            "body_cx": body_cx,
        }

        return np.ascontiguousarray(out)
