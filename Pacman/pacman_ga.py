"""
pacman_ga.py — Genetic Algorithm solver for GA-ready Pacman
============================================================
Requires: pacman_ga_ready.py in the same folder (for Wall, BlinkyAI, etc.)

Run:
    python pacman_ga.py               # headless GA, prints best genome each gen
    python pacman_ga.py --watch       # renders best genome of each gen in pygame
    python pacman_ga.py --play 42     # plays genome index 42 from last run visually

Genome encoding  (one list per individual):
    [move_0, move_1, ..., move_{SEQ_LEN-1}, blinky_speed, maze_seed, drop_prob]

    move_i      : int  0=UP 1=DOWN 2=LEFT 3=RIGHT
    blinky_speed: int  chosen from SPEED_OPTIONS
    maze_seed   : int  0..9999
    drop_prob   : float 0.0..0.4  (fraction of interior walls removed)
"""

import random
import sys
import math
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"   # suppress display by default
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

# ── Import our modified Pacman module ────────────────────────────────────────
# We import only the non-display pieces; startGame() is NOT called.
from pacman_ga_ready import (
    Wall, Block, Player, Ghost, BlinkyAI, RandomGhostAI,
    setup_walls, setup_gate,
    Pinky_directions, Inky_directions, Clyde_directions,
    SPEED_OPTIONS,
    w as PAC_X, p_h as PAC_Y,
    m_h as GHOST_Y, b_h as BLINKY_Y,
    i_w as INKY_X, c_w as CLYDE_X,
)

# ── GA hyper-parameters ──────────────────────────────────────────────────────
POP_SIZE        = 40        # individuals per generation
SEQ_LEN         = 200       # number of move steps per genome
N_GENERATIONS   = 30        # generations to run
ELITE_K         = 4         # top-K elites copied unchanged each generation
TOURNAMENT_K    = 5         # tournament size for parent selection
MUTATION_RATE   = 0.03      # probability of flipping any single move gene
TICKS_PER_STEP  = 1         # game ticks between move changes (keep at 1 headless)

MOVES           = [0, 1, 2, 3]   # UP DOWN LEFT RIGHT
MOVE_DELTAS     = {               # (dx, dy) at speed S
    0: (0, -1),
    1: (0,  1),
    2: (-1, 0),
    3:  (1, 0),
}

# ── Fitness weights ───────────────────────────────────────────────────────────
W_PELLET        = 10.0   # reward per pellet eaten
W_SURVIVAL      = 0.05   # reward per tick alive (encourages exploration)
W_DEATH_PENALTY = 50.0   # subtracted if Pacman is caught before all pellets gone
W_WIN_BONUS     = 500.0  # bonus for eating every pellet


# ─────────────────────────────────────────────────────────────────────────────
# Headless game simulation
# ─────────────────────────────────────────────────────────────────────────────

def _make_game(maze_seed, drop_prob, ghost_speed, pac_speed):
    """
    Build all sprites and return (Pacman, Blinky, Pinky, Inky, Clyde,
                                   wall_list, gate, block_list, total_pellets)
    without opening a display window.
    """
    all_sprites  = pygame.sprite.RenderPlain()
    block_list   = pygame.sprite.RenderPlain()
    pac_collide  = pygame.sprite.RenderPlain()

    wall_list = setup_walls(all_sprites, seed=maze_seed, drop_probability=drop_prob)
    gate      = setup_gate(all_sprites)

    Pacman = Player(PAC_X, PAC_Y, "images/Trollman.png")
    all_sprites.add(Pacman)
    pac_collide.add(Pacman)

    Blinky = BlinkyAI(PAC_X, BLINKY_Y, "images/Blinky.png",
                      speed=ghost_speed, rng_seed=maze_seed)

    pl = len(Pinky_directions) - 1
    il = len(Inky_directions)  - 1
    cl = len(Clyde_directions) - 1

    Pinky = RandomGhostAI(PAC_X,  GHOST_Y, "images/Pinky.png", speed=ghost_speed, rng_seed=maze_seed + 1)
    Inky  = RandomGhostAI(INKY_X, GHOST_Y, "images/Inky.png",  speed=ghost_speed, rng_seed=maze_seed + 2)
    Clyde = RandomGhostAI(CLYDE_X, GHOST_Y, "images/Clyde.png", speed=ghost_speed, rng_seed=maze_seed + 3)

    monsta_list = pygame.sprite.RenderPlain()
    for g in (Blinky, Pinky, Inky, Clyde):
        monsta_list.add(g)
        all_sprites.add(g)

    # Pellets
    for row in range(19):
        for col in range(19):
            if row in (7, 8) and col in (8, 9, 10):
                continue
            block = Block((255, 255, 0), 4, 4)
            block.rect.x = (30 * col + 6) + 26
            block.rect.y = (30 * row + 6) + 26
            if (pygame.sprite.spritecollide(block, wall_list, False) or
                    pygame.sprite.spritecollide(block, pac_collide, False)):
                continue
            block_list.add(block)
            all_sprites.add(block)

    total = len(block_list)

    def _scale(dirs, spd):
        out = []
        for d in dirs:
            mag = max(abs(d[0]), abs(d[1]))
            f   = spd / mag if mag else 1
            out.append([int(d[0]*f), int(d[1]*f), d[2]])
        return out

    scaled_pinky  = _scale(Pinky_directions, ghost_speed)
    scaled_inky   = _scale(Inky_directions,  ghost_speed)
    scaled_clyde  = _scale(Clyde_directions, ghost_speed)

    return (Pacman, Blinky, Pinky, Inky, Clyde,
            wall_list, gate, block_list, monsta_list,
            total, scaled_pinky, scaled_inky, scaled_clyde,
            pl, il, cl, pac_speed)


