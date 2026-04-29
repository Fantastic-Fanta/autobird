# ---------------------------------------------------------------------------
# detector.py — screen capture and OpenCV template-matching detection
# ---------------------------------------------------------------------------

import cv2
import numpy as np
import mss

import config


class Detector:
    def __init__(self):
        self._sct = mss.mss()

        # Load templates in colour and grayscale.
        self._bird_tmpl   = self._load_template(
            config.BIRD_TEMPLATE, config.BIRD_SPRITE_FRAMES, config.BIRD_TEMPLATE_SCALE
        )
        self._top_tmpl    = self._load_template(
            config.PIPE_TOP_TEMPLATE,
            scale=config.PIPE_TEMPLATE_SCALE,
            vcrop=config.PIPE_TOP_TRUNK_CROP,
        )
        self._bottom_tmpl = self._load_template(
            config.PIPE_BOTTOM_TEMPLATE,
            scale=config.PIPE_TEMPLATE_SCALE,
            vcrop=config.PIPE_BOTTOM_TRUNK_CROP,
        )

        self._bird_h,   self._bird_w   = self._bird_tmpl.shape[:2]
        self._top_h,    self._top_w    = self._top_tmpl.shape[:2]
        self._bottom_h, self._bottom_w = self._bottom_tmpl.shape[:2]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_template(
        path: str,
        sprite_frames: int = 1,
        scale: float = 1.0,
        vcrop: tuple = (0.0, 1.0),
    ) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Template not found: {path}")
        if sprite_frames > 1:
            # Sprite sheet: frames are laid out horizontally — take only the first.
            frame_w = img.shape[1] // sprite_frames
            img = img[:, :frame_w]
        if vcrop != (0.0, 1.0):
            h = img.shape[0]
            y0 = int(h * vcrop[0])
            y1 = int(h * vcrop[1])
            img = img[y0:y1]
        if scale != 1.0:
            h, w = img.shape[:2]
            img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
        return img

    @staticmethod
    def _to_gray(bgr: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _match(frame_gray: np.ndarray, tmpl_gray: np.ndarray, threshold: float):
        """Return list of (x, y, confidence) for all matches above threshold."""
        fh, fw = frame_gray.shape[:2]
        th, tw = tmpl_gray.shape[:2]
        if th > fh or tw > fw:
            return []  # template larger than frame — skip silently
        result = cv2.matchTemplate(frame_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        locs = np.where(result >= threshold)
        hits = []
        for y, x in zip(*locs):
            hits.append((int(x), int(y), float(result[y, x])))
        return hits

    @staticmethod
    def _suppress(hits, min_dist: int):
        """Simple greedy non-maximum suppression on the x-axis."""
        if not hits:
            return []
        # Sort by confidence descending so we keep the best hit per column.
        hits = sorted(hits, key=lambda h: -h[2])
        kept = []
        for h in hits:
            if all(abs(h[0] - k[0]) >= min_dist for k in kept):
                kept.append(h)
        return kept

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture(self) -> np.ndarray:
        """Grab the configured screen region and return a BGR numpy array."""
        raw = self._sct.grab(config.REGION)
        # mss returns BGRA; drop the alpha channel.
        frame = np.array(raw)[:, :, :3]
        return frame

    def find_bird(self, frame: np.ndarray):
        """
        Locate the bird in *frame* using template matching.

        Returns (cx, cy) — the centre of the best match — or None if the
        confidence is below BIRD_THRESHOLD.
        """
        gray = self._to_gray(frame)
        tmpl_gray = self._to_gray(self._bird_tmpl)

        fh, fw = gray.shape[:2]
        th, tw = tmpl_gray.shape[:2]
        if th > fh or tw > fw:
            return None  # template larger than frame — skip silently

        result = cv2.matchTemplate(gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if config.DEBUG:
            print(f"bird match score: {max_val:.3f} (threshold={config.BIRD_THRESHOLD})")

        if max_val < config.BIRD_THRESHOLD:
            return None

        x, y = max_loc
        cx = x + self._bird_w // 2
        cy = y + self._bird_h // 2
        return (cx, cy)

    def find_pipes(self, frame: np.ndarray) -> list:
        """
        Detect pipe (tree) pairs in *frame*.

        Returns a list of dicts, each representing one pipe column:
          {
            "x":       int,   # x-centre of the pipe column (pixels from left of region)
            "gap_y":   int,   # y-centre of the gap between top and bottom pipe
            "top_rect":    (x, y, w, h),  # bounding box of the top pipe match
            "bot_rect":    (x, y, w, h),  # bounding box of the bottom pipe match
          }
        """
        gray = self._to_gray(frame)
        top_gray    = self._to_gray(self._top_tmpl)
        bottom_gray = self._to_gray(self._bottom_tmpl)

        # Find all candidate matches for each pipe type.
        top_hits    = self._suppress(
            self._match(gray, top_gray,    config.PIPE_THRESHOLD),
            config.PIPE_SUPPRESS_DIST,
        )
        bottom_hits = self._suppress(
            self._match(gray, bottom_gray, config.PIPE_THRESHOLD),
            config.PIPE_SUPPRESS_DIST,
        )

        # Pair top and bottom hits that share roughly the same x-column.
        pairs = []
        used_bottom = set()

        for tx, ty, _ in top_hits:
            best_dist = config.PIPE_PAIR_TOLERANCE + 1
            best_idx  = -1
            for i, (bx, by, _) in enumerate(bottom_hits):
                if i in used_bottom:
                    continue
                dist = abs(tx - bx)
                if dist < best_dist:
                    best_dist = dist
                    best_idx  = i

            if best_idx == -1:
                continue  # no matching bottom pipe found

            bx, by, _ = bottom_hits[best_idx]
            used_bottom.add(best_idx)

            # Gap boundaries: bottom edge of top pipe ↔ top edge of bottom pipe.
            top_bottom_edge    = ty + self._top_h
            bottom_top_edge    = by
            gap_y = (top_bottom_edge + bottom_top_edge) // 2

            col_x = (tx + self._top_w // 2 + bx + self._bottom_w // 2) // 2

            pairs.append({
                "x":        col_x,
                "gap_y":    gap_y,
                "top_rect":    (tx, ty, self._top_w, self._top_h),
                "bot_rect":    (bx, by, self._bottom_w, self._bottom_h),
            })

        return pairs

    def next_pipe(self, pipes: list, bird_x: int):
        """
        Return the pipe column that is immediately ahead of the bird
        (closest pipe whose x-centre is greater than bird_x), or None.
        """
        ahead = [p for p in pipes if p["x"] > bird_x]
        if not ahead:
            return None
        return min(ahead, key=lambda p: p["x"])

    # ------------------------------------------------------------------
    # Debug overlay
    # ------------------------------------------------------------------

    def draw_debug(
        self,
        frame: np.ndarray,
        bird_pos,
        pipes: list,
        next_p,
    ) -> np.ndarray:
        """Draw detection overlays onto a copy of *frame* and return it."""
        out = frame.copy()

        # All detected pipe bounding boxes (dim blue).
        for p in pipes:
            tx, ty, tw, th = p["top_rect"]
            bx, by, bw, bh = p["bot_rect"]
            cv2.rectangle(out, (tx, ty), (tx + tw, ty + th), (180, 80, 0), 1)
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (180, 80, 0), 1)

        # Next pipe: bright orange boxes + gap line.
        if next_p is not None:
            tx, ty, tw, th = next_p["top_rect"]
            bx, by, bw, bh = next_p["bot_rect"]
            cv2.rectangle(out, (tx, ty), (tx + tw, ty + th), (0, 140, 255), 2)
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (0, 140, 255), 2)
            # Horizontal line at gap centre.
            gy = next_p["gap_y"]
            cv2.line(out, (0, gy), (out.shape[1], gy), (0, 255, 255), 1)
            cv2.putText(
                out, f"gap y={gy}", (tx, gy - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1,
            )

        # Bird dot + coordinates.
        if bird_pos is not None:
            cx, cy = bird_pos
            cv2.circle(out, (cx, cy), 6, (0, 255, 0), -1)
            cv2.putText(
                out, f"bird ({cx},{cy})", (cx + 8, cy - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
            )

        return out
