import random
import time

import pygame

import config

WIDTH  = config.REGION["width"]   # 679
HEIGHT = config.REGION["height"]  # 499

# Physics from src_bird.txt
GRAVITY    = -0.6867              # velocity delta per frame
JUMP_VEL   = 9.0                  # velocity set on jump
PIPE_SPEED = 0.008 * WIDTH        # px per frame (~5.43 px @ 679 wide)
SPAWN_SECS = 1.5                  # seconds between pipe spawns

BIRD_X       = int(WIDTH * 0.333)
PIPE_W       = config.PIPE_TOP_SIZE[0]   # 115 px
GAP_H        = 160                       # pixels of open space between pipes
FLAP_SECS    = 0.15                      # animation frame interval (from src_bird.txt)

SKY   = (68, 149, 245)
RED   = (220, 40, 40)
BLACK = (0, 0, 0)


def load_assets():
    # Bird: 4 × 64×64 frames in a horizontal sprite sheet, scaled 0.5 → 32×32
    sheet = pygame.image.load(config.BIRD_TEMPLATE).convert_alpha()
    fw = sheet.get_width() // config.BIRD_SPRITE_FRAMES
    fh = sheet.get_height()
    s  = config.BIRD_TEMPLATE_SCALE
    bird_frames = [
        pygame.transform.scale(
            sheet.subsurface((i * fw, 0, fw, fh)),
            (int(fw * s), int(fh * s)),
        )
        for i in range(config.BIRD_SPRITE_FRAMES)
    ]

    # Pipes pre-scaled to (PIPE_W, HEIGHT).
    # Top pipe blit at (x, gap_top - HEIGHT) → bottom of image sits at gap_top.
    # Bottom pipe blit at (x, gap_bottom)    → top of image sits at gap_bottom.
    pipe_top = pygame.transform.scale(
        pygame.image.load(config.PIPE_TOP_TEMPLATE).convert_alpha(),
        (PIPE_W, HEIGHT),
    )
    pipe_bot = pygame.transform.scale(
        pygame.image.load(config.PIPE_BOTTOM_TEMPLATE).convert_alpha(),
        (PIPE_W, HEIGHT),
    )

    return bird_frames, pipe_top, pipe_bot


class Bird:
    def __init__(self):
        self.x          = BIRD_X
        self.y          = float(HEIGHT // 2)
        self.vel        = 0.0
        self._last_jump = -999.0
        self.frame      = 0
        self._last_flap = 0.0

    def jump(self):
        now = time.perf_counter()
        if now - self._last_jump >= config.JUMP_COOLDOWN:
            self.vel        = JUMP_VEL
            self._last_jump = now

    def step(self):
        self.vel += GRAVITY
        self.y   -= self.vel
        self.y    = max(0.0, min(float(HEIGHT - 1), self.y))
        now = time.perf_counter()
        if now - self._last_flap >= FLAP_SECS:
            self.frame      = (self.frame + 1) % config.BIRD_SPRITE_FRAMES
            self._last_flap = now


class Pipe:
    def __init__(self, x, gap_y):
        self.x       = float(x)
        self.gap_y   = gap_y
        self._scored = False

    def step(self):
        self.x -= PIPE_SPEED

    def offscreen(self):
        return self.x + PIPE_W < 0


def next_pipe(pipes, bird_x):
    ahead = [p for p in pipes if p.x + PIPE_W > bird_x]
    return min(ahead, key=lambda p: p.x) if ahead else None


def collides(bird, pipe):
    bx, by = bird.x, bird.y
    if bx + 15 < pipe.x or bx - 15 > pipe.x + PIPE_W:
        return False
    gap_top    = pipe.gap_y - GAP_H // 2
    gap_bottom = pipe.gap_y + GAP_H // 2
    return by < gap_top or by > gap_bottom


def spawn_pipe():
    gap_y = random.randint(int(HEIGHT * 0.25), int(HEIGHT * 0.75))
    return Pipe(WIDTH, gap_y)


def draw(screen, font, big_font, bird_frames, pipe_top, pipe_bot, bird, pipes, score, alive):
    screen.fill(SKY)

    for p in pipes:
        ix        = int(p.x)
        gap_top   = p.gap_y - GAP_H // 2
        gap_bottom = p.gap_y + GAP_H // 2
        screen.blit(pipe_top, (ix, gap_top - HEIGHT))
        screen.blit(pipe_bot, (ix, gap_bottom))
        pygame.draw.line(screen, RED, (ix, p.gap_y), (ix + PIPE_W, p.gap_y), 2)

    bx, by = bird.x, int(bird.y)
    img = bird_frames[bird.frame]
    screen.blit(img, (bx - img.get_width() // 2, by - img.get_height() // 2))

    screen.blit(font.render(f"Score: {score}", True, BLACK), (10, 10))

    if not alive:
        msg = big_font.render("DEAD  —  R to restart", True, RED)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - msg.get_height() // 2))

    pygame.display.flip()


def reset():
    bird       = Bird()
    pipes      = [spawn_pipe()]
    score      = 0
    last_spawn = time.perf_counter()
    return bird, pipes, score, last_spawn


def main():
    pygame.init()
    screen   = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Flappy Bird Simulation")
    clock    = pygame.time.Clock()
    font     = pygame.font.SysFont(None, 32)
    big_font = pygame.font.SysFont(None, 56)

    bird_frames, pipe_top, pipe_bot = load_assets()
    bird, pipes, score, last_spawn  = reset()
    alive = True

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    bird, pipes, score, last_spawn = reset()
                    alive = True

        if alive:
            now = time.perf_counter()

            if now - last_spawn >= SPAWN_SECS:
                pipes.append(spawn_pipe())
                last_spawn = now

            for p in pipes:
                p.step()

            # Bot decision — same rule as main.py
            np = next_pipe(pipes, bird.x)
            if np is not None and bird.y > np.gap_y:
                bird.jump()

            bird.step()

            for p in pipes:
                if not p._scored and p.x + PIPE_W < bird.x:
                    p._scored = True
                    score += 1

            for p in pipes:
                if collides(bird, p):
                    alive = False

            if bird.y <= 1 or bird.y >= HEIGHT - 2:
                alive = False

            pipes = [p for p in pipes if not p.offscreen()]

        draw(screen, font, big_font, bird_frames, pipe_top, pipe_bot, bird, pipes, score, alive)
        clock.tick(config.TARGET_FPS)


if __name__ == "__main__":
    main()
