"""Everything run 1 measured, from one job, on the held-out split.

Run 1 is `configs/pipeline_test1700.json`: the routed 3B -> 7B -> flash pipeline
over all 1,700 claims of `test.json`. Because `skip_local_when_escalating` is
false, every claim carries a 3B verdict and a 7B verdict as well as the routed
one, so a single job yields condition 1 at 3B, condition 1 at 7B and condition 4
on the same claims. Condition 2 was run separately at the same n on the same
split, so the cloud-alone arm is paired against these claims too.

Scoring is strict throughout, matching `analyse_routing.py`: an unparseable
response has extracted_label None, never equals a bool, and counts as wrong.

Everything here reads stored result files. No model calls, no GPU, no quota.

Usage:
    python3 test_scripts/analyse_run1.py
"""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_condition1 import load_run, two_sided_binomial

RUN = "condition4_pipeline_test1700"
CLOUD_ALONE = "condition2_flash_v2_test1700"
SUBSETS = ("ie", "numeric", "knowledge")

# deepseek-v4-flash, USD per 1M tokens. USD is the figure to quote: it comes
# from our own recorded token counts, so it is exact for our usage and is not
# affected by anyone else spending on the key (19 Aug cost-method inversion).
RATE_IN, RATE_OUT = 0.14, 0.28


def wilson(hits, n, z=1.96):
    """95% interval for a proportion. Wilson rather than normal-approximation,
    because it stays inside [0,1] and behaves at the small per-cell counts
    below."""
    if n == 0:
        return 0.0, 0.0
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def arms(record):
    """The four verdicts available for one claim. None means not produced."""
    return {"3B alone": record.get("verdict_local_a"),
            "7B alone": record.get("verdict_local_b"),
            "cloud (when called)": record.get("verdict_cloud"),
            "routed": record.get("extracted_label")}


def acc(pairs):
    """pairs is a list of (predicted, gold). Strict."""
    hits = sum(p == g for p, g in pairs)
    return hits, len(pairs), (hits / len(pairs) if pairs else 0.0)


def line(label, hits, n, extra=""):
    lo, hi = wilson(hits, n)
    pct = hits / n if n else 0.0
    return f"  {label:22}{pct:>7.1%}  ({hits:>4}/{n:<4})  95% CI {lo:>5.1%} to {hi:>5.1%}  {extra}"


def mcnemar(run_a, run_b, ids, name_a, name_b):
    """Paired test on the claims where exactly one of the two is right."""
    a_only = sum(1 for i in ids
                 if (run_a[i]["extracted_label"] == run_a[i]["gold_label"])
                 and not (run_b[i]["extracted_label"] == run_b[i]["gold_label"]))
    b_only = sum(1 for i in ids
                 if (run_b[i]["extracted_label"] == run_b[i]["gold_label"])
                 and not (run_a[i]["extracted_label"] == run_a[i]["gold_label"]))
    n = a_only + b_only
    p = two_sided_binomial(min(a_only, b_only), n)
    verdict = "SIGNIFICANT" if p < 0.05 else "tie"
    print(f"  {name_a} right where {name_b} wrong: {a_only}")
    print(f"  {name_b} right where {name_a} wrong: {b_only}")
    print(f"  {n} disagreements, p = {p:.4f}   {verdict}")
    return p