def simulate(genome, render=False):
    """
    Run one genome through the game and return its fitness score.

    genome layout: [move_0..move_{SEQ_LEN-1}, blinky_speed_idx, maze_seed, drop_prob_raw]
    """
    moves       = genome[:SEQ_LEN]
    blinky_spd  = SPEED_OPTIONS[genome[SEQ_LEN] % len(SPEED_OPTIONS)]
    maze_seed   = int(genome[SEQ_LEN + 1]) % 10000
    drop_prob   = min(0.4, max(0.0, genome[SEQ_LEN + 2] / 100.0))
    pac_speed   = blinky_spd   # same speed pool; genome implicitly chooses via blinky_spd

    (Pacman, Blinky, Pinky, Inky, Clyde,
     wall_list, gate, block_list, monsta_list,
     total, sp_pinky, sp_inky, sp_clyde,
     pl, il, cl, pac_spd) = _make_game(maze_seed, drop_prob, blinky_spd, pac_speed)

    if render:
        screen = pygame.display.get_surface()
        clock  = pygame.time.Clock()
        font   = pygame.font.Font("freesansbold.ttf", 18)

    score       = 0
    ticks_alive = 0
    dead        = False
    won         = False

    p_turn = b_turn = i_turn = c_turn = 0
    p_steps = b_steps = i_steps = c_steps = 0

    # Apply move sequence
    for step_idx, move in enumerate(moves):
        if dead or won:
            break

        dx, dy = MOVE_DELTAS[move]
        # Reset velocity, apply genome direction
        Pacman.change_x = dx * pac_spd
        Pacman.change_y = dy * pac_spd

        for _ in range(TICKS_PER_STEP):
            Pacman.update(wall_list, gate)

            Blinky.update(wall_list, False)

            Pinky.update(wall_list, False)
            Inky.update(wall_list, False)
            Clyde.update(wall_list, False)

            hits = pygame.sprite.spritecollide(Pacman, block_list, True)
            score += len(hits)
            ticks_alive += 1

            if pygame.sprite.spritecollide(Pacman, monsta_list, False):
                dead = True
                break

            if score == total:
                won = True
                break

        if render and pygame.display.get_surface():
            screen.fill((0, 0, 0))
            wall_list.draw(screen)
            gate.draw(screen)
            block_list.draw(screen)
            monsta_list.draw(screen)
            Pacman.draw(screen) if hasattr(Pacman, 'draw') else None
            pygame.sprite.RenderPlain(Pacman).draw(screen)
            txt = font.render(f"Step {step_idx+1}/{SEQ_LEN}  Score {score}/{total}", True, (255,0,0))
            screen.blit(txt, [10, 10])
            pygame.display.flip()
            clock.tick(15)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()

    # ── Fitness ───────────────────────────────────────────────────────────────
    fitness = score * W_PELLET + ticks_alive * W_SURVIVAL
    if dead:
        fitness -= W_DEATH_PENALTY
    if won:
        fitness += W_WIN_BONUS

    return fitness


# ─────────────────────────────────────────────────────────────────────────────
# Genome helpers
# ─────────────────────────────────────────────────────────────────────────────

GENOME_LEN = SEQ_LEN + 3   # moves + blinky_speed_idx + maze_seed + drop_prob_raw

def random_genome():
    moves = [random.choice(MOVES) for _ in range(SEQ_LEN)]
    blinky_idx = random.randint(0, len(SPEED_OPTIONS) - 1)
    maze_seed  = random.randint(0, 9999)
    drop_raw   = random.randint(0, 40)   # 0..40 → 0.0..0.40 after /100
    return moves + [blinky_idx, maze_seed, drop_raw]


