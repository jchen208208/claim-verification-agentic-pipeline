"""Validate src/evidence_asserter.py against all 700 testmini claims, offline.

Nothing here touches a model, the cloud, or the real prompt template. The
evidence blocks are fabricated in memory and discarded. No files are written.
Delete this script once the asserter is trusted.

Three controls, each building a fake evidence_block and asking what
assert_evidence says about it:

    gold   the gold elements' text, joined      -> must be True
    decoy  the same NUMBER of non-gold elements
           drawn from the SAME report, seeded   -> must be False
    hard   the non-gold elements of that report
           sharing the most tokens with the
           claim, i.e. what a lexical retriever
           would wrongly return                 -> must be False
    claim  the claim statement alone            -> must be False

gold is the positive control: does the check work when the evidence really is
there? decoy is the false-positive rate: do witnesses turn up in text that is
not the gold element? claim is the specific bug found during design, where a
witness copied into the claim is found in the prompt whether or not retrieval
worked, and the fix was scoping the check to the evidence block.

Also reported: the share of gold elements whose top witness has report count 1,
which is the case that makes a hit conclusive, and the same figures at several
MIN_TOKEN_LEN values so that constant is measured rather than guessed.

Usage:
    python3 scripts/validate_evidence_asserter.py
"""

import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import evidence_asserter as ea
from src.evidence_asserter import (assert_evidence, check_overflow,
                                   count_report_tokens, pick_tokens, tokenize)
from src.loader import load_claims

REPORT_DIR = REPO_ROOT / "FinDVer" / "financial_reports"
SEED = 0
THRESHOLDS = [2, 3, 4, 5]


def load_report(filename, cache):
    """Parsed filing, cached. 700 claims cite only ~255 distinct reports."""
    if filename not in cache:
        with open(REPORT_DIR / filename) as f:
            cache[filename] = json.load(f)
    return cache[filename]


def build_block(claim, report, mode, rng):
    """Fabricate an evidence_block for one control."""
    elements = report["context"]
    gold = list(claim.relevant_context)

    if mode == "gold":
        chosen = gold
    elif mode == "decoy":
        pool = [i for i in range(len(elements)) if i not in set(gold)]
        chosen = rng.sample(pool, min(len(gold), len(pool)))
    elif mode == "hard":
        # the closest non-gold elements by token overlap with the claim, which
        # is roughly what a lexical retriever returns when it misses
        wanted = set(tokenize(claim.statement))
        pool = [i for i in range(len(elements)) if i not in set(gold)]
        pool.sort(key=lambda i: -len(wanted & set(tokenize(elements[i]["context"]))))
        chosen = pool[:len(gold)]
    elif mode == "claim":
        return claim.statement
    else:
        raise ValueError(mode)

    return "\n\n".join(elements[i]["context"] for i in chosen)


def run_controls(claims, cache):
    """Run all three controls over every claim. Returns per-mode tallies."""
    results = {}
    for mode in ("gold", "decoy", "hard", "claim"):
        rng = random.Random(SEED)
        true_count = 0
        partial = 0          # some witnesses matched but not all
        offenders = []
        for claim in claims:
            report = load_report(claim.report, cache)
            block = build_block(claim, report, mode, rng)
            present, found = assert_evidence(block, claim, report)
            if present:
                true_count += 1
                offenders.append(claim.example_id)
            elif any(m > 0 for m, _ in found.values()):
                partial += 1
        results[mode] = (true_count, partial, offenders)
    return results


def witness_quality(claims, cache, min_len):
    """Share of gold elements whose witnesses are conclusive at a threshold."""
    ea.MIN_TOKEN_LEN = min_len
    counts_cache = {}
    total = top_unique = all_unique = 0
    for claim in claims:
        report = load_report(claim.report, cache)
        if claim.report not in counts_cache:
            counts_cache[claim.report] = count_report_tokens(report)
        counts = counts_cache[claim.report]
        for i in claim.relevant_context:
            witnesses = pick_tokens(report["context"][i]["context"], counts)
            total += 1
            if witnesses and witnesses[0][1] == 1:
                top_unique += 1
            if witnesses and all(c == 1 for _, c in witnesses):
                all_unique += 1
    ea.MIN_TOKEN_LEN = 3
    return total, top_unique, all_unique


def main():
    claims = load_claims()
    cache = {}
    print(f"claims: {len(claims)}")

    results = run_controls(claims, cache)
    n = len(claims)

    print("\ncontrol   evidence_present=True   partial   expected")
    for mode, expected in (("gold", "700/700"), ("decoy", "0/700"),
                           ("hard", "0/700"), ("claim", "0/700")):
        true_count, partial, _ = results[mode]
        print(f"  {mode:<7} {true_count:>10}/{n} {partial:>13} {expected:>11}")

    for mode in ("decoy", "hard", "claim"):
        offenders = results[mode][2]
        if offenders:
            print(f"\n  {mode} false positives ({len(offenders)}): {offenders[:10]}")

    print("\nwitness quality by MIN_TOKEN_LEN")
    print("  len   elements   top witness count==1   all 3 count==1")
    for min_len in THRESHOLDS:
        total, top_unique, all_unique = witness_quality(claims, cache, min_len)
        print(f"  {min_len:>3} {total:>10} {top_unique:>13} ({100*top_unique/total:5.1f}%)"
              f" {all_unique:>10} ({100*all_unique/total:5.1f}%)")

    check_overflow_cases()


def check_overflow_cases():
    """check_overflow is arithmetic, so a handful of cases covers it."""
    cases = [
        ((4500, 2000, 16384), False, "normal run, ~9800 tokens of slack"),
        ((14000, 2384, 16384), True,  "sum exactly at the window"),
        ((15000, 2000, 16384), True,  "sum over the window, eviction likely"),
        ((None, 2000, 16384), None,   "failed call, prompt count missing"),
        ((4500, None, 16384), None,   "failed call, eval count missing"),
    ]
    print("\ncheck_overflow")
    for args, expected, why in cases:
        got = check_overflow(*args)
        flag = "ok " if got is expected else "FAIL"
        print(f"  {flag} {str(args):<24} -> {str(got):<5} {why}")


if __name__ == "__main__":
    main()
