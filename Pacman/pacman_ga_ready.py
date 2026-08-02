# Pacman - GA-Ready Version
# Changes from original:
#   1. Blinky movement is no longer hardcoded — uses free-roaming AI with random direction changes
#   2. Walls are no longer hardcoded — generated from a parameterized layout (seed-able for GA)
#   3. Speed is randomized per game instance (pacman_speed, ghost_speed drawn from ranges)
#   4. Ghost base class exposes a `set_genome_speed(dx, dy)` for future GA control of Blinky

import pygame
import random

# ── Colours ──────────────────────────────────────────────────────────────────
black  = (  0,   0,   0)
white  = (255, 255, 255)
blue   = (  0,   0, 255)
green  = (  0, 255,   0)
red    = (255,   0,   0)
purple = (255,   0, 255)
yellow = (255, 255,   0)

# ── Speed configuration (randomised each game) ───────────────────────────────
SPEED_OPTIONS = [15, 20, 25, 30]          # pixel increments per tick

def random_speed():
    """Pick a random step size from the allowed set."""
    return random.choice(SPEED_OPTIONS)

# ── Wall sprite ───────────────────────────────────────────────────────────────
class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color=blue):
        super().__init__()
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.rect.top  = y
        self.rect.left = x

# ── Maze generation ───────────────────────────────────────────────────────────
# Wall layout is expressed as a list of (x, y, w, h) tuples.
# `generate_wall_layout` accepts a seed so the GA can reproduce any maze.
# The border is always fixed; interior walls are drawn from a seeded template
# that can later be parameterised by the GA genome.

BORDER_WALLS = [
    (0,   0,   6,   600),   # left
    (0,   0,   600, 6  ),   # top
    (0,   600, 606, 6  ),   # bottom
    (600, 0,   6,   606),   # right
]

# Interior walls expressed as named segments — each can be toggled by the GA
INTERIOR_SEGMENTS = {
    "top_center_divider":    (300, 0,   6,  66),
    "top_left_shelf":        (60,  60,  186, 6),
    "top_right_shelf":       (360, 60,  186, 6),
    "left_upper_corner_h":   (60,  120, 66,  6),
    "left_upper_corner_v":   (60,  120, 6,   126),
    "center_top_h":          (180, 120, 246, 6),
    "center_top_divider_v":  (300, 120, 6,  66),
    "right_upper_corner_h":  (480, 120, 66,  6),
    "right_upper_corner_v":  (540, 120, 6,   126),
    "left_mid_upper_h":      (120, 180, 126, 6),
    "left_mid_upper_v":      (120, 180, 6,   126),
    "right_mid_upper_h":     (360, 180, 126, 6),
    "right_mid_upper_v":     (480, 180, 6,   126),
    "left_inner_v":          (180, 240, 6,   126),
    "mid_bottom_h":          (180, 360, 246, 6),
    "right_inner_v":         (420, 240, 6,   126),
    "center_left_h":         (240, 240, 42,  6),
    "center_right_h":        (324, 240, 42,  6),
    "center_left_v":         (240, 240, 6,   66),
    "center_mid_h":          (240, 300, 126, 6),
    "center_right_v":        (360, 240, 6,   66),
    "left_side_h":           (0,   300, 66,  6),
    "right_side_h":          (540, 300, 66,  6),
    "lower_left_h":          (60,  360, 66,  6),
    "lower_left_v":          (60,  360, 6,   186),
    "lower_right_h":         (480, 360, 66,  6),
    "lower_right_v":         (540, 360, 6,   186),
    "lower_inner_h":         (120, 420, 366, 6),
    "lower_inner_left_v":    (120, 420, 6,   66),
    "lower_inner_right_v":   (480, 420, 6,   66),
    "bottom_inner_h":        (180, 480, 246, 6),
    "bottom_center_v":       (300, 480, 6,   66),
    "bottom_left_h":         (120, 540, 126, 6),
    "bottom_right_h":        (360, 540, 126, 6),
}

def generate_wall_layout(seed=None, drop_probability=0.0):
    """
    Return a list of (x, y, w, h) wall tuples.

    seed            – random seed for reproducibility (GA can pass genome index)
    drop_probability– probability [0,1] of omitting any interior segment (0 = classic maze)
    """
    rng = random.Random(seed)
    walls = list(BORDER_WALLS)
    for seg in INTERIOR_SEGMENTS.values():
        if rng.random() >= drop_probability:
            walls.append(seg)
    return walls


