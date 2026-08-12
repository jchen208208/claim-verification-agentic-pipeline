"""Regenerate every cites-missing-information number in paper_numbers.md §2.11.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. The §2.11 numbers were produced by throwaway code typed
into a terminal on 11 August and never saved, so nothing in that section could
be regenerated. This script is that script.

It prints three things, all from stored result files, with no model calls:

    the diagnostic set    the 100 gold-entailed FDV-KNOW claims in
                          gold_alone_3b_full700, split by whether the model got
                          them right, and how often each group declares the
                          information absent. Retrieval is excluded by
                          construction: every gold element was in the prompt, so
                          a response claiming absence is wrong about its own
                          input.
    the model-level table how often each model cites missing information, how
                          often it then refutes, and how often those refutations
                          are wrong, against its base refutation rate.
    --show GROUP          every matched sentence, so the regex can be checked by
                          reading instead of trusted. This is the spot-check.

Usage:
    python3 test_scripts/analyse_missing_info.py
    python3 test_scripts/analyse_missing_info.py --show right
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_condition1 import load_run

DIAGNOSTIC_RUN = "gold_alone_3b_full700"

MODEL_RUNS = {
    "3b":    "condition1_3b_full700",
    "7b":    "condition1_7b_full700",
    "flash": "condition2_deepseek_flash_full700",
    "pro":   "condition2_deepseek_pro_full700",
}

# The phrase family, written out rather than left as "and so on", because the
# original list was lost and the count depends entirely on it.
#
# Every absence word is anchored to the document or to the information. A bare
# "lack" matches the subject matter instead of the model's reasoning: "a lack of
# authorized shares" and "this lack of cash flow generation" are facts stated in
# the filing, not the model reporting missing evidence. Leaving "lack" unanchored
# put 5 false positives into a control group of 51, which turned a 15-fold
# separation into a 4-fold one.
MISSING_INFO_PHRASES = (
    r"do(?:es)? not (?:explicitly )?(?:provide|mention|state|specify|include|contain|indicate|disclose)",
    r"not (?:provided|mentioned|stated|specified|included|disclosed|explicitly stated)",
    r"(?:is|are) no (?:information|mention|data|evidence|reference|indication|details?)",
    r"no (?:information|mention|data|evidence|reference|indication|specific (?:information|details?))",
    r"lack of (?:information|data|detail|disclosure|mention|evidence)",
    r"(?:information|data|evidence|details?) (?:is|are) (?:absent|missing|not available)",
)
CITES_MISSING = re.compile("|".join(MISSING_INFO_PHRASES), re.I)


def cites_missing(record):
    """Does the response claim the document does not contain something."""
    return bool(CITES_MISSING.search(record["response"] or ""))


def diagnostic_groups(run):
    """The two halves of the diagnostic set, keyed by whether the model was right.

    Both are gold-entailed FDV-KNOW claims. 'wrong' uses `is not True` rather
    than `is False` so the one unparseable response counts as wrong, which is
    strict scoring and is where the documented 49 comes from: 48 refuted plus
    knowledge-val-0 unparseable.
    """
    know = [i for i in run if i.startswith("knowledge") and run[i]["gold_label"] is True]
    wrong = sorted(i for i in know if run[i]["extracted_label"] is not True)
    right = sorted(i for i in know if run[i]["extracted_label"] is True)
    return {"wrong": wrong, "right": right}


def print_diagnostic(run, groups):
    print(f"\ndiagnostic set: gold-entailed FDV-KNOW claims in {DIAGNOSTIC_RUN}")
    print("every gold element was in the prompt, so retrieval is excluded\n")
    print(f"  {'group':24s} {'n':>4s} {'says info missing':>18s}")
    for name, label in (("wrong", "entailed, model WRONG"), ("right", "entailed, model RIGHT")):
        ids = groups[name]
        hits = [i for i in ids if cites_missing(run[i])]
        print(f"  {label:24s} {len(ids):4d} {len(hits):9d} {len(hits) / len(ids):8.1%}")


def print_model_table():
    print("\nhow each model uses the phrase, all 700 claims per run\n")
    print(f"  {'model':6s} {'cites missing':>16s} {'then refutes':>16s} {'those wrong':>16s} {'base refute':>12s}")
    for name, directory in MODEL_RUNS.items():
        run = load_run(directory)
        ids = sorted(run)
        cites = [i for i in ids if cites_missing(run[i])]
        refuted = [i for i in cites if run[i]["extracted_label"] is False]
        wrong = [i for i in refuted if run[i]["gold_label"] is not False]

        # base rate: how often this model's refutations are wrong generally, so
        # the column above has something to be compared against
        all_refuted = [i for i in ids if run[i]["extracted_label"] is False]
        all_wrong = [i for i in all_refuted if run[i]["gold_label"] is not False]

        print(f"  {name:6s} {len(cites):8d} {len(cites) / len(ids):7.1%}"
              f" {len(refuted):8d} {len(refuted) / max(len(cites), 1):7.1%}"
              f" {len(wrong):8d} {len(wrong) / max(len(refuted), 1):7.1%}"
              f" {len(all_wrong) / max(len(all_refuted), 1):11.1%}")


def print_matches(run, ids):
    """The spot-check: the matched phrase in context, for reading."""
    for i in ids:
        match = CITES_MISSING.search(run[i]["response"] or "")
        if not match:
            continue
        text = run[i]["response"]
        start, end = max(0, match.start() - 120), min(len(text), match.end() + 120)
        print(f"\n--- {i}   matched {match.group(0)!r}")
        print("   ", " ".join(text[start:end].split()))


def main():
    run = load_run(DIAGNOSTIC_RUN)
    groups = diagnostic_groups(run)

    args = sys.argv[1:]
    if "--show" in args:
        group = args[args.index("--show") + 1]
        print_matches(run, groups[group])
        return

    print_diagnostic(run, groups)
    print_model_table()
    print("\nspot-check a group by reading every match:")
    print("  python3 test_scripts/analyse_missing_info.py --show right")


if __name__ == "__main__":
    main()
