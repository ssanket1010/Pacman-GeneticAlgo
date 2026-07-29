import random

class Chromosome:
    def __init__(self):
        self.genes = {
            "aggressiveness": random.uniform(0, 1),
            "ambush": random.uniform(0, 1),
            "retreat": random.uniform(0, 1),
            "coordination": random.uniform(0, 1),
        }

        self.fitness = 0