def setup_walls(all_sprites_list, seed=None, drop_probability=0.0):
    wall_list = pygame.sprite.RenderPlain()
    for (x, y, w, h) in generate_wall_layout(seed, drop_probability):
        wall = Wall(x, y, w, h)
        wall_list.add(wall)
        all_sprites_list.add(wall)
    return wall_list


def setup_gate(all_sprites_list):
    gate = pygame.sprite.RenderPlain()
    gate.add(Wall(282, 242, 42, 2, white))
    all_sprites_list.add(gate)
    return gate


# ── Pellet ────────────────────────────────────────────────────────────────────
class Block(pygame.sprite.Sprite):
    def __init__(self, color, width, height):
        super().__init__()
        self.image = pygame.Surface([width, height])
        self.image.fill(white)
        self.image.set_colorkey(white)
        pygame.draw.ellipse(self.image, color, [0, 0, width, height])
        self.rect = self.image.get_rect()


# ── Player (Pacman) ───────────────────────────────────────────────────────────
class Player(pygame.sprite.Sprite):
    change_x = 0
    change_y = 0

    def __init__(self, x, y, filename):
        super().__init__()
        self.image = pygame.image.load(filename).convert()
        self.rect  = self.image.get_rect()
        self.rect.top  = y
        self.rect.left = x
        self.prev_x = x
        self.prev_y = y

    def prevdirection(self):
        self.prev_x = self.change_x
        self.prev_y = self.change_y

    def changespeed(self, x, y):
        self.change_x += x
        self.change_y += y

    def update(self, walls, gate):
        old_x = self.rect.left
        self.rect.left = old_x + self.change_x
        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.left = old_x
        else:
            old_y = self.rect.top
            self.rect.top = old_y + self.change_y
            if pygame.sprite.spritecollide(self, walls, False):
                self.rect.top = old_y

        if gate:
            if pygame.sprite.spritecollide(self, gate, False):
                self.rect.left = old_x
                self.rect.top  = old_y


# ── Ghost base (scripted path — retained for compatibility) ────────────────
class Ghost(Player):
    """Scripted ghost: follows a predefined direction list."""

    def changespeed(self, direction_list, ghost_tag, turn, steps, max_turn):
        try:
            z = direction_list[turn][2]
            if steps < z:
                self.change_x = direction_list[turn][0]
                self.change_y = direction_list[turn][1]
                steps += 1
            else:
                if turn < max_turn:
                    turn += 1
                elif ghost_tag == "clyde":
                    turn = 2
                else:
                    turn = 0
                self.change_x = direction_list[turn][0]
                self.change_y = direction_list[turn][1]
                steps = 0
            return [turn, steps]
        except IndexError:
            return [0, 0]


class RandomGhostAI(Player):
    """Ghost that leaves the middle square, then roams randomly."""

    DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    HOUSE_EXIT_X = 287
    HOUSE_EXIT_Y = 210

    def __init__(self, x, y, filename, speed, rng_seed=None):
        super().__init__(x, y, filename)
        self.speed = speed
        self._rng = random.Random(rng_seed)
        self.direction_ttl = 0
        self.has_left_house = False
        self._pick_random_direction()

    def _pick_random_direction(self):
        dx, dy = self._rng.choice(self.DIRECTIONS)
        self.change_x = dx * self.speed
        self.change_y = dy * self.speed
        self.direction_ttl = self._rng.randint(5, 20)

    def _can_move(self, walls, dx, dy):
        old_x, old_y = self.rect.left, self.rect.top
        self.rect.left += dx
        self.rect.top += dy
        blocked = pygame.sprite.spritecollide(self, walls, False)
        self.rect.left, self.rect.top = old_x, old_y
        return not blocked

    def _move_toward_exit(self, walls):
        if abs(self.rect.left - self.HOUSE_EXIT_X) > 1:
            step = min(self.speed, abs(self.rect.left - self.HOUSE_EXIT_X))
            dx = step if self.rect.left < self.HOUSE_EXIT_X else -step
            if self._can_move(walls, dx, 0):
                self.rect.left += dx
                return

        step = min(self.speed, abs(self.rect.top - self.HOUSE_EXIT_Y))
        dy = -step if self.rect.top > self.HOUSE_EXIT_Y else step
        if step and self._can_move(walls, 0, dy):
            self.rect.top += dy
            return

        self.has_left_house = True
        self._pick_random_direction()

    def update(self, walls, gate):
        if not self.has_left_house:
            self._move_toward_exit(walls)
            return

        old_x, old_y = self.rect.left, self.rect.top

        self.rect.left += self.change_x
        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.left = old_x
            self._pick_random_direction()
            return

        self.rect.top += self.change_y
        if pygame.sprite.spritecollide(self, walls, False):
            self.rect.top = old_y
            self._pick_random_direction()
            return

        self.direction_ttl -= 1
        if self.direction_ttl <= 0:
            self._pick_random_direction()