def crossover(p1, p2):
    """Single-point crossover on the move segment; tail genes averaged."""
    cut = random.randint(1, SEQ_LEN - 1)
    child_moves = p1[:cut] + p2[cut:SEQ_LEN]
    # Tail: randomly inherit from one parent
    child_tail  = [random.choice([p1[i], p2[i]]) for i in range(SEQ_LEN, GENOME_LEN)]
    return child_moves + child_tail


def mutate(genome, rate=MUTATION_RATE):
    g = genome[:]
    for i in range(SEQ_LEN):
        if random.random() < rate:
            g[i] = random.choice(MOVES)
    # Occasionally mutate tail parameters
    if random.random() < 0.1:
        g[SEQ_LEN] = random.randint(0, len(SPEED_OPTIONS) - 1)
    if random.random() < 0.05:
        g[SEQ_LEN + 1] = random.randint(0, 9999)
    if random.random() < 0.1:
        g[SEQ_LEN + 2] = max(0, min(40, g[SEQ_LEN + 2] + random.randint(-5, 5)))
    return g


def tournament_select(population, fitnesses, k=TOURNAMENT_K):
    contestants = random.sample(range(len(population)), k)
    best = max(contestants, key=lambda i: fitnesses[i])
    return population[best]


# ─────────────────────────────────────────────────────────────────────────────
# Main GA loop
# ─────────────────────────────────────────────────────────────────────────────

def run_ga(watch=False):
    pygame.init()

    if watch:
        import os
        os.environ.pop("SDL_VIDEODRIVER", None)
        screen = pygame.display.set_mode([606, 606])
        pygame.display.set_caption("Pacman GA — watching best genome")
    else:
        pygame.display.set_mode([1, 1])   # minimal surface, no window

    population = [random_genome() for _ in range(POP_SIZE)]
    best_ever_genome   = None
    best_ever_fitness  = -math.inf

    for gen in range(1, N_GENERATIONS + 1):
        # ── Evaluate ──────────────────────────────────────────────────────────
        fitnesses = [simulate(g) for g in population]

        ranked = sorted(zip(fitnesses, population), key=lambda x: x[0], reverse=True)
        gen_best_f, gen_best_g = ranked[0]

        if gen_best_f > best_ever_fitness:
            best_ever_fitness = gen_best_f
            best_ever_genome  = gen_best_g[:]

        avg_f = sum(fitnesses) / len(fitnesses)
        print(f"Gen {gen:3d}/{N_GENERATIONS}  best={gen_best_f:8.1f}  "
              f"avg={avg_f:8.1f}  all-time_best={best_ever_fitness:8.1f}")

        # Optionally render the best genome of this generation
        if watch:
            print("  → rendering best genome…")
            simulate(gen_best_g, render=True)

        # ── Next generation ───────────────────────────────────────────────────
        new_pop = [g for _, g in ranked[:ELITE_K]]   # elites pass through

        while len(new_pop) < POP_SIZE:
            p1 = tournament_select(population, fitnesses)
            p2 = tournament_select(population, fitnesses)
            child = crossover(p1, p2)
            child = mutate(child)
            new_pop.append(child)

        population = new_pop

    print("\n── GA complete ──")
    print(f"Best fitness : {best_ever_fitness:.2f}")
    blinky_spd  = SPEED_OPTIONS[best_ever_genome[SEQ_LEN] % len(SPEED_OPTIONS)]
    maze_seed   = int(best_ever_genome[SEQ_LEN + 1]) % 10000
    drop_prob   = min(0.4, best_ever_genome[SEQ_LEN + 2] / 100.0)
    print(f"Best genome  : blinky_speed={blinky_spd}  maze_seed={maze_seed}  drop_prob={drop_prob:.2f}")
    print(f"Move preview : {best_ever_genome[:20]}…")
    return best_ever_genome, best_ever_fitness


def play_genome(genome):
    """Render a single genome visually (call after run_ga)."""
    import os
    os.environ.pop("SDL_VIDEODRIVER", None)
    pygame.init()
    pygame.display.set_mode([606, 606])
    pygame.display.set_caption("Pacman GA — playback")
    simulate(genome, render=True)
    pygame.quit()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--play" in args:
        # Quick demo: play a random genome visually
        print("Playing a random genome for demonstration…")
        g = random_genome()
        os.environ.pop("SDL_VIDEODRIVER", None)
        pygame.init()
        pygame.display.set_mode([606, 606])
        simulate(g, render=True)
        pygame.quit()

    elif "--watch" in args:
        best_g, best_f = run_ga(watch=True)
        print("\nReplaying best genome…")
        play_genome(best_g)

    else:
        best_g, best_f = run_ga(watch=False)
        ans = input("\nPlay back the best genome? [y/N] ").strip().lower()
        if ans == "y":
            play_genome(best_g)
