# ---------------------------------------------------------------------------
# main.py — entry point; starts the Flappy Bird auto-player game loop
# ---------------------------------------------------------------------------

import time
import sys

import cv2

import config
from detector import Detector
from controller import Controller


def main():
    detector   = Detector()
    controller = Controller()

    frame_duration = 1.0 / config.TARGET_FPS

    print("Auto-player running. Press Ctrl-C to stop.")
    _WIN = "Flappy Bird Auto-Player (DEBUG)"
    if config.DEBUG:
        print("DEBUG mode on — press 'q' in the OpenCV window to quit.")
        cv2.namedWindow(_WIN, cv2.WINDOW_NORMAL)
        # Keep the debug window outside the capture region so it doesn't
        # feed back into its own frames (infinite mirror effect).
        r = config.REGION
        cv2.resizeWindow(_WIN, r["width"], r["height"])
        cv2.moveWindow(_WIN, r["left"], r["top"] + r["height"] + 10)

    try:
        while True:
            t_start = time.perf_counter()

            # --- Capture ---
            frame = detector.capture()

            # --- Detect ---
            bird_pos = detector.find_bird(frame)
            pipes    = detector.find_pipes(frame)
            next_p   = detector.next_pipe(pipes, bird_pos[0]) if bird_pos else None

            # --- Decide ---
            if bird_pos is not None and next_p is not None:
                bird_y  = bird_pos[1]
                gap_y   = next_p["gap_y"]
                if bird_y > gap_y:
                    controller.jump()

            # --- Debug window ---
            if config.DEBUG:
                debug_frame = detector.draw_debug(frame, bird_pos, pipes, next_p)
                small = cv2.resize(debug_frame, (r["width"], r["height"]))
                cv2.imshow(_WIN, small)
                # 'q' quits; waitKey(1) keeps the loop non-blocking.
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            # --- Frame-rate cap ---
            elapsed = time.perf_counter() - t_start
            sleep_for = frame_duration - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        if config.DEBUG:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