# ── Blinky: free-roaming AI ghost (NO hardcoded path) ────────────────────────
class BlinkyAI(Player):
    """
    Blinky moves freely around the maze without a scripted direction list.
    Direction is chosen randomly when Blinky hits a wall or every
    `direction_ttl` ticks — whichever comes first.

    For GA integration: call `set_genome_speed(dx, dy)` to override the
    AI choice with a genome-prescribed direction.
    """

    DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def __init__(self, x, y, filename, speed, rng_seed=None):
        super().__init__(x, y, filename)
        self.speed        = speed
        self._rng         = random.Random(rng_seed)
        self.direction_ttl = 0          # ticks until forced re-roll
        self._genome_dx   = None        # set by GA; None → use AI
        self._genome_dy   = None
        self._pick_random_direction()

    # ── GA hook ───────────────────────────────────────────────────────────────
    def set_genome_speed(self, dx, dy):
        """Override autonomous AI with a GA-prescribed direction this tick."""
        self._genome_dx = dx
        self._genome_dy = dy

    def clear_genome_speed(self):
        self._genome_dx = None
        self._genome_dy = None

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _pick_random_direction(self):
        dx, dy = self._rng.choice(self.DIRECTIONS)
        self.change_x = dx * self.speed
        self.change_y = dy * self.speed
        self.direction_ttl = self._rng.randint(5, 20)   # hold direction 5-20 ticks

    def update(self, walls, gate):
        # Apply genome override if set
        if self._genome_dx is not None:
            self.change_x = self._genome_dx
            self.change_y = self._genome_dy

        old_x = self.rect.left
        old_y = self.rect.top

        self.rect.left += self.change_x
        x_hit = pygame.sprite.spritecollide(self, walls, False)
        if x_hit:
            self.rect.left = old_x
            self._pick_random_direction()   # bounce: pick new dir
            return

        self.rect.top += self.change_y
        y_hit = pygame.sprite.spritecollide(self, walls, False)
        if y_hit:
            self.rect.top = old_y
            self._pick_random_direction()
            return

        # Periodic random re-direction (keeps movement natural)
        self.direction_ttl -= 1
        if self.direction_ttl <= 0:
            self._pick_random_direction()


# ── Scripted direction tables (Pinky, Inky, Clyde unchanged) ─────────────────
Pinky_directions = [
    [0,-30,4],[15,0,9],[0,15,11],[-15,0,23],[0,15,7],[15,0,3],[0,-15,3],
    [15,0,19],[0,15,3],[15,0,3],[0,15,3],[15,0,3],[0,-15,15],[-15,0,7],
    [0,15,3],[-15,0,19],[0,-15,11],[15,0,9],
]
Blinky_directions = []   # kept empty — Blinky is now BlinkyAI

Inky_directions = [
    [30,0,2],[0,-15,4],[15,0,10],[0,15,7],[15,0,3],[0,-15,3],[15,0,3],
    [0,-15,15],[-15,0,15],[0,15,3],[15,0,15],[0,15,11],[-15,0,3],[0,-15,7],
    [-15,0,11],[0,15,3],[-15,0,11],[0,15,7],[-15,0,3],[0,-15,3],[-15,0,3],
    [0,-15,15],[15,0,15],[0,15,3],[-15,0,15],[0,15,11],[15,0,3],[0,-15,11],
    [15,0,11],[0,15,3],[15,0,1],
]
Clyde_directions = [
    [-30,0,2],[0,-15,4],[15,0,5],[0,15,7],[-15,0,11],[0,-15,7],[-15,0,3],
    [0,15,7],[-15,0,7],[0,15,15],[15,0,15],[0,-15,3],[-15,0,11],[0,-15,7],
    [15,0,3],[0,-15,11],[15,0,9],
]

