"""Regenerate every routing and label-bias number in paper_numbers.md §2.10.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. This script is that script for §2.10, which was first
produced by throwaway code typed into a terminal on 11 August.

It prints five things, all from stored result files, with no model calls:

    the bias table        how often each model says entailed, and its accuracy
                          on each class separately. This is where the refuted
                          bias in prompts/baseline_v1.txt shows up.
    the error pool        how many entailed claims the cloud calls refuted, and
                          whether a local model can identify any of them
    per-subset McNemar    a paired test per subset for any two runs, because
                          the all-subset number hid the FDV-IE effect on 11 Aug
    the routing gate      run the 3B and 7B on every claim, keep the shared
                          verdict when they agree, escalate when they differ
    self-disagreement     whether a model contradicting itself predicts error

Scoring is strict throughout: an unparseable response has extracted_label None,
which never equals a bool, so it counts as wrong. FINDVER-compatible scoring is
deliberately absent — it injects a coin flip, and every comparison here is
between two of our own runs, where strict is the only scoring that makes a
difference mean something (architecture plan §9).

Usage:
    python3 test_scripts/analyse_routing.py
    python3 test_scripts/analyse_routing.py --local 3b --cloud flash
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_condition1 import load_run, two_sided_binomial

# Short names, because these appear in every table below. Only n=700 runs are
# listed: n=102 accuracy is known to be inflated by an easy draw (§2.3.1) and
# must not be mixed into a routing table.
RUNS = {
    "3b":    "condition1_3b_full700",
    "7b":    "condition1_7b_full700",
    "flash": "condition2_deepseek_flash_full700",
    "pro":   "condition2_deepseek_pro_full700",
    "gold":  "gold_alone_3b_full700",
    "pad":   "gold_padded_3b_full700",
    # prompt v2 runs, added 12 Aug. The local arm stays on v1 because v2 did not
    # help the 3B (p = 0.378), so these exist to price a v2 cloud arm under the
    # gate, not to replace the local baselines.
    "3bv2":    "condition1_3b_v2_full700",
    "flashv2": "condition2_flash_v2_full700",
}

SUBSETS = ("ie", "knowledge", "numeric")


def correct(record):
    """Strict scoring. extracted_label None is unparseable and never matches."""
    return record["extracted_label"] == record["gold_label"]


def accuracy(run, ids):
    return sum(correct(run[i]) for i in ids) / len(ids) if ids else 0.0


def mcnemar(run_a, run_b, ids):
    """(a_only_right, b_only_right, p) for two runs over the same claims."""
    a = sum(1 for i in ids if correct(run_a[i]) and not correct(run_b[i]))
    b = sum(1 for i in ids if correct(run_b[i]) and not correct(run_a[i]))
    return a, b, two_sided_binomial(min(a, b), a + b)


# ------------------------------------------------------------------ sections

def print_bias(runs, ids, gold):
    """The measurement that located the refuted bias in the prompt.

    A model can score well overall while being badly skewed, so the headline
    accuracy hides this completely. The column that matters is 'says entailed':
    gold is 50%, and both cloud models sit near 30%.
    """
    entailed = [i for i in ids if gold[i] is True]
    refuted = [i for i in ids if gold[i] is False]

    print("\nLABEL BIAS  (gold is 50% entailed)")
    print(f"  {'run':8}{'says entailed':>15}{'acc entailed':>15}{'acc refuted':>14}")
    for name, run in runs.items():
        says = sum(1 for i in ids if run[i]["extracted_label"] is True)
        print(f"  {name:8}{says:>7} {says/len(ids):5.0%}"
              f"{accuracy(run, entailed):>15.1%}{accuracy(run, refuted):>14.1%}")


def print_error_pool(runs, ids, gold, cloud_name):
    """Entailed claims the cloud calls refuted, and whether anything spots them.

    This is the largest single error pool in the project. A helper is only
    useful here if its precision beats the base rate, which is how often a
    cloud 'refuted' is wrong in the first place.
    """
    cloud = runs[cloud_name]
    said_refuted = [i for i in ids if cloud[i]["extracted_label"] is False]
    wrong = [i for i in said_refuted if gold[i] is True]
    base = len(wrong) / len(said_refuted)

    print(f"\nTHE CLOUD'S REFUTED ERROR POOL  ({cloud_name})")
    print(f"  says refuted on {len(said_refuted)}, wrong on {len(wrong)} "
          f"({base:.0%}) = {len(wrong)/len(ids):.1%} of the benchmark")
    print(f"  by subset: {dict(Counter(runs['3b'][i]['subset'] for i in wrong))}")
    for helper in ("3b", "7b"):
        flagged = [i for i in said_refuted if runs[helper][i]["extracted_label"] is True]
        if not flagged:
            continue
        precision = sum(1 for i in flagged if gold[i] is True) / len(flagged)
        print(f"    {helper} says entailed on {len(flagged):3} of them, right {precision:5.1%}"
              f"   (base rate {base:.1%}, so a lift of {precision-base:+.1%})")


def print_subset_pairs(runs, ids, subset_of, pairs):
    """Paired McNemar per subset.

    Added because on 11 August the all-subset comparison of condition 1 against
    gold-alone read p = 0.116, a tie, while FDV-IE alone was +10.4 points at
    p = 0.004. Averaging three subsets whose effects run in opposite directions
    hides the result.
    """
    print("\nPER-SUBSET PAIRED COMPARISONS")
    for a_name, b_name in pairs:
        a, b = runs[a_name], runs[b_name]
        print(f"\n  {a_name} vs {b_name}")
        print(f"    {'subset':12}{a_name+' only':>12}{b_name+' only':>12}{'net':>6}{'p':>8}")
        for subset in SUBSETS + ("ALL",):
            sel = ids if subset == "ALL" else [i for i in ids if subset_of[i] == subset]
            x, y, p = mcnemar(a, b, sel)
            print(f"    {subset:12}{x:>12}{y:>12}{y-x:>+6}{p:>8.3f}")


def print_gate(runs, ids, gold, subset_of, local_a, local_b, cloud_name):
    """The routing rule: two local models vote, disagreement escalates.

    The second local model is not answering the question. It is a confidence
    signal: where the two agree, the stronger one is markedly more accurate
    than where they differ, and that gap is what makes the gate work.
    """
    a, b, cloud = runs[local_a], runs[local_b], runs[cloud_name]
    agree = [i for i in ids if a[i]["extracted_label"] == b[i]["extracted_label"]]
    differ = [i for i in ids if i not in set(agree)]

    routed = {i: (b[i]["extracted_label"] if i in set(agree)
                  else cloud[i]["extracted_label"]) for i in ids}
    hits = sum(routed[i] == gold[i] for i in ids)

    only_cloud = sum(1 for i in ids if correct(cloud[i]) and routed[i] != gold[i])
    only_routed = sum(1 for i in ids if routed[i] == gold[i] and not correct(cloud[i]))
    p = two_sided_binomial(min(only_cloud, only_routed), only_cloud + only_routed)

    print(f"\nROUTING GATE  ({local_a}/{local_b} agree -> keep {local_b}, "
          f"else escalate to {cloud_name})")
    print(f"  the gate: agree n={len(agree)} {local_b} acc {accuracy(b, agree):.1%}"
          f"  |  differ n={len(differ)} {local_b} acc {accuracy(b, differ):.1%}")
    print(f"  routed            {hits}/{len(ids)} = {hits/len(ids):.1%}"
          f"   cloud calls {len(differ)}/{len(ids)} = {len(differ)/len(ids):.0%}")
    print(f"  {cloud_name} alone       "
          f"{sum(correct(cloud[i]) for i in ids)}/{len(ids)} = {accuracy(cloud, ids):.1%}"
          f"   cloud calls 100%")
    print(f"  vs {cloud_name}: {cloud_name}-only-right {only_cloud}, "
          f"routed-only-right {only_routed}, p = {p:.3f}"
          f"   {'TIE' if p >= 0.05 else 'SIGNIFICANT'}")
    print(f"    {'subset':12}{'routed':>9}{cloud_name:>9}")
    for subset in SUBSETS:
        sel = [i for i in ids if subset_of[i] == subset]
        r = sum(routed[i] == gold[i] for i in sel) / len(sel)
        print(f"    {subset:12}{r:>9.1%}{accuracy(cloud, sel):>9.1%}")


def print_self_disagreement(runs, ids, names):
    """Does a model contradicting itself predict that it is wrong?

    CONTAMINATED, and the warning is printed rather than buried in a comment.
    The three 3B runs available differ in retrieval, and two of them use gold
    evidence, so this mixes genuine sampling noise with a prompt change. It
    shows the mechanism exists. It does not show a deployable version works,
    which needs one model sampled repeatedly at temperature > 0.
    """
    print("\nSELF-DISAGREEMENT AS A CONFIDENCE SIGNAL")
    print("  *** CONTAMINATED: these runs differ in retrieval and two use gold")
    print("  *** evidence. Mechanism only. Do not cite as a result. ***")
    votes = {i: [runs[n][i]["extracted_label"] for n in names] for i in ids}
    unanimous = [i for i in ids if len(set(map(str, votes[i]))) == 1]
    split = [i for i in ids if len(set(map(str, votes[i]))) > 1]
    base = runs[names[0]]
    print(f"  runs compared: {', '.join(names)}")
    print(f"    unanimous  n={len(unanimous):3}  {names[0]} acc {accuracy(base, unanimous):6.1%}")
    print(f"    split      n={len(split):3}  {names[0]} acc {accuracy(base, split):6.1%}")


def main():
    args = sys.argv[1:]
    local_a = args[args.index("--local") + 1] if "--local" in args else "3b"
    cloud = args[args.index("--cloud") + 1] if "--cloud" in args else "flash"

    runs = {}
    for short, directory in RUNS.items():
        try:
            runs[short] = load_run(directory)
        except SystemExit:
            print(f"skipping {short}: results/{directory} not found")

    ids = sorted(set.intersection(*(set(r) for r in runs.values())))
    gold = {i: runs["3b"][i]["gold_label"] for i in ids}
    subset_of = {i: runs["3b"][i]["subset"] for i in ids}

    print("=" * 78)
    print(f"ROUTING AND BIAS ANALYSIS   n={len(ids)} claims shared by all runs")
    print("strict scoring: an unparseable response counts as wrong")
    print("=" * 78)
    print("\nBASELINES")
    for name, run in runs.items():
        print(f"  {name:8}{accuracy(run, ids):>8.1%}")

    print_bias(runs, ids, gold)
    print_error_pool(runs, ids, gold, cloud)
    print_subset_pairs(runs, ids, subset_of,
                       [("3b", "pad"), ("pad", "gold"), ("3b", "gold")])
    print_gate(runs, ids, gold, subset_of, local_a, "7b", cloud)
    print_self_disagreement(runs, ids, ["3b", "pad", "gold"])
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
