"""Population helpers for the Pacman genetic algorithm."""

from .config import POP_SIZE
from .evolution import random_genome


def create_population(size=POP_SIZE):
    """Create a population of list-based genomes for the active GA."""
    return [random_genome() for _ in range(size)]


population = create_population()
