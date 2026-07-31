"""Stratified random sample from the six subgroups.
Used for debugging (sample size: 1/2) or testing different
pipeline configurations (sample size: ~17)"""

from collections import defaultdict
import random

def group_by_cell(claims):
    # Split the 700 claims into the 6 (subset, label) groups.
    cells = defaultdict(list)
    for c in claims:
        cells[(c.subset, c.entailment_label)].append(c)

    return dict(cells)

SEED = 0

def stratified_sample(claims, per_cell, seed = SEED):
    # Draw claims from each of the 6 cells deterministically.
    cells = group_by_cell(claims)
    rng = random.Random(seed) #creates a private generator for this function seeded with 0 so the sequence of nums is always the same

    samp = []
    for key in sorted(cells):
        samp.extend(rng.sample(cells[key], per_cell))

    rng.shuffle(samp)
    return samp