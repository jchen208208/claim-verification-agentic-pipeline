"""Stratified random sample from the six subgroups.
Used for debugging (sample size: 1/2) or testing different
pipeline configurations (sample size: ~17)"""

from collections import defaultdict


def group_by_cell(claims):
    # Split the 700 claims into the 6 (subset, label) groups.
    cells = defaultdict(list)
    for c in claims:
        cells[(c.subset, c.entailment_label)].append(c)

    return dict(cells)