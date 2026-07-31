"""Stratified random sample from the six subgroups.
Used for debugging (sample size: 1/2) or testing different
pipeline configurations (sample size: ~17)"""

from collections import defaultdict, Counter
import random

def group_by_cell(claims):
    # Split the 700 claims into the 6 (subset, label) groups.
    cells = defaultdict(list)
    for c in claims:
        cells[(c.subset, c.entailment_label)].append(c)

    return dict(cells)


def check_balance(sample, per_cell):
    # raises errors if the sample is not exactly balanced.
    counts = Counter((c.subset, c.entailment_label) for c in sample)

    if len(counts) != 6:
        raise ValueError(f"expected 6 cells, got {len(counts)}: {dict(counts)}")

    off = {k: v for k, v in counts.items() if v != per_cell}

    if off:
        raise ValueError(f"cells not at {per_cell}: {off}")


SEED = 0

def stratified_sample(claims, per_cell, seed = SEED):
    # Draw claims from each of the 6 cells deterministically.
    cells = group_by_cell(claims)
    rng = random.Random(seed) #creates a private generator for this function seeded with 0 so the sequence of nums is always the same

    samp = []
    for key in sorted(cells):
        samp.extend(rng.sample(cells[key], per_cell))

    rng.shuffle(samp)
    check_balance(samp, per_cell)
    return samp