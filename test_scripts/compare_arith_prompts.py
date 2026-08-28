"""Did the v1 prompt cause the wrong-operation failure, or did it not?

The first 9 claims of the v1 run showed the model answering a claim asserting
"-9.63%" with `difference`. Two of nine failed that way. The claim that the
PROMPT caused it was a hypothesis, not a measurement: v1's worked example shows
a 25% growth claim and then writes `CLAIMED: 25` with the percent sign removed,
and v1 never tells the model to match the operation to what the claim asserts.

This runs both prompts over the same claims, same model, temperature 0, seed 0,
and reports two numbers per prompt:

    units clash   the model chose a non-percent operation for a claim whose
                  asserted value carries a percent sign. This is the observed
                  failure, measured directly.
    computed ok   the model's own numbers and operation, run through Python,
                  reproduce the benchmark's execution_result. This is the real
                  target: it is what the skill has to get right to be useful.

Uses the local 3B on the GPU box. No cloud calls, no API key, no cost.

Usage:
    python3 test_scripts/compare_arith_prompts.py [n_claims]
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.arithmetic_skill import compute, parse_response

# Defined here rather than imported, so this script runs whether or not the
# units guard has been added to src/arithmetic_skill.py yet.
PERCENT_OPERATIONS = {"percent_change", "percent_of"}
from src.bm25_retriever import retrieve
from src.loader import load_claims
from src.ollama_client import call_ollama
from src.run_loop import build_prompt, load_prompt_template, read_report

SKILL_CONFIG = {
    "model": "qwen2.5-coder:3b",
    "num_ctx": 32768,
    "num_predict": 1000,
    "temperature": 0,
    "seed": 0,
    "ollama_host": "10.0.0.26",
}

MAIN_CONFIG = {"num_ctx": 32768, "num_predict": 2000}


def gold_values(claim):
    result = claim.execution_result
    return [float(v) for v in result] if isinstance(result, list) else [float(result)]


def evaluate(claim, evidence, template):
    """One claim through one prompt. Returns a small dict of what happened."""
    prompt = template.replace("<REPORT>", evidence).replace("<STATEMENT>", claim.statement)
    raw = call_ollama(prompt, SKILL_CONFIG)
    numbers, operation, claimed = parse_response(raw["response"])

    out = {"numbers": numbers, "operation": operation, "claimed": claimed,
           "parsed": None not in (numbers, operation, claimed),
           "units_clash": False, "computed": None, "computed_ok": False}

    if not out["parsed"]:
        return out

    text = claimed or ""
    is_percent = operation in PERCENT_OPERATIONS
    out["units_clash"] = ("%" in text and not is_percent) or ("$" in text and is_percent)

    out["computed"] = computed = compute(operation, numbers)
    if computed is not None:
        # Does the model's own arithmetic reproduce the benchmark's answer?
        # Tolerant to 0.5%, because this asks whether it did the RIGHT SUM, not
        # whether it matched to the last digit.
        for gold in gold_values(claim):
            if gold != 0 and abs(computed - gold) <= 0.005 * abs(gold):
                out["computed_ok"] = True
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25

    claims = [c for c in load_claims() if c.subset == "numeric"]
    claims.sort(key=lambda c: c.example_id)
    claims = claims[:n]

    main_template = load_prompt_template("baseline_v1")
    versions = {}
    for name in ("arithmetics_v1", "arithmetics_v2"):
        path = REPO_ROOT / "prompts" / f"{name}.txt"
        if not path.exists() and len(sys.argv) > 2:
            path = Path(sys.argv[2]) / f"{name}.txt"
        if path.exists():
            versions[name] = path.read_text()
        else:
            print(f"  (skipping {name}, not found at {path})")

    if len(versions) < 2:
        raise SystemExit("need both prompt versions on disk to compare")

    print(f"{len(claims)} numeric claims, qwen2.5-coder:3b, temperature 0, seed 0\n")

    results = {name: [] for name in versions}
    for index, claim in enumerate(claims, 1):
        report = read_report(claim.report)
        chunks = retrieve(claim, report, k=10)
        _, evidence, _ = build_prompt(claim, chunks, main_template, MAIN_CONFIG)
        for name, template in versions.items():
            results[name].append((claim, evaluate(claim, evidence, template)))
        print(f"  [{index}/{len(claims)}] {claim.example_id}", end="\r", flush=True)
    print(" " * 60, end="\r")

    print(f"  {'prompt':18}{'parsed':>10}{'units clash':>14}{'computed ok':>14}")
    for name in versions:
        rows = [r for _, r in results[name]]
        parsed = sum(r["parsed"] for r in rows)
        clash = sum(r["units_clash"] for r in rows)
        good = sum(r["computed_ok"] for r in rows)
        print(f"  {name:18}{parsed:>7}/{len(rows)}{clash:>11}/{len(rows)}{good:>11}/{len(rows)}")

    print("\n  CLAIMS WHERE THE TWO PROMPTS CHOSE A DIFFERENT OPERATION\n")
    names = list(versions)
    shown = 0
    for (claim, a), (_, b) in zip(results[names[0]], results[names[1]]):
        if a["operation"] == b["operation"]:
            continue
        shown += 1
        print(f"  {claim.example_id}   gold execution_result = {claim.execution_result}")
        for name, r in ((names[0], a), (names[1], b)):
            mark = "ok " if r["computed_ok"] else ("CLASH" if r["units_clash"] else "no ")
            print(f"     {name:18} {str(r['operation']):16} claimed={str(r['claimed'])[:14]:16}"
                  f" computed={r['computed']}  {mark}")
    if not shown:
        print("  none: the two prompts agreed on every operation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
