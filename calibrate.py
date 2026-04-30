"""
One-shot calibration: captures frames until trees are visible, then measures
their on-screen pixel dimensions using HSV color detection. Run while the game
is running and a pipe pair is visible on screen.

Usage:
    python calibrate.py
"""

import time
import cv2
import numpy as np
import mss
import config


def _grab():
    with mss.mss() as sct:
        raw = sct.grab(config.REGION)
    return np.array(raw)[:, :, :3]


def _find_trunk_bbox(frame_bgr):
    """Return list of (x, y, w, h) bounding boxes for brown trunk columns."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    # Brown trunk: hue ~10-25 (orange-brown), moderate sat and val
    mask = cv2.inRange(hsv, (8, 60, 60), (25, 200, 200))
    # Dilate slightly to bridge gaps
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 200:  # ignore tiny noise
            continue
        # Trunk columns are taller than wide and at least 30px wide
        if h > w * 1.5 and w >= 15:
            boxes.append((x, y, w, h))
    return boxes


def _find_crown_bbox(frame_bgr, trunk_box):
    """Return (x, y, w, h) bounding box of the crown near a trunk."""
    tx, ty, tw, th = trunk_box
    # Crown: green/yellow-green leaves around the trunk ends
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask_green = cv2.inRange(hsv, (35, 50, 80), (90, 255, 255))
    # Cream/tan coconut faces
    mask_tan   = cv2.inRange(hsv, (15, 20, 150), (40, 120, 255))
    mask = cv2.bitwise_or(mask_green, mask_tan)
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)

    # Only look in a strip around the top or bottom of the trunk.
    h, w = frame_bgr.shape[:2]
    cx = tx + tw // 2
    search_w = tw * 3

    # Top end of trunk
    top_strip = np.zeros_like(mask)
    strip_y0 = max(0, ty - tw)
    strip_y1 = min(h, ty + tw * 2)
    top_strip[strip_y0:strip_y1, max(0, cx - search_w):min(w, cx + search_w)] = \
        mask[strip_y0:strip_y1, max(0, cx - search_w):min(w, cx + search_w)]

    # Bottom end of trunk
    bot_strip = np.zeros_like(mask)
    strip_y0 = max(0, ty + th - tw * 2)
    strip_y1 = min(h, ty + th + tw)
    bot_strip[strip_y0:strip_y1, max(0, cx - search_w):min(w, cx + search_w)] = \
        mask[strip_y0:strip_y1, max(0, cx - search_w):min(w, cx + search_w)]

    results = {}
    for label, strip in [('top_end', top_strip), ('bot_end', bot_strip)]:
        ys, xs = np.where(strip > 0)
        if len(xs) < 50:
            continue
        results[label] = (xs.min(), ys.min(), xs.max() - xs.min(), ys.max() - ys.min())
    return results


def main():
    print("Capturing frames… move a pipe into view if needed.")
    print("Press Ctrl-C to stop.\n")

    found_any = False
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        frame = _grab()
        boxes = _find_trunk_bbox(frame)
        if not boxes:
            time.sleep(0.1)
            continue

        found_any = True
        vis = frame.copy()
        print(f"Found {len(boxes)} trunk(s):")
        for i, b in enumerate(boxes):
            x, y, w, h = b
            print(f"  trunk {i}: x={x} y={y} w={w} h={h}  (frame {frame.shape[1]}x{frame.shape[0]})")
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 140, 255), 2)
            crowns = _find_crown_bbox(frame, b)
            for end, cb in crowns.items():
                cx2, cy2, cw, ch = cb
                print(f"    crown at {end}: x={cx2} y={cy2} w={cw} h={ch}")
                cv2.rectangle(vis, (cx2, cy2), (cx2 + cw, cy2 + ch), (0, 255, 0), 2)

        cv2.imwrite("debug_calibrate.png", vis)
        print("\nSaved debug_calibrate.png")

        # Suggest config values
        if boxes:
            widths = [b[2] for b in boxes]
            avg_w = int(np.median(widths))
            # Crown height is roughly 60% of trunk width based on the sprites
            est_crown_h = int(avg_w * 2.5)
            print(f"\nSuggested config values (based on measured trunk width={avg_w}px):")
            print(f"  PIPE_TOP_SIZE    = ({avg_w}, {est_crown_h})")
            print(f"  PIPE_BOTTOM_SIZE = ({avg_w}, {est_crown_h})")

        time.sleep(0.5)

    if not found_any:
        print("No trunks found after 20s. Make sure a pipe is visible in the capture region.")


if __name__ == "__main__":
    main()