def main():
    run = load_run(RUN)
    ids = sorted(run)
    gold = {i: run[i]["gold_label"] for i in ids}

    print("=" * 78)
    print(f"RUN 1: {RUN}, split test.json")
    print("=" * 78)

    # ---------- integrity, before any accuracy number is believed ----------
    print("\nINTEGRITY")
    failed = [i for i in ids if run[i]["status"] != "ok"]
    print(f"  claims                {len(ids)}")
    print(f"  status ok             {len(ids) - len(failed)}")
    print(f"  failed                {len(failed)}")
    print(f"  unparseable (routed)  {sum(run[i]['extracted_label'] is None for i in ids)}")
    print(f"  context overflow      {sum(bool(run[i].get('context_overflow')) for i in ids)}")
    print(f"  truncated by length   {sum(run[i].get('done_reason') == 'length' for i in ids)}")
    print(f"  evidence present      {sum(bool(run[i].get('evidence_present')) for i in ids)}"
          f" = {sum(bool(run[i].get('evidence_present')) for i in ids) / len(ids):.1%}")
    print(f"  locals skipped        {sum(bool(run[i].get('locals_skipped')) for i in ids)}")
    print("  extraction source     " + ", ".join(
        f"{k}={v}" for k, v in Counter(run[i]["extraction_source"] for i in ids).most_common()))

    # ---------- headline ----------
    print("\n\nHEADLINE, strict scoring, all 1,700 held-out claims")
    for name in ("3B alone", "7B alone", "routed"):
        pairs = [(arms(run[i])[name], gold[i]) for i in ids]
        hits, n, _ = acc(pairs)
        print(line(name, hits, n))
    called = [i for i in ids if run[i].get("cloud_called")]
    hits, n, _ = acc([(run[i]["verdict_cloud"], gold[i]) for i in called])
    print(line("cloud, where called", hits, n, "subset of claims, not comparable"))

    try:
        cloud = load_run(CLOUD_ALONE)
    except SystemExit:
        cloud = None
    if cloud:
        shared = [i for i in ids if i in cloud]
        hits, n, _ = acc([(cloud[i]["extracted_label"], cloud[i]["gold_label"]) for i in shared])
        print(line("cloud alone (cond 2)", hits, n, "same claims, separate run"))

    # ---------- the comparison the paper turns on ----------
    if cloud:
        print("\n\nROUTED vs CLOUD ALONE, paired McNemar on the same 1,700 claims")
        mcnemar(run, cloud, shared, "routed", "cloud ")
        print("\n  per subset")
        for s in SUBSETS:
            sub = [i for i in shared if run[i]["subset"] == s]
            print(f"\n  --- {s} (n={len(sub)}) ---")
            mcnemar(run, cloud, sub, "routed", "cloud ")

    # ---------- per subset ----------
    print("\n\nPER SUBSET")
    print(f"  {'':22}" + "".join(f"{s:>16}" for s in SUBSETS))
    for name in ("3B alone", "7B alone", "routed"):
        cells = []
        for s in SUBSETS:
            sub = [i for i in ids if run[i]["subset"] == s]
            hits, n, a = acc([(arms(run[i])[name], gold[i]) for i in sub])
            cells.append(f"{a:.1%} ({hits}/{n})")
        print(f"  {name:22}" + "".join(f"{c:>16}" for c in cells))
    if cloud:
        cells = []
        for s in SUBSETS:
            sub = [i for i in shared if run[i]["subset"] == s]
            hits, n, a = acc([(cloud[i]["extracted_label"], cloud[i]["gold_label"]) for i in sub])
            cells.append(f"{a:.1%} ({hits}/{n})")
        print(f"  {'cloud alone':22}" + "".join(f"{c:>16}" for c in cells))

    # ---------- per label: the refuted bias ----------
    print("\n\nPER GOLD LABEL, where the prompt's refuted bias shows")
    print(f"  {'':22}{'entailed':>18}{'refuted':>18}{'says entailed':>16}")
    for name in ("3B alone", "7B alone", "routed"):
        cells = []
        for want in (True, False):
            sub = [i for i in ids if gold[i] is want]
            hits, n, a = acc([(arms(run[i])[name], gold[i]) for i in sub])
            cells.append(f"{a:.1%} ({hits}/{n})")
        says = sum(arms(run[i])[name] is True for i in ids) / len(ids)
        print(f"  {name:22}" + "".join(f"{c:>18}" for c in cells) + f"{says:>15.1%}")
    if cloud:
        cells = []
        for want in (True, False):
            sub = [i for i in shared if cloud[i]["gold_label"] is want]
            hits, n, a = acc([(cloud[i]["extracted_label"], cloud[i]["gold_label"]) for i in sub])
            cells.append(f"{a:.1%} ({hits}/{n})")
        says = sum(cloud[i]["extracted_label"] is True for i in shared) / len(shared)
        print(f"  {'cloud alone':22}" + "".join(f"{c:>18}" for c in cells) + f"{says:>15.1%}")
    print(f"  {'GOLD':22}" + "".join(
        f"{sum(1 for i in ids if gold[i] is w) / len(ids):>17.1%}" for w in (True, False)))

    # ---------- routing behaviour ----------
    print("\n\nROUTING BEHAVIOUR")
    print(f"  cloud called          {len(called)} = {len(called) / len(ids):.1%}")
    print("  escalation reason     " + ", ".join(
        f"{k}={v}" for k, v in Counter(run[i].get("escalation_reason") for i in ids).most_common()))
    print("  final source          " + ", ".join(
        f"{k}={v}" for k, v in Counter(run[i].get("final_source") for i in ids).most_common()))

    agree = [i for i in ids if run[i]["verdict_local_a"] == run[i]["verdict_local_b"]]
    disagree = [i for i in ids if i not in set(agree)]
    print(f"\n  locals agree          {len(agree)} = {len(agree) / len(ids):.1%}")
    hits, n, _ = acc([(run[i]["verdict_local_a"], gold[i]) for i in agree])
    print(line("  when they agree", hits, n, "kept without a cloud call"))
    hits, n, _ = acc([(run[i]["extracted_label"], gold[i]) for i in disagree])
    print(line("  when they differ", hits, n, "routed answer there"))

    print("\n  accuracy split by whether the cloud was called")
    not_called = [i for i in ids if not run[i].get("cloud_called")]
    for label, group in (("cloud called", called), ("kept local", not_called)):
        hits, n, _ = acc([(run[i]["extracted_label"], gold[i]) for i in group])
        print(line("  " + label, hits, n))

    # ---------- ceiling ----------
    print("\n\nCEILING: what perfect selection among the verdicts we already have would score")
    oracle = 0
    for i in ids:
        available = [v for v in (run[i]["verdict_local_a"], run[i]["verdict_local_b"],
                                 run[i].get("verdict_cloud")) if v is not None]
        oracle += any(v == gold[i] for v in available)
    print(line("oracle over 3B/7B/cloud", oracle, len(ids), "not implementable, an upper bound"))
    both_local = sum(any(v == gold[i] for v in (run[i]["verdict_local_a"],
                                                run[i]["verdict_local_b"]) if v is not None)
                     for i in ids)
    print(line("oracle over 3B/7B only", both_local, len(ids), "no cloud at all"))

    # ---------- cost ----------
    print("\n\nCOST, from our own recorded token counts")
    tin = tout = 0
    for i in called:
        stage = (run[i].get("stages") or {}).get("cloud") or {}
        tin += stage.get("prompt_eval_count") or 0
        tout += stage.get("eval_count") or 0
    usd = tin / 1e6 * RATE_IN + tout / 1e6 * RATE_OUT
    print(f"  cloud calls           {len(called)}")
    print(f"  input tokens          {tin:,}")
    print(f"  output tokens         {tout:,}")
    print(f"  USD at flash list     ${usd:.3f}")
    if cloud:
        ctin = sum(cloud[i].get("prompt_eval_count") or 0 for i in shared)
        ctout = sum(cloud[i].get("eval_count") or 0 for i in shared)
        cusd = ctin / 1e6 * RATE_IN + ctout / 1e6 * RATE_OUT
        print(f"  cloud alone, same n   ${cusd:.3f}")
        if cusd:
            print(f"  routed / cloud alone  {usd / cusd:.1%} of the cost")

    wall = sum(run[i].get("elapsed_seconds") or 0 for i in ids)
    per = sorted(run[i].get("elapsed_seconds") or 0 for i in ids)
    print(f"\n  wall clock, summed    {wall / 3600:.2f} h")
    print(f"  median per claim      {per[len(per) // 2]:.1f} s   "
          f"(median, because some claims ran under GPU contention)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