pl = len(Pinky_directions) - 1
il = len(Inky_directions)  - 1
cl = len(Clyde_directions) - 1


# ── Pygame init ───────────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode([606, 606])
pygame.display.set_caption('Pacman — GA Ready')
background = pygame.Surface(screen.get_size()).convert()
background.fill(black)
clock = pygame.time.Clock()
font  = pygame.font.Font("freesansbold.ttf", 24)

# Default spawn positions
w   = 303 - 16
p_h = (7 * 60) + 19
m_h = (4 * 60) + 19
b_h = (3 * 60) + 19
i_w = 303 - 16 - 32
c_w = 303 + (32 - 16)


# ── Main game function ────────────────────────────────────────────────────────
def startGame(maze_seed=None, maze_drop_prob=0.0, speed_seed=None):
    """
    maze_seed       – seed for wall layout (None = classic maze)
    maze_drop_prob  – fraction of interior walls to randomly omit  [0..1]
    speed_seed      – seed for randomised speeds (None = fresh random)

    GA usage example:
        startGame(maze_seed=42, maze_drop_prob=0.2, speed_seed=7)
    """
    speed_rng = random.Random(speed_seed)

    # Randomised speeds (drawn once per game instance)
    pacman_speed = speed_rng.choice(SPEED_OPTIONS)
    ghost_speed  = speed_rng.choice(SPEED_OPTIONS)
    print(f"[GA] pacman_speed={pacman_speed}  ghost_speed={ghost_speed}  "
          f"maze_seed={maze_seed}  drop_prob={maze_drop_prob}")

    all_sprites_list = pygame.sprite.RenderPlain()
    block_list       = pygame.sprite.RenderPlain()
    monsta_list      = pygame.sprite.RenderPlain()
    pacman_collide   = pygame.sprite.RenderPlain()

    wall_list = setup_walls(all_sprites_list, seed=maze_seed,
                            drop_probability=maze_drop_prob)
    gate      = setup_gate(all_sprites_list)

    p_turn = b_turn = i_turn = c_turn = 0
    p_steps = b_steps = i_steps = c_steps = 0

    # ── Sprites ───────────────────────────────────────────────────────────────
    Pacman = Player(w, p_h, "images/Trollman.png")
    all_sprites_list.add(Pacman)
    pacman_collide.add(Pacman)

    # Blinky: free-roaming AI (GA can call set_genome_speed each tick)
    Blinky = BlinkyAI(w, b_h, "images/Blinky.png",
                      speed=ghost_speed, rng_seed=speed_seed)
    monsta_list.add(Blinky)
    all_sprites_list.add(Blinky)

    # Scripted ghosts with randomised step sizes
    def scale_dirs(directions, new_speed):
        """Re-scale direction magnitudes to match the chosen ghost_speed."""
        scaled = []
        for d in directions:
            orig_mag = max(abs(d[0]), abs(d[1]))
            if orig_mag == 0:
                scaled.append(d)
                continue
            factor = new_speed / orig_mag
            scaled.append([int(d[0] * factor), int(d[1] * factor), d[2]])
        return scaled

    Pinky = RandomGhostAI(w,   m_h, "images/Pinky.png", speed=ghost_speed, rng_seed=speed_rng.randint(0, 9999))
    Inky  = RandomGhostAI(i_w, m_h, "images/Inky.png",  speed=ghost_speed, rng_seed=speed_rng.randint(0, 9999))
    Clyde = RandomGhostAI(c_w, m_h, "images/Clyde.png", speed=ghost_speed, rng_seed=speed_rng.randint(0, 9999))
    for g in (Pinky, Inky, Clyde):
        monsta_list.add(g)
        all_sprites_list.add(g)

    scaled_pinky = scale_dirs(Pinky_directions, ghost_speed)
    scaled_inky  = scale_dirs(Inky_directions,  ghost_speed)
    scaled_clyde = scale_dirs(Clyde_directions, ghost_speed)

    # ── Pellets ───────────────────────────────────────────────────────────────
    for row in range(19):
        for column in range(19):
            if (row in (7, 8)) and (column in (8, 9, 10)):
                continue
            block = Block(yellow, 4, 4)
            block.rect.x = (30 * column + 6) + 26
            block.rect.y = (30 * row   + 6) + 26
            if (pygame.sprite.spritecollide(block, wall_list, False) or
                    pygame.sprite.spritecollide(block, pacman_collide, False)):
                continue
            block_list.add(block)
            all_sprites_list.add(block)

    total_pellets = len(block_list)
    score = 0
    done  = False

    # ── Game loop ─────────────────────────────────────────────────────────────
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:  Pacman.changespeed(-pacman_speed, 0)
                if event.key == pygame.K_RIGHT: Pacman.changespeed( pacman_speed, 0)
                if event.key == pygame.K_UP:    Pacman.changespeed(0, -pacman_speed)
                if event.key == pygame.K_DOWN:  Pacman.changespeed(0,  pacman_speed)

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT:  Pacman.changespeed( pacman_speed, 0)
                if event.key == pygame.K_RIGHT: Pacman.changespeed(-pacman_speed, 0)
                if event.key == pygame.K_UP:    Pacman.changespeed(0,  pacman_speed)
                if event.key == pygame.K_DOWN:  Pacman.changespeed(0, -pacman_speed)

        # ── Update ────────────────────────────────────────────────────────────
        Pacman.update(wall_list, gate)

        # Blinky: autonomous AI (no scripted path)
        # GA hook: insert  Blinky.set_genome_speed(dx, dy)  here per tick
        Blinky.update(wall_list, False)

        # Pinky, Inky, and Clyde leave the middle square first, then roam.
        Pinky.update(wall_list, False)
        Inky.update(wall_list, False)
        Clyde.update(wall_list, False)

        # Pellet collection
        hits = pygame.sprite.spritecollide(Pacman, block_list, True)
        score += len(hits)

        # ── Draw ──────────────────────────────────────────────────────────────
        screen.fill(black)
        wall_list.draw(screen)
        gate.draw(screen)
        all_sprites_list.draw(screen)
        monsta_list.draw(screen)

        text = font.render(f"Score: {score}/{total_pellets}", True, red)
        screen.blit(text, [10, 10])
        speed_text = font.render(
            f"P:{pacman_speed}px  G:{ghost_speed}px", True, white)
        screen.blit(speed_text, [10, 580])

        if score == total_pellets:
            doNext("Congratulations, you won!", 145,
                   all_sprites_list, block_list, monsta_list,
                   pacman_collide, wall_list, gate, maze_seed,
                   maze_drop_prob, speed_seed)

        if pygame.sprite.spritecollide(Pacman, monsta_list, False):
            doNext("Game Over", 235,
                   all_sprites_list, block_list, monsta_list,
                   pacman_collide, wall_list, gate, maze_seed,
                   maze_drop_prob, speed_seed)

        pygame.display.flip()
        clock.tick(10)


