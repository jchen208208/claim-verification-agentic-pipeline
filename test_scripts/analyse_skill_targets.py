"""What would a per-subset prompt skill actually have to fix?

The skills idea is conditional prompting: a differently built prompt per model,
possibly per subset. Before spending a GPU night on one, this asks the offline
question the architecture plan demands of any expensive idea: is there an
identifiable failure for a skill to target, or are the errors diffuse?

Everything here reads stored result files and the benchmark's own fields. No
model calls, no GPU, no cloud quota.

NUMERIC. FINDVER ships `execution_result`, its own computed answer, for every
numeric claim on testmini. So for each claim we can measure how far the asserted
value sits from the truth, and split accuracy by that distance. A claim refuted
because it says -9.63% where the truth is -9.64% is a different task from one
refuted because it says 171% where the truth is 26%.

    Two data facts the loader's type hint hides. `execution_result` is int on 37
    claims, float on 202 and a LIST of 2-3 values on 11, where the claim asserts
    several quantities. And test.json ships none of these fields at all, so this
    analysis is testmini-only (see the 16 August trap).

    Matching the asserted value to the gold value needs two allowances, both
    validated below rather than assumed. Sign, because direction is often carried
    in words while the numeral stays positive: "a decrease of $61,525" against a
    gold of -61525. And scale, because a filing may report in thousands: trap 7.

KNOWLEDGE. 2.17 found that one failure mode, declaring the evidence absent and
refuting on that basis, is 63% of the cloud model's knowledge errors on both
splits. This checks whether the same mode explains the LOCAL models' knowledge
errors, because a skill for the 3B has to fix the 3B's failure and not the
cloud's.

Usage:
    python3 test_scripts/analyse_skill_targets.py
"""

import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse_condition1 import load_run
from analyse_missing_info import cites_missing
from src.loader import load_claims

RUNS = {
    "3B": "condition1_3b_full700",
    "7B": "condition1_7b_full700",
    "cloud v2": "condition2_flash_v2_full700",
}

NUMBER = re.compile(r"-?\$?\s?\d[\d,]*(?:\.\d+)?")

# Multipliers tried when matching an asserted value to the gold value. Chosen by
# validation, not by taste: this set matches 122 of 125 entailed claims within 1%
# where an up-only set matched 118, while moving the refuted-looking-tight count
# only from 36 to 37. A set that also matched refuted claims would be too loose.
SCALES = (1, 1e3, 1e-3, 1e6, 1e-6, 1e-2, 1e2)

# How far the claim sits from the truth. The names are the point: a claim inside
# 0.1% cannot be rejected without computing the value to better than one part in
# a thousand.
BUCKETS = (("tight <0.1%", 0.0, 0.001),
           ("mid 0.1-1%", 0.001, 0.01),
           ("loose >1%", 0.01, float("inf")))


def numbers_in(text):
    """Every number in the text, with both signs as candidates."""
    values = []
    for match in NUMBER.findall(text):
        try:
            values.append(float(match.replace("$", "").replace(",", "").strip()))
        except ValueError:
            pass
    return values + [-v for v in values]


def gold_values(claim):
    """execution_result as a list, because 11 claims carry several values."""
    result = claim.execution_result
    return [float(v) for v in result] if isinstance(result, list) else [float(result)]


def margin(claim):
    """Relative distance from the asserted value(s) to the gold value(s).

    Worst case over gold values, so a claim asserting two quantities is only
    'tight' when BOTH of its numbers are close. Best case over asserted numbers
    and scales, because the statement contains dates and other figures too.
    """
    asserted = numbers_in(claim.statement)
    if not asserted:
        return None
    errors = []
    for gold in gold_values(claim):
        if gold == 0:
            continue
        errors.append(min(abs(value * scale - gold) / abs(gold)
                          for value in asserted for scale in SCALES))
    return max(errors) if errors else None


def accuracy(run, ids):
    correct = sum(run[i]["extracted_label"] == run[i]["gold_label"] for i in ids)
    return correct, len(ids), correct / len(ids) if ids else 0.0


def two_proportion_z(k1, n1, k2, n2):
    """z for two independent proportions. Unpaired, because the two buckets hold
    different claims; McNemar does not apply."""
    if not n1 or not n2:
        return 0.0
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (k2 / n2 - k1 / n1) / se


