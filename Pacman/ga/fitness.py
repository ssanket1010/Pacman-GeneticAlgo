"""Fitness scoring helpers for the Pacman genetic algorithm."""

from .config import W_DEATH_PENALTY, W_PELLET, W_SURVIVAL, W_WIN_BONUS


def calculate_fitness(pellets_eaten, ticks_alive, dead=False, won=False):
    """Return the weighted GA fitness score for a simulation outcome."""
    fitness = pellets_eaten * W_PELLET + ticks_alive * W_SURVIVAL
    if dead:
        fitness -= W_DEATH_PENALTY
    if won:
        fitness += W_WIN_BONUS
    return fitness