# ── End screen ────────────────────────────────────────────────────────────────
def doNext(message, left,
           all_sprites_list, block_list, monsta_list, pacman_collide,
           wall_list, gate, maze_seed, maze_drop_prob, speed_seed):
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); return
                if event.key == pygame.K_RETURN:
                    for grp in (all_sprites_list, block_list, monsta_list,
                                pacman_collide, wall_list, gate):
                        del grp
                    # New random speed seed each retry so speeds re-randomise
                    startGame(maze_seed=maze_seed,
                              maze_drop_prob=maze_drop_prob,
                              speed_seed=random.randint(0, 9999))
                    return

        w_surf = pygame.Surface((400, 200))
        w_surf.set_alpha(10)
        w_surf.fill((128, 128, 128))
        screen.blit(w_surf, (100, 200))

        screen.blit(font.render(message, True, white),  [left, 233])
        screen.blit(font.render("Press ENTER to play again.", True, white), [135, 303])
        screen.blit(font.render("Press ESCAPE to quit.",      True, white), [165, 333])

        pygame.display.flip()
        clock.tick(10)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Classic maze + fresh random speeds:
    startGame()

    # GA example (uncomment to test):
    # startGame(maze_seed=42, maze_drop_prob=0.15, speed_seed=7)

    pygame.quit()