def numeric_section(claims):
    numeric = {i: c for i, c in claims.items() if c.subset == "numeric"}
    entailed = [c for c in numeric.values() if c.entailment_label]
    refuted = [c for c in numeric.values() if not c.entailment_label]

    # Validation first. Entailed claims assert the gold value by definition, so a
    # matcher that cannot find it on them is broken and every number below would
    # inherit the fault.
    matched = sum(1 for c in entailed
                  if (m := margin(c)) is not None and m < 0.01)
    print(f"\nVALIDATION: {matched}/{len(entailed)} entailed claims match gold within 1%")
    print("  They assert the gold value by definition, so this is the matcher's own test.")

    print("\nHOW FAR REFUTED CLAIMS SIT FROM THE TRUTH")
    counts = {}
    for name, low, high in BUCKETS:
        counts[name] = [c.example_id for c in refuted
                        if (m := margin(c)) is not None and low <= m < high]
        n = len(counts[name])
        print(f"  {name:14} {n:>4} claims = {n / len(refuted):>5.1%} of refuted numeric")

    print("\nACCURACY ON REFUTED NUMERIC CLAIMS, BY MARGIN")
    print(f"  {'model':10}" + "".join(f"{b[0]:>18}" for b in BUCKETS))
    for label, directory in RUNS.items():
        run = load_run(directory)
        cells = []
        for name, _, _ in BUCKETS:
            ids = [i for i in counts[name] if i in run]
            correct, n, acc = accuracy(run, ids)
            cells.append(f"{acc:.1%} ({correct}/{n})")
        print(f"  {label:10}" + "".join(f"{c:>18}" for c in cells))

    print("\n  what they PREDICT there, where gold is always refuted")
    for label, directory in RUNS.items():
        run = load_run(directory)
        cells = []
        for name, _, _ in BUCKETS:
            ids = [i for i in counts[name] if i in run]
            says_entailed = sum(run[i]["extracted_label"] is True for i in ids)
            cells.append(f"entailed {says_entailed / len(ids):.0%}")
        print(f"  {label:10}" + "".join(f"{c:>18}" for c in cells))

    print("\n  loose minus tight, is the gap real")
    for label, directory in RUNS.items():
        run = load_run(directory)
        tight = [i for i in counts[BUCKETS[0][0]] if i in run]
        loose = [i for i in counts[BUCKETS[2][0]] if i in run]
        kt, nt, at = accuracy(run, tight)
        kl, nl, al = accuracy(run, loose)
        z = two_proportion_z(kt, nt, kl, nl)
        verdict = "SIGNIFICANT" if abs(z) > 1.96 else "not significant"
        print(f"  {label:10} {al - at:>+7.1%}   z = {z:>5.2f}   {verdict}")


def knowledge_section():
    print("\n\nKNOWLEDGE: does the cloud's dominant failure mode explain the LOCAL models?")
    print("  the mode (2.17): declares the evidence absent, refutes, and is wrong\n")
    print(f"  {'model':10}{'cites missing':>15}{'then refutes':>14}"
          f"{'those wrong':>13}{'base refute wrong':>19}{'lift':>7}")
    for label, directory in RUNS.items():
        run = load_run(directory)
        ids = [i for i in sorted(run) if run[i]["subset"] == "knowledge"]
        cites = [i for i in ids if cites_missing(run[i])]
        refutes = [i for i in cites if run[i]["extracted_label"] is False]
        wrong = [i for i in refutes if run[i]["gold_label"] is not False]

        all_refuted = [i for i in ids if run[i]["extracted_label"] is False]
        all_wrong = [i for i in all_refuted if run[i]["gold_label"] is not False]

        rate = len(wrong) / len(refutes) if refutes else 0.0
        base = len(all_wrong) / len(all_refuted) if all_refuted else 0.0
        lift = rate / base if base else 0.0
        print(f"  {label:10}{len(cites) / len(ids):>14.1%}"
              f"{len(refutes) / max(len(cites), 1):>13.1%}"
              f"{rate:>12.1%}{base:>18.1%}{lift:>7.2f}x")

    print("\n  A lift near 1.00 means the phrase carries no signal for that model:")
    print("  it refutes wrongly just as often when it does NOT cite missing evidence.")


def main():
    claims = {c.example_id: c for c in load_claims()}
    print("testmini only. test.json ships no execution_result, python_calculation")
    print("or knowledge fields at all, so none of the numeric analysis transfers.")
    numeric_section(claims)
    knowledge_section()
    return 0


if __name__ == "__main__":
    sys.exit(main())
