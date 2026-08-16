"""Regenerate every number behind `src/numeric_detector.py`.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script reproduces it. This is that script for the numeric detector.

The detector exists to remove an oracle. `always escalate numeric` used to read
`claim.subset`, an annotation FINDVER ships and no deployed system has, which
made the 79.7% headline oracle-assisted (paper_numbers.md 2.13.3). The detector
decides the same thing from the claim wording alone, with no model call.

It prints four things:

    detection, testmini    precision and recall against the numeric subset,
                           whole detector and one pattern at a time
    detection, test.json   the same on 1,700 claims that were never inspected
                           while the patterns were written. This is the only
                           honest generalisation check available without a run,
                           and it costs nothing because test.json ships subset
                           labels too
    the routed table       accuracy and cloud-call rate for the detector against
                           the oracle label, the plain gate and cloud-alone, all
                           re-derived from stored n=700 result files
    paired tests           McNemar against the oracle label policy and against
                           cloud-alone, because the whole question is whether
                           the detector loses anything by dropping the annotation

Scoring is strict throughout, matching analyse_routing.py: an unparseable
response has extracted_label None, which never equals a bool, so it counts as
wrong. No FINDVER-compatible column, because that injects a coin flip and every
comparison here is between two of our own policies.

Usage:
    python3 test_scripts/measure_numeric_detector.py
    python3 test_scripts/measure_numeric_detector.py --show misses
    python3 test_scripts/measure_numeric_detector.py --show fp
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import re

from analyse_condition1 import load_run, two_sided_binomial
from numeric_detector import _DETECTOR, _PATTERNS, is_numeric_claim

DATA = REPO_ROOT / "FinDVer" / "data"

# Names for the three patterns, in the order src/numeric_detector.py defines
# them. Kept here rather than in src/ so the pipeline module carries no strings
# that exist only for reporting.
PATTERN_NAMES = ("equation tail", "word 'percentage'", "hedged copula")

# The three runs the routed table is built from. All n=700, all on the same
# claims. The local arm is the 7B, matching analyse_routing.py: the gate keeps
# the shared verdict when 3B and 7B agree, so the kept verdict is the 7B's.
LOCAL_A, LOCAL_B, CLOUD = (
    "condition1_3b_full700",
    "condition1_7b_full700",
    "condition2_flash_v2_full700",
)


def load_claims(filename):
    """Statement, subset flag and id for one FINDVER split."""
    path = DATA / filename
    if not path.is_file():
        raise SystemExit(f"no such data file: {path}")
    return [
        (c["example_id"], c["statement"], c["subset"] == "numeric", c["subset"])
        for c in json.loads(path.read_text())
    ]


def detection_table(filename, note):
    """Precision and recall against the numeric subset, whole and per pattern."""
    claims = load_claims(filename)
    total_numeric = sum(1 for _, _, y, _ in claims if y)

    print(f"\nDETECTION on {filename}   n={len(claims)}, numeric={total_numeric} "
          f"({total_numeric / len(claims):.1%})")
    print(f"  {note}")
    print(f"  {'':22}{'flags':>7}{'tp':>6}{'fp':>5}{'prec':>8}{'rec':>8}")

    rows = [("WHOLE DETECTOR", _DETECTOR)]
    rows += [
        (name, re.compile(pattern, re.IGNORECASE))
        for name, pattern in zip(PATTERN_NAMES, _PATTERNS)
    ]

    for name, regex in rows:
        hits = [y for _, statement, y, _ in claims if regex.search(statement)]
        flagged, true_pos = len(hits), sum(hits)
        precision = true_pos / flagged if flagged else 0.0
        recall = true_pos / total_numeric
        marker = "  <--" if name == "WHOLE DETECTOR" else ""
        print(f"  {name:22}{flagged:>7}{true_pos:>6}{flagged - true_pos:>5}"
              f"{precision:>8.3f}{recall:>8.3f}{marker}")

    # Where the false positives land matters: a knowledge claim wrongly sent to
    # the cloud costs a call, and knowledge is the subset the cloud is worst at.
    fp_subsets = {}
    for _, statement, y, subset in claims:
        if not y and _DETECTOR.search(statement):
            fp_subsets[subset] = fp_subsets.get(subset, 0) + 1
    if fp_subsets:
        spread = ", ".join(f"{k} {v}" for k, v in sorted(fp_subsets.items()))
        print(f"  false positives by subset: {spread}")


def routed_table():
    """Accuracy and cloud-call rate for each escalation policy."""
    statements = {
        example_id: statement
        for example_id, statement, _, _ in load_claims("testmini.json")
    }
    local_a, local_b, cloud = (load_run(LOCAL_A), load_run(LOCAL_B), load_run(CLOUD))
    ids = sorted(set(local_a) & set(local_b) & set(cloud))
    gold = {i: local_a[i]["gold_label"] for i in ids}

    def disagree(i):
        return local_a[i]["extracted_label"] != local_b[i]["extracted_label"]

    def run_policy(decide):
        """Verdict per claim under one policy, plus the cloud-call count."""
        verdicts, calls = {}, 0
        for i in ids:
            escalate = decide(i)
            calls += escalate
            source = cloud[i] if escalate else local_b[i]
            verdicts[i] = source["extracted_label"]
        return verdicts, calls / len(ids)

    policies = [
        ("3B alone", lambda i: None, local_a),
        ("7B alone", lambda i: None, local_b),
        ("gate only", disagree, None),
        ("gate + subset LABEL (oracle)",
         lambda i: i.startswith("numeric") or disagree(i), None),
        ("gate + DETECTOR",
         lambda i: is_numeric_claim(statements[i]) or disagree(i), None),
        ("always cloud", lambda i: True, None),
    ]

    print(f"\nROUTED, n={len(ids)}   local {LOCAL_A} + {LOCAL_B}, cloud {CLOUD}")
    print(f"  {'policy':32}{'acc':>7}{'calls':>8}   deployable")

    results = {}
    for name, decide, standalone in policies:
        if standalone is not None:
            verdicts = {i: standalone[i]["extracted_label"] for i in ids}
            call_rate = 0.0
        else:
            verdicts, call_rate = run_policy(decide)
        correct = sum(verdicts[i] == gold[i] for i in ids)
        results[name] = verdicts
        deployable = "NO, reads claim.subset" if "LABEL" in name else "yes"
        print(f"  {name:32}{correct / len(ids):>7.1%}{call_rate:>8.1%}   {deployable}")

    print("\nPAIRED, detector against the two policies it has to match")
    detector = results["gate + DETECTOR"]
    for other_name in ("gate + subset LABEL (oracle)", "always cloud"):
        other = results[other_name]
        ours = sum(detector[i] == gold[i] and other[i] != gold[i] for i in ids)
        theirs = sum(other[i] == gold[i] and detector[i] != gold[i] for i in ids)
        p = two_sided_binomial(ours, ours + theirs)
        if p >= 0.05:
            verdict = "TIE"
        else:
            verdict = "DETECTOR BETTER" if ours > theirs else "DETECTOR WORSE"
        print(f"  vs {other_name:32} {ours:>3} / {theirs:<3}  p = {p:.3f}   {verdict}")


def show_errors(kind):
    """Print the detector's mistakes on both splits, for reading by eye."""
    for filename in ("testmini.json", "test.json"):
        claims = load_claims(filename)
        if kind == "misses":
            bad = [(i, s, sub) for i, s, y, sub in claims
                   if y and not is_numeric_claim(s)]
            heading = "NUMERIC CLAIMS MISSED"
        else:
            bad = [(i, s, sub) for i, s, y, sub in claims
                   if not y and is_numeric_claim(s)]
            heading = "NON-NUMERIC CLAIMS WRONGLY FLAGGED"
        print(f"\n{heading} in {filename}: {len(bad)}")
        for example_id, statement, subset in bad:
            print(f"  [{subset}] {example_id}: {statement[:200]}")


def main():
    if "--show" in sys.argv:
        kind = sys.argv[sys.argv.index("--show") + 1]
        if kind not in ("misses", "fp"):
            raise SystemExit("--show takes 'misses' or 'fp'")
        show_errors(kind)
        return

    detection_table("testmini.json",
                    "the patterns were written against this file")
    detection_table("test.json",
                    "HELD OUT: never inspected while the patterns were written")
    routed_table()

    print("\nThe routed table is testmini only. test.json has no pipeline run "
          "yet,\nso the detector's effect on accuracy there is unmeasured.")


if __name__ == "__main__":
    main()
