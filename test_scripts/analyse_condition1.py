"""Regenerate every accuracy table in the project from the per-claim result files.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. This script is that script for sections 2.3, 2.5 and
2.6, which were all first produced by throwaway code.

It takes result directory names and prints three things:

    the metric table       one column per run, the headline numbers
    the per-subset table   strict accuracy only, n=34 per cell at 102 claims
    the paired table       for every pair of runs, how often they agree, who is
                           right when they do not, and whether that split is
                           distinguishable from a coin flip

Two scorings are reported, and the difference between them matters. **Strict**
counts an unparseable response as wrong. **FINDVER-compatible** replaces it with
a coin flip, which is what the official evaluation does, so it is the only
number that may sit beside a published figure. The gap between the two is how
much of a score is imputation rather than reasoning.

The coin flip is seeded and walks the claims in sorted id order, so this script
returns the same number every time it runs. The official evaluation does not
seed it and does not.

Usage:
    python3 test_scripts/analyse_condition1.py                       the default set
    python3 test_scripts/analyse_condition1.py condition1_3b_k10 condition1_3b_k20
"""

import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "results"

DEFAULT_RUNS = [
    "condition1_3b_k10",
    "condition1_3b_k20",
    "condition1_qwen25_3b_k10",
    "condition2_deepseek_pro",
    "condition2_deepseek_flash",
]

# USD per million tokens, (input cache-miss, output). Published 8 August 2026;
# DeepSeek's pricing page warns of a significant rise, so this needs re-checking
# before any cost figure goes into the paper.
PRICING = {
    "deepseek-v4-pro": (0.435, 0.87),
    "deepseek-v4-flash": (0.14, 0.28),
}

COIN_SEED = 0


def load_run(name):
    """Every result file in one directory, keyed by example id."""
    directory = RESULTS_ROOT / name
    if not directory.is_dir():
        raise SystemExit(f"no such results directory: {directory}")

    records = {}
    for path in sorted(directory.glob("*.json")):
        record = json.loads(path.read_text())
        records[record["example_id"]] = record

    if not records:
        raise SystemExit(f"no result files in {directory}")
    return records


def score(records):
    """Every headline metric for one run, as a plain dict."""
    ids = sorted(records)
    n = len(ids)

    # strict: an unparseable response is wrong, never a coerced default.
    strict = sum(records[i]["extracted_label"] == records[i]["gold_label"] for i in ids)

    # FINDVER-compatible: unparseable becomes a coin flip, which is what
    # FinDVer/evaluation.py does. Seeded here so the number is stable.
    rng = random.Random(COIN_SEED)
    compatible = 0
    for i in ids:
        predicted = records[i]["extracted_label"]
        if predicted is None:
            predicted = rng.choice([True, False])
        compatible += predicted == records[i]["gold_label"]

    def total(field):
        return sum(records[i].get(field) or 0 for i in ids)

    trimmed = sum(records[i].get("chunks_kept") != records[i].get("chunks_requested")
                  for i in ids if records[i].get("chunks_requested") is not None)

    prompt_tokens = total("prompt_eval_count")
    output_tokens = total("eval_count")

    model = records[ids[0]]["config"]["model"]
    cost = None
    if model in PRICING:
        rate_in, rate_out = PRICING[model]
        cost = prompt_tokens / 1e6 * rate_in + output_tokens / 1e6 * rate_out

    return {
        "n": n,
        "ok": sum(records[i]["status"] == "ok" for i in ids),
        "failed": sum(records[i]["status"] != "ok" for i in ids),
        "model": model,
        "strict": strict / n,
        "compatible": compatible / n,
        "unparseable": sum(records[i]["extracted_label"] is None for i in ids) / n,
        "evidence": sum(bool(records[i]["evidence_present"]) for i in ids) / n,
        "predicted_true": sum(records[i]["extracted_label"] is True for i in ids),
        "gold_true": sum(records[i]["gold_label"] for i in ids),
        "prompt_mean": prompt_tokens / n,
        "output_mean": output_tokens / n,
        "thinking_mean": sum(len(records[i].get("thinking") or "") for i in ids) / n,
        "truncated": sum(records[i]["done_reason"] == "length" for i in ids),
        "overflow": sum(bool(records[i]["context_overflow"]) for i in ids),
        "trimmed": trimmed,
        "minutes": total("elapsed_seconds") / 60,
        "per_claim": total("elapsed_seconds") / n,
        "sources": Counter(records[i]["extraction_source"] for i in ids),
        "fingerprints": {records[i].get("system_fingerprint") for i in ids},
        "served": {records[i].get("served_model") for i in ids},
        "cost": cost,
    }


def two_sided_binomial(hits, trials):
    """Exact two-sided p for `hits` successes in `trials` fair coin flips.

    This is McNemar's test on the disagreements between two runs. It answers the
    only question that matters when two accuracy figures differ: could a split
    this lopsided happen by chance? Below about 25 disagreements almost nothing
    is significant, which is why several results in this project are recorded as
    ties despite having a visible gap.
    """
    if trials == 0:
        return 1.0
    observed = math.comb(trials, hits) * 0.5 ** trials
    return min(1.0, sum(math.comb(trials, k) * 0.5 ** trials
                        for k in range(trials + 1)
                        if math.comb(trials, k) * 0.5 ** trials <= observed * 1.0000001))


