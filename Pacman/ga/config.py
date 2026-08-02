"""Configuration constants for the Pacman genetic algorithm."""

# GA hyper-parameters
POP_SIZE = 40        # individuals per generation
SEQ_LEN = 200        # number of move steps per genome
N_GENERATIONS = 30   # generations to run
ELITE_K = 4          # top-K elites copied unchanged each generation
TOURNAMENT_K = 5     # tournament size for parent selection
MUTATION_RATE = 0.03 # probability of flipping any single move gene
TICKS_PER_STEP = 1   # game ticks between move changes (keep at 1 headless)

# Genome encoding
SPEED_OPTIONS = [15, 20, 25, 30] # pixel increments per tick
MOVES = [0, 1, 2, 3] # UP DOWN LEFT RIGHT
GENOME_LEN = SEQ_LEN + 3 # moves + blinky_speed_idx + maze_seed + drop_prob_raw

# Movement lookup: (dx, dy) multiplied by Pacman's speed.
MOVE_DELTAS = {
    0: (0, -1),
    1: (0, 1),
    2: (-1, 0),
    3: (1, 0),
}

# Fitness weights
W_PELLET = 10.0        # reward per pellet eaten
W_SURVIVAL = 0.05      # reward per tick alive (encourages exploration)
W_DEATH_PENALTY = 50.0 # subtracted if Pacman is caught before all pellets gone
W_WIN_BONUS = 500.0    # bonus for eating every pellet
