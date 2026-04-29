# ---------------------------------------------------------------------------
# config.py — all user-tunable constants for the Flappy Bird auto-player
# ---------------------------------------------------------------------------

# Absolute screen coordinates of the game window capture region.
# Derived from Data.txt: LeftCorner (772, 125), RightCorner (1451, 624).
REGION = {"left": 772, "top": 125, "width": 679, "height": 499}

# Paths to template images (relative to the working directory).
BIRD_TEMPLATE         = "bird.png"
PIPE_TOP_TEMPLATE     = "tree_top.png"
PIPE_BOTTOM_TEMPLATE  = "tree_bottom.png"

# Number of animation frames in bird.png (laid out horizontally).
# The first frame is extracted and used as the match template.
BIRD_SPRITE_FRAMES = 4

# Template-matching confidence thresholds (0.0–1.0).
# Lower = more detections but more false positives; raise if you see ghost detections.
BIRD_THRESHOLD = 0.60
PIPE_THRESHOLD = 0.45

# Minimum pixel distance on the x-axis between two pipe detections of the same type.
# Prevents the same physical pipe column from being counted twice.
PIPE_SUPPRESS_DIST = 40

# Maximum x-distance (px) between a top-pipe and bottom-pipe match for them to be
# paired as the same pipe column.
PIPE_PAIR_TOLERANCE = 50

# Scale factors applied to templates at load time.
# Ideal value = (sprite pixels on screen) / (template image pixels).
# Bird sprite sheet: 64x64 px per frame.
BIRD_TEMPLATE_SCALE  = 0.5   # 64px -> ~32px; tune to match on-screen bird size
# Tree/pipe templates: 128x384 px sprites.
PIPE_TEMPLATE_SCALE  = 0.5   # 128x384 -> 64x192px; tune to match on-screen pipe size

# Vertical crop of the tree sprites used for matching (fractions of image height).
# The crown (top tree) and roots (bottom tree) may be clipped off-screen during
# play, so we match only the trunk section which is always fully visible.
# (0.0, 1.0) = full image; (0.3, 0.8) = middle 50%, etc.
PIPE_TOP_TRUNK_CROP    = (0.25, 0.85)  # skip palm crown at top
PIPE_BOTTOM_TRUNK_CROP = (0.10, 0.75)  # skip root cluster at bottom

# Minimum time (seconds) between consecutive Space-bar presses.
JUMP_COOLDOWN = 0.25

# Target game-loop rate in frames per second.
TARGET_FPS = 60

# Set to True to show a live OpenCV debug window with detection overlays.
DEBUG = True