def print_metrics(names, scores):
    width = max(14, max(len(name) for name in names) + 1)

    def row(label, fmt, key=None, get=None):
        cells = "".join(format(fmt(get(scores[nm]) if get else scores[nm][key]), f">{width}")
                        for nm in names)
        print(f"{label:<26}{cells}")

    print("\n" + "=" * (26 + width * len(names)))
    print(f"{'':<26}" + "".join(format(nm, f'>{width}') for nm in names))
    print("=" * (26 + width * len(names)))

    row("model", str, "model")
    row("n", str, "n")
    row("ok / failed", str, get=lambda s: f"{s['ok']}/{s['failed']}")
    print("-" * (26 + width * len(names)))
    row("strict accuracy", lambda v: f"{v:.1%}", "strict")
    row("FINDVER-compatible", lambda v: f"{v:.1%}", "compatible")
    row("unparseable", lambda v: f"{v:.1%}", "unparseable")
    row("  of which truncated", str, "truncated")
    print("-" * (26 + width * len(names)))
    row("evidence_present", lambda v: f"{v:.1%}", "evidence")
    row("predicted True", str, get=lambda s: f"{s['predicted_true']}/{s['n']}")
    row("gold True", str, get=lambda s: f"{s['gold_true']}/{s['n']}")
    print("-" * (26 + width * len(names)))
    row("prompt tokens, mean", lambda v: f"{v:,.0f}", "prompt_mean")
    row("output tokens, mean", lambda v: f"{v:,.0f}", "output_mean")
    row("thinking chars, mean", lambda v: f"{v:,.0f}", "thinking_mean")
    row("context overflow", str, "overflow")
    row("trimmer fired", str, "trimmed")
    print("-" * (26 + width * len(names)))
    row("wall clock, min", lambda v: f"{v:.1f}", "minutes")
    row("seconds per claim", lambda v: f"{v:.1f}", "per_claim")
    row("cost, USD", lambda v: "-" if v is None else f"${v:.3f}", "cost")

    print("\nextraction sources")
    for name in names:
        print(f"  {name:<26} {dict(scores[name]['sources'])}")

    served = {nm: scores[nm]["served"] for nm in names if scores[nm]["served"] != {None}}
    if served:
        print("\nserved_model / system_fingerprint  (one value each means no model roll mid-run)")
        for name, value in served.items():
            print(f"  {name:<26} {value}  {scores[name]['fingerprints']}")


def print_subsets(names, runs):
    print("\nstrict accuracy by subset")
    subsets = sorted({r["subset"] for records in runs.values() for r in records.values()})
    width = max(14, max(len(name) for name in names) + 1)
    print(f"{'':<26}" + "".join(format(nm, f'>{width}') for nm in names))

    for subset in subsets:
        cells = ""
        for name in names:
            records = runs[name]
            ids = [i for i in sorted(records) if records[i]["subset"] == subset]
            hit = sum(records[i]["extracted_label"] == records[i]["gold_label"] for i in ids)
            cells += format(f"{hit/len(ids):.1%} ({hit}/{len(ids)})", f">{width}")
        print(f"{subset:<26}{cells}")


def print_pairs(names, runs):
    print("\npaired comparisons, on the claims both runs share")
    print(f"{'pair':<46}{'agree':>14}{'A right':>9}{'B right':>9}{'p':>9}")

    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            name_a, name_b = names[a], names[b]
            run_a, run_b = runs[name_a], runs[name_b]
            ids = sorted(set(run_a) & set(run_b))
            if not ids:
                continue

            agree = sum(run_a[i]["extracted_label"] == run_b[i]["extracted_label"] for i in ids)
            a_right = sum(run_a[i]["extracted_label"] == run_a[i]["gold_label"]
                          and run_b[i]["extracted_label"] != run_b[i]["gold_label"] for i in ids)
            b_right = sum(run_b[i]["extracted_label"] == run_b[i]["gold_label"]
                          and run_a[i]["extracted_label"] != run_a[i]["gold_label"] for i in ids)

            p = two_sided_binomial(max(a_right, b_right), a_right + b_right)
            verdict = "" if p < 0.05 else "  tie"
            pair = f"{name_a} vs {name_b}"
            print(f"{pair:<46}{f'{agree}/{len(ids)}':>14}{a_right:>9}{b_right:>9}"
                  f"{p:>9.3f}{verdict}")

    print("\np is an exact two-sided McNemar test on the disagreements. p >= 0.05 means the")
    print("split is not distinguishable from a coin flip, so the two runs must be reported")
    print("as tied however far apart their accuracy columns look.")


def main():
    names = sys.argv[1:] or DEFAULT_RUNS
    names = [n for n in names if (RESULTS_ROOT / n).is_dir()]
    if not names:
        raise SystemExit("no result directories found")

    runs = {name: load_run(name) for name in names}
    scores = {name: score(runs[name]) for name in names}

    print_metrics(names, scores)
    print_subsets(names, runs)
    print_pairs(names, runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
