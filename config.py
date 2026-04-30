# ---------------------------------------------------------------------------
# config.py — all user-tunable constants for the Flappy Bird auto-player
# ---------------------------------------------------------------------------

# Absolute screen coordinates of the game window capture region.
# Derived from Data.txt: LeftCorner (772, 125), RightCorner (1451, 624).
REGION = {"left": 772, "top": 125, "width": 679, "height": 499}

# Paths to template images (relative to the working directory).
BIRD_TEMPLATE         = "bird.png"
PIPE_TOP_TEMPLATE     = "tree_top.png"     # top pipe hangs from ceiling — crown at bottom of sprite faces the gap
PIPE_BOTTOM_TEMPLATE  = "tree_bottom.png"  # bottom pipe grows from floor — crown at top of sprite faces the gap

# Number of animation frames in bird.png (laid out horizontally).
# The first frame is extracted and used as the match template.
BIRD_SPRITE_FRAMES = 4

# Template-matching confidence thresholds (0.0–1.0).
# Lower = more detections but more false positives; raise if you see ghost detections.
BIRD_THRESHOLD = 0.9   # TM_CCORR_NORMED with mask — good matches score 0.85+
PIPE_THRESHOLD = 0.55

# Fraction of frame height/width to search when locating the bird.
# The bird is always in the left ~40 % of the screen and above the HUD strip.
BIRD_SEARCH_VMAX = 0.82
BIRD_SEARCH_XMIN = 0.30   # left boundary of bird search column (~204 px)
BIRD_SEARCH_XMAX = 0.40   # right boundary (~272 px) — ~68 px strip around the bird

PIPE_SUPPRESS_DIST = 40

# Maximum x-distance (px) between a top-pipe and bottom-pipe match for them to be
# paired as the same pipe column.
PIPE_PAIR_TOLERANCE = 50

# Bird sprite sheet: 64x64 px per frame.
BIRD_TEMPLATE_SCALE  = 0.5   # 64px -> 32px; matches on-screen bird size in 679x499 frame

# Exact on-screen pixel size (width, height) for each pipe in the capture frame.
# From game source: TreeBottom is 175px tall, TreeTop is 210px tall, both 115px wide.
PIPE_TOP_SIZE    = (115, 175)  # top pipe hangs from ceiling — root cluster is gap-facing end
PIPE_BOTTOM_SIZE = (115, 210)  # bottom pipe grows from floor — crown is gap-facing end

# Crop the sprite to the gap-facing end before resizing so the template is always fully
# visible in the frame (the other end goes off-screen).
# tree_bottom.png is 384px tall; bottom 175px = fraction (1 - 175/384) = 0.544
# tree_top.png is 384px tall;   top 210px    = fraction 210/384 = 0.547
PIPE_TOP_TRUNK_CROP    = (0.544, 1.0)   # bottom 175px of tree_bottom.png (root cluster)
PIPE_BOTTOM_TRUNK_CROP = (0.0,  0.547)  # top 210px of tree_top.png (crown)

# Minimum time (seconds) between consecutive Space-bar presses.
JUMP_COOLDOWN = 0.25

# Target game-loop rate in frames per second.
TARGET_FPS = 60

# Set to True to show a live OpenCV debug window with detection overlays.
DEBUG = True

# Pipe physics: 0.008 UDim2 scale/tick × 679 px × 60 fps
PIPE_SPEED_PX_PER_SEC = 326.0
# Only scan for pipes to the right of this x fraction (bird is at ~33%).
PIPE_DETECT_XMIN      = 0.42
# Sky-blue fill colour (BGR) — game background Color3.fromRGB(68, 149, 245).
PIPE_BLOT_COLOR       = (245, 149, 68)
# Drop a tracked pipe if not re-detected within this many seconds.
PIPE_TRACK_MAX_AGE    = 0.5
