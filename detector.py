# ---------------------------------------------------------------------------
# detector.py — screen capture and OpenCV template-matching detection
# ---------------------------------------------------------------------------

import time
import cv2
import numpy as np
import mss

import config


class Detector:
    def __init__(self):
        self._sct = mss.mss()
        self._bird_smooth = None   # EMA-smoothed (cx, cy) or None

        # Load all animation frames of the bird sprite as separate templates + masks.
        self._bird_tmpls, self._bird_masks = self._load_bird_frames(
            config.BIRD_TEMPLATE, config.BIRD_SPRITE_FRAMES, config.BIRD_TEMPLATE_SCALE
        )
        self._bird_tmpl = self._bird_tmpls[0]  # kept for shape reference
        tw, th = config.PIPE_TOP_SIZE
        bw, bh = config.PIPE_BOTTOM_SIZE
        self._top_tmpl = cv2.resize(
            self._load_template(config.PIPE_TOP_TEMPLATE, vcrop=config.PIPE_TOP_TRUNK_CROP),
            (tw, th),
        )
        self._bottom_tmpl = cv2.resize(
            self._load_template(config.PIPE_BOTTOM_TEMPLATE, vcrop=config.PIPE_BOTTOM_TRUNK_CROP),
            (bw, bh),
        )

        self._bird_h,   self._bird_w   = self._bird_tmpl.shape[:2]
        self._top_h,    self._top_w    = self._top_tmpl.shape[:2]
        self._bottom_h, self._bottom_w = self._bottom_tmpl.shape[:2]

        self._pipe_tracks: list = []
        self._last_pipe_time: float = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_bird_frames(path: str, sprite_frames: int, scale: float):
        """Return (frames, masks) — one BGR array and one uint8 mask per animation frame.

        Paletted PNGs render their transparent background as black when loaded
        by OpenCV.  We detect those pixels and mask them out so template
        matching ignores them.
        """
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Template not found: {path}")

        # Build a per-pixel alpha mask.
        if img.ndim == 3 and img.shape[2] == 4:
            # True RGBA — use the alpha channel directly.
            alpha = img[:, :, 3]
            img   = img[:, :, :3]
        else:
            # BGR or indexed (palette already expanded to BGR by OpenCV).
            # Background pixels are pure black; bird pixels are not.
            img = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            alpha = (img.max(axis=2) > 15).astype(np.uint8) * 255

        frame_w = img.shape[1] // sprite_frames
        frames, masks = [], []
        for i in range(sprite_frames):
            f = img[:,   i * frame_w:(i + 1) * frame_w]
            m = alpha[:, i * frame_w:(i + 1) * frame_w]
            if scale != 1.0:
                h, w    = f.shape[:2]
                new_sz  = (max(1, int(w * scale)), max(1, int(h * scale)))
                f = cv2.resize(f, new_sz, interpolation=cv2.INTER_NEAREST)
                m = cv2.resize(m, new_sz, interpolation=cv2.INTER_NEAREST)
            frames.append(f)
            masks.append(m)
        return frames, masks

    @staticmethod
    def _load_template(
        path: str,
        sprite_frames: int = 1,
        vcrop: tuple = (0.0, 1.0),
    ) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Template not found: {path}")
        if sprite_frames > 1:
            frame_w = img.shape[1] // sprite_frames
            img = img[:, :frame_w]
        if vcrop != (0.0, 1.0):
            h = img.shape[0]
            y0 = int(h * vcrop[0])
            y1 = int(h * vcrop[1])
            img = img[y0:y1]
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
        """Greedy non-maximum suppression in 2D."""
        if not hits:
            return []
        hits = sorted(hits, key=lambda h: -h[2])
        kept = []
        for h in hits:
            if all((h[0]-k[0])**2 + (h[1]-k[1])**2 >= min_dist**2 for k in kept):
                kept.append(h)
        return kept

    def _update_tracks(self, detections: list, now: float) -> None:
        MATCH_TOL = config.PIPE_TOP_SIZE[0]  # 115 px — 1 pipe-width tolerance

        # 1. Dead-reckon: advance every track's x left by elapsed distance.
        dt = (now - self._last_pipe_time) if self._last_pipe_time > 0 else 0.0
        for t in self._pipe_tracks:
            t["x"] -= int(dt * config.PIPE_SPEED_PX_PER_SEC)

        # 2. Match each detection to its nearest track.
        unmatched = list(range(len(detections)))
        for t in self._pipe_tracks:
            best_dist, best_di = MATCH_TOL + 1, -1
            for di in unmatched:
                dist = abs(detections[di]["x"] - t["x"])
                if dist < best_dist:
                    best_dist, best_di = dist, di
            if best_di != -1:
                d = detections[best_di]
                t["x"]         = d["x"]
                t["gap_y"]     = d["gap_y"]
                t["top_y"]     = d["top_rect"][1]
                t["bot_y"]     = d["bot_rect"][1]
                t["last_seen"] = now
                unmatched.remove(best_di)

        # 3. Spawn new tracks for unmatched detections.
        for di in unmatched:
            d = detections[di]
            self._pipe_tracks.append({
                "x": d["x"], "gap_y": d["gap_y"],
                "top_y": d["top_rect"][1], "bot_y": d["bot_rect"][1],
                "last_seen": now,
            })

        # 4. Expire stale tracks.
        self._pipe_tracks = [
            t for t in self._pipe_tracks
            if (now - t["last_seen"]) <= config.PIPE_TRACK_MAX_AGE
        ]

        self._last_pipe_time = now

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

        Returns (cx, cy) — the EMA-smoothed centre of the best match — or
        None if the confidence is below BIRD_THRESHOLD.
        """
        if config.DEBUG and not hasattr(self, '_frame_size_logged'):
            print(f"[DEBUG] frame shape={frame.shape}  bird template shape={self._bird_tmpl.shape}")
            self._frame_size_logged = True

        gray = self._to_gray(frame)

        # Restrict search to the column where the bird lives.
        # The bird's x position is fixed; pipes scroll in from the right.
        search_h  = int(gray.shape[0] * config.BIRD_SEARCH_VMAX)
        search_x0 = int(gray.shape[1] * config.BIRD_SEARCH_XMIN)
        search_x1 = int(gray.shape[1] * config.BIRD_SEARCH_XMAX)
        search_gray = gray[:search_h, search_x0:search_x1]

        if config.DEBUG and not hasattr(self, '_diag_saved'):
            cv2.imwrite('debug_template.png', self._bird_tmpls[0])
            cv2.imwrite('debug_template_gray.png', self._to_gray(self._bird_tmpls[0]))
            cv2.imwrite('debug_search_region.png', search_gray)
            print("[DEBUG] saved debug_template.png, debug_template_gray.png, debug_search_region.png")
            self._diag_saved = True

        best_val, best_loc = -1.0, None
        for tmpl, mask in zip(self._bird_tmpls, self._bird_masks):
            tg = self._to_gray(tmpl)
            if tg.shape[0] > search_gray.shape[0] or tg.shape[1] > search_gray.shape[1]:
                continue
            result = cv2.matchTemplate(search_gray, tg, cv2.TM_CCORR_NORMED, mask=mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val, best_loc = max_val, max_loc

        max_val, max_loc = best_val, best_loc

        if config.DEBUG and not hasattr(self, '_score_print_next'):
            self._score_print_next = 0.0
        if config.DEBUG:
            now = time.monotonic()
            if now >= self._score_print_next:
                print(f"bird match score: {max_val:.3f} (threshold={config.BIRD_THRESHOLD})")
                self._score_print_next = now + 1.0

        if max_val < config.BIRD_THRESHOLD:
            return self._bird_smooth

        x, y = max_loc
        cx = search_x0 + x + self._bird_w // 2
        cy = y + self._bird_h // 2

        # Colour guard: the bird is cream/tan; pipes are green.
        # Sample the matched region in BGR and reject if green-dominant.
        half = self._bird_w // 2
        rx0, rx1 = max(0, cx - half), min(frame.shape[1], cx + half)
        ry0, ry1 = max(0, cy - half), min(frame.shape[0], cy + half)
        region = frame[ry0:ry1, rx0:rx1].astype(float)
        if region.size > 0:
            mean_b, mean_g, mean_r = region[:,:,0].mean(), region[:,:,1].mean(), region[:,:,2].mean()
            if config.DEBUG:
                now = time.monotonic()
                if now >= getattr(self, '_color_print_next', 0.0):
                    print(f"  colour check BGR=({mean_b:.0f},{mean_g:.0f},{mean_r:.0f})")
                    self._color_print_next = now + 1.0
            if mean_g > mean_r + 25:
                # Green-dominant → pipe, not bird; hold last known position.
                return self._bird_smooth

        # EMA smoothing: α=0.4 keeps the marker stable while still tracking quickly.
        alpha = 0.4
        if self._bird_smooth is None:
            self._bird_smooth = (cx, cy)
        else:
            sx, sy = self._bird_smooth
            self._bird_smooth = (
                int(alpha * cx + (1 - alpha) * sx),
                int(alpha * cy + (1 - alpha) * sy),
            )

        return self._bird_smooth

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

        # Restrict search to the right of the bird so pipe detection and bird
        # detection operate on non-overlapping regions.
        fh, fw = gray.shape[:2]
        pipe_x0 = int(fw * config.PIPE_DETECT_XMIN)
        search_gray = gray[:, pipe_x0:]

        # Find all candidate matches for each pipe type.
        top_raw    = self._match(search_gray, top_gray,    config.PIPE_THRESHOLD)
        bottom_raw = self._match(search_gray, bottom_gray, config.PIPE_THRESHOLD)

        if config.DEBUG:
            now = time.monotonic()
            if now >= getattr(self, '_pipe_print_next', 0.0):
                fh, fw = gray.shape[:2]
                th, tw = top_gray.shape[:2]
                bh, bw = bottom_gray.shape[:2]
                r_top = cv2.matchTemplate(gray, top_gray, cv2.TM_CCOEFF_NORMED)
                r_bot = cv2.matchTemplate(gray, bottom_gray, cv2.TM_CCOEFF_NORMED)
                _, top_best, _, top_loc = cv2.minMaxLoc(r_top)
                _, bot_best, _, bot_loc = cv2.minMaxLoc(r_bot)
                print(
                    f"pipe scores: top_best={top_best:.3f}@{top_loc}  bot_best={bot_best:.3f}@{bot_loc}"
                    f"  (threshold={config.PIPE_THRESHOLD})"
                    f"  top_tmpl={tw}x{th}  bot_tmpl={bw}x{bh}"
                    f"  frame={fw}x{fh}"
                )
                print(f"  top_hits={len(top_raw)}  bottom_hits={len(bottom_raw)}")
                self._pipe_print_next = now + 1.0

            if not getattr(self, '_pipe_diag_saved', False):
                r_top = cv2.matchTemplate(gray, top_gray, cv2.TM_CCOEFF_NORMED)
                r_bot = cv2.matchTemplate(gray, bottom_gray, cv2.TM_CCOEFF_NORMED)
                # Normalise heat maps to 0-255 for saving
                def _norm(m):
                    mn, mx = m.min(), m.max()
                    return ((m - mn) / max(mx - mn, 1e-6) * 255).astype(np.uint8)
                cv2.imwrite('debug_pipe_frame.png',   frame)
                cv2.imwrite('debug_pipe_top_tmpl.png',    self._top_tmpl)
                cv2.imwrite('debug_pipe_bot_tmpl.png',    self._bottom_tmpl)
                cv2.imwrite('debug_pipe_top_heat.png',    cv2.applyColorMap(_norm(r_top), cv2.COLORMAP_JET))
                cv2.imwrite('debug_pipe_bot_heat.png',    cv2.applyColorMap(_norm(r_bot), cv2.COLORMAP_JET))
                print("[DEBUG] saved debug_pipe_*.png")
                self._pipe_diag_saved = True

        top_hits    = self._suppress(top_raw,    config.PIPE_SUPPRESS_DIST)
        bottom_hits = self._suppress(bottom_raw, config.PIPE_SUPPRESS_DIST)

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

            # Translate search_gray-relative coords back to full-frame.
            fx_t = tx + pipe_x0
            fx_b = bx + pipe_x0

            # Gap boundaries: bottom edge of top pipe ↔ top edge of bottom pipe.
            top_bottom_edge = ty + self._top_h
            bottom_top_edge = by
            gap_y = (top_bottom_edge + bottom_top_edge) // 2

            col_x = (fx_t + self._top_w // 2 + fx_b + self._bottom_w // 2) // 2

            pairs.append({
                "x":        col_x,
                "gap_y":    gap_y,
                "top_rect": (fx_t, ty, self._top_w, self._top_h),
                "bot_rect": (fx_b, by, self._bottom_w, self._bottom_h),
            })

        self._update_tracks(pairs, time.monotonic())
        return pairs

    def blot_pipes(self, frame: np.ndarray) -> np.ndarray:
        """
        Return a copy of *frame* with all tracked pipe areas painted sky-blue so
        that bird detection cannot lock on to them.
        """
        MARGIN = 10
        out   = frame.copy()
        fh, fw = out.shape[:2]
        color = config.PIPE_BLOT_COLOR
        half  = self._top_w // 2  # both pipes are 115 px wide

        for t in self._pipe_tracks:
            x  = t["x"]
            x0 = max(0, x - half - MARGIN)
            x1 = min(fw, x + half + MARGIN)
            if x1 <= x0:
                continue
            # Top pipe: ceiling down to bottom edge of template.
            out[0 : min(fh, t["top_y"] + self._top_h), x0:x1] = color
            # Bottom pipe: top edge of template down to floor.
            out[max(0, t["bot_y"]) : fh, x0:x1] = color

        return out

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

        # Tracked pipe predicted positions (magenta) — shows dead-reckoned state.
        half_tw = self._top_w // 2
        for t in self._pipe_tracks:
            x = t["x"]
            cv2.rectangle(out, (x - half_tw, t["top_y"]),
                          (x + half_tw, t["top_y"] + self._top_h), (255, 0, 255), 1)
            cv2.rectangle(out, (x - half_tw, t["bot_y"]),
                          (x + half_tw, t["bot_y"] + self._bottom_h), (255, 0, 255), 1)

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
