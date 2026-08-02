"""Genome creation, mutation, crossover, and selection helpers."""

import random

from .config import GENOME_LEN, MOVES, MUTATION_RATE, SEQ_LEN, SPEED_OPTIONS, TOURNAMENT_K


def random_genome():
    """Create a random list-based Pacman GA genome."""
    moves = [random.choice(MOVES) for _ in range(SEQ_LEN)]
    blinky_idx = random.randint(0, len(SPEED_OPTIONS) - 1)
    maze_seed = random.randint(0, 9999)
    drop_raw = random.randint(0, 40)  # 0..40 → 0.0..0.40 after /100
    return moves + [blinky_idx, maze_seed, drop_raw]


def crossover(p1, p2):
    """Single-point crossover on the move segment; tail genes inherited."""
    cut = random.randint(1, SEQ_LEN - 1)
    child_moves = p1[:cut] + p2[cut:SEQ_LEN]
    child_tail = [random.choice([p1[i], p2[i]]) for i in range(SEQ_LEN, GENOME_LEN)]
    return child_moves + child_tail


def mutate(genome, rate=MUTATION_RATE):
    """Return a mutated copy of a list-based Pacman GA genome."""
    mutated = genome[:]
    for i in range(SEQ_LEN):
        if random.random() < rate:
            mutated[i] = random.choice(MOVES)

    # Occasionally mutate tail parameters.
    if random.random() < 0.1:
        mutated[SEQ_LEN] = random.randint(0, len(SPEED_OPTIONS) - 1)
    if random.random() < 0.05:
        mutated[SEQ_LEN + 1] = random.randint(0, 9999)
    if random.random() < 0.1:
        mutated[SEQ_LEN + 2] = max(0, min(40, mutated[SEQ_LEN + 2] + random.randint(-5, 5)))
    return mutated


def tournament_select(population, fitnesses, k=TOURNAMENT_K):
    """Select the fittest genome from a random tournament."""
    contestants = random.sample(range(len(population)), k)
    best = max(contestants, key=lambda i: fitnesses[i])
    return population[best]
