"""Can an arithmetic verification skill work, before we build one?

The proposal (working_state.md, 27 August): when the numeric detector fires, the
3B locates the operands in the retrieved text, and PYTHON does the arithmetic and
the comparison instead of the model. The measured failure it targets is §2.19:
on refuted numeric claims whose asserted value sits within 0.1% of the truth, the
local models answer entailed 57% of the time.

The user's constraint is that we cannot afford another component built, measured
and set aside (§4.5 lists six). Nothing can prove a skill works before it runs,
but two of its ceilings can be computed offline, free, from fields the benchmark
already ships. If either ceiling is low the skill is dead and we learn it in an
afternoon rather than after a GPU night.

    PART 1  SEPARABILITY. Give the skill PERFECT arithmetic. It still has to
            decide entailed from refuted by comparing its computed value to the
            claim's asserted one, and that needs a tolerance. Entailed claims are
            ROUNDED ("approximately 16.07%"), so they sit a little away from the
            truth. Refuted claims in the tight band sit a little away from the
            truth too. If those two distributions overlap, no tolerance separates
            them and the skill cannot work no matter how good the arithmetic is.
            This is the ceiling that matters and it is checked first.

    PART 2  COVERAGE. The skill cannot compute with numbers it never saw. §2.20
            measured that all gold evidence reaches the prompt on 68.2% of
            numeric claims. This asks the sharper question: do the specific
            operands of the gold calculation appear in what BM25 retrieved?

    PART 3  The two combined, against the 3B's actual score on the same claims.

testmini only. `python_calculation` and `execution_result` do not exist in
test.json (the 16 August trap), so none of this transfers to the reported split.
No model calls, no GPU, no cloud quota.

KILL CRITERIA, fixed in working_state.md before these numbers were read:
    fewer than 20 of the 37 tight-band claims covered            -> stop
    oracle gain under about 5 points on the numeric subset       -> stop

Usage:
    python3 test_scripts/analyse_numeric_skill_ceiling.py
"""

import ast
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse_condition1 import load_run
from analyse_skill_targets import BUCKETS, NUMBER, SCALES, margin
from src.bm25_retriever import retrieve
from src.loader import load_claims
from src.run_loop import read_report

# The run whose numeric accuracy the skill has to improve on. Condition 1 is the
# local 3B alone, which is what the skill replaces on numeric claims.
BASELINE_RUN = "condition1_3b_full700"

K = 10

# A number as it appears in a filing: $1,204,500 / (45,300) / 65,300 * / 3.27
TEXT_NUMBER = re.compile(r"\(?\$?\s?\d[\d,]*(?:\.\d+)?\)?")

# Relative tolerance for calling a retrieved number the same as an operand.
# Not zero, because filings round: an operand of 86724037 may be printed as
# 86,724 under an "(in thousands)" heading, and 3.274 may be printed as 3.27.
MATCH_TOL = 0.005

# Operands below this are structural, not quantities from the filing: the 100 in
# a percentage, the 1 in round(x, 1), the 2 in an average. Used only by the
# fallback path, which reports how often it fires.
MIN_OPERAND = 1000


def parse_text_numbers(text):
    """Every number in a block of filing text, both signs, parens as negative."""
    values = set()
    for match in TEXT_NUMBER.findall(text):
        negative = match.startswith("(") and match.endswith(")")
        cleaned = match.strip("()").replace("$", "").replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        values.add(-value if negative else value)
        values.add(value)
        values.add(-value)
    return values


def operands_of(claim):
    """The literal numbers the gold calculation reads out of the filing.

    Only constants bound straight to a name, `total_interest_paid = 183479`.
    That deliberately drops derived values (`net_change = ending - beginning`)
    and structural constants (`* 100`, `round(x, 1)`), because neither has to be
    found in the text. Returns (operands, used_fallback).
    """
    code = claim.python_calculation
    if not code:
        return [], False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return [], False

    operands = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, (int, float)) and not isinstance(node.value.value, bool):
                operands.append(float(node.value.value))

    if operands:
        return operands, False

    # No plain assignments, e.g. `return 183479 - 2483`. Take every literal big
    # enough to be a quantity rather than a multiplier.
    fallback = [float(n.value) for n in ast.walk(tree)
                if isinstance(n, ast.Constant)
                and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)
                and abs(n.value) >= MIN_OPERAND]
    return fallback, bool(fallback)


def found_in(operand, text_values, allow_scale):
    """Is this operand present among the numbers of the retrieved text?"""
    scales = SCALES if allow_scale else (1,)
    for scale in scales:
        target = operand * scale
        if target == 0:
            continue
        for value in text_values:
            if abs(value - target) <= MATCH_TOL * abs(target):
                return True
    return False


def asserted_values(statement):
    """Every number in the claim, with the precision it was written to.

    '17.1%' carries one decimal place. That is information: it says the author
    considered one decimal enough, so 17.19 and 17.1 are the same assertion.
    A flat relative tolerance throws this away and pays for it on both sides.
    """
    out = []
    for match in NUMBER.findall(statement):
        cleaned = match.replace("$", "").replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        places = len(cleaned.split(".")[1]) if "." in cleaned else 0
        out.append((value, places))
    return out


def gold_values(claim):
    result = claim.execution_result
    return [float(v) for v in result] if isinstance(result, list) else [float(result)]


def precision_verdict(claim):
    """Entailed iff the computed value matches the claim AT THE CLAIM'S OWN PRECISION.

    Accepts rounding and truncation, because FINDVER's own labels accept both:
    numeric-val-187 asserts 17.1% against a gold of 17.19 and is labelled
    entailed. Sign and scale are allowed for the same reasons as §2.19's matcher.

    No threshold, and therefore nothing tuned on these claims. That is the point
    of it: §4.5's warning about selecting a winner on the evaluation set cannot
    apply to a rule with no parameter to select.
    """
    tokens = asserted_values(claim.statement)
    if not tokens:
        return None
    for gold in gold_values(claim):
        matched = False
        for value, places in tokens:
            factor = 10 ** places
            for scale in SCALES:
                for candidate in (value * scale, -value * scale):
                    if abs(round(gold, places) - candidate) < 1e-9:
                        matched = True
                    if abs(math.trunc(gold * factor) / factor - candidate) < 1e-9:
                        matched = True
        if not matched:
            return False
    return True


def precision_rule(claims):
    """PART 1B. The same question with a rule that has no tuned parameter."""
    print("\n" + "=" * 78)
    print("PART 1B  A BETTER RULE: compare at the precision the claim states")
    print("=" * 78)
    print("\n  A flat tolerance has to serve two jobs at once and fails both. Tight")
    print("  thresholds wrongly refute rounded entailed claims (17.1% against a")
    print("  true 17.19); loose ones wave through the tight band §2.19 is about.")
    print("  Comparing at the claim's own precision removes the conflict, and it")
    print("  has no parameter chosen on these claims.\n")

    entailed = [c for c in claims if c.entailment_label]
    refuted = [c for c in claims if not c.entailment_label]
    e_ok = sum(1 for c in entailed if precision_verdict(c) is True)
    r_ok = sum(1 for c in refuted if precision_verdict(c) is False)
    total = (e_ok + r_ok) / len(claims)
    print(f"  {'entailed correct':22}{e_ok}/{len(entailed)} = {e_ok / len(entailed):.1%}")
    print(f"  {'refuted correct':22}{r_ok}/{len(refuted)} = {r_ok / len(refuted):.1%}")
    print(f"  {'overall':22}{e_ok + r_ok}/{len(claims)} = {total:.1%}")
    return total


def separability(claims):
    """PART 1. With perfect arithmetic, does any tolerance separate the labels?"""
    print("\n" + "=" * 78)
    print("PART 1  SEPARABILITY: with PERFECT arithmetic, can a tolerance decide?")
    print("=" * 78)
    print("\nThe skill computes the true value, then must call the claim entailed or")
    print("refuted by how far the asserted value sits from it. Entailed claims are")
    print("rounded, so they are not at zero. If the two distributions overlap, no")
    print("threshold works and better arithmetic cannot help.\n")

    rows = []
    unmatched = 0
    for claim in claims:
        m = margin(claim)
        if m is None:
            unmatched += 1
            continue
        rows.append((claim.example_id, claim.entailment_label, m))

    entailed = sorted(m for _, label, m in rows if label)
    refuted = sorted(m for _, label, m in rows if not label)
    print(f"  claims with a computable margin   {len(rows)}/{len(claims)}"
          f"   ({unmatched} have no parseable number in the statement)")
    print(f"  entailed {len(entailed)}   refuted {len(refuted)}")

    def pct(sorted_values, q):
        if not sorted_values:
            return float("nan")
        return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]

    print("\n  HOW FAR THE ASSERTED VALUE SITS FROM THE TRUTH")
    print(f"  {'':10}{'p50':>12}{'p75':>12}{'p90':>12}{'p95':>12}{'max':>12}")
    for name, values in (("entailed", entailed), ("refuted", refuted)):
        print(f"  {name:10}" + "".join(f"{pct(values, q):>11.4%}"
                                       for q in (0.50, 0.75, 0.90, 0.95))
              + f"{max(values):>11.2%}")

    print("\n  ACCURACY AT EACH TOLERANCE, perfect arithmetic assumed")
    print("  predict entailed when margin < tolerance\n")
    print(f"  {'tolerance':>12}{'accuracy':>12}{'entailed ok':>14}{'refuted ok':>13}")

    candidates = [0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10]
    best = None
    for tol in candidates:
        ent_ok = sum(1 for m in entailed if m < tol)
        ref_ok = sum(1 for m in refuted if m >= tol)
        acc = (ent_ok + ref_ok) / len(rows)
        marker = ""
        if best is None or acc > best[1]:
            best = (tol, acc)
            marker = ""
        print(f"  {tol:>11.2%}{acc:>12.1%}"
              f"{ent_ok / len(entailed):>13.1%}{ref_ok / len(refuted):>13.1%}{marker}")

    # The best threshold over a fine grid, reported separately because choosing
    # it on these claims is selection on the evaluation set (§4.5).
    grid = sorted({m for _, _, m in rows})
    best_fine = (0.0, 0.0)
    for tol in grid:
        acc = (sum(1 for m in entailed if m < tol)
               + sum(1 for m in refuted if m >= tol)) / len(rows)
        if acc > best_fine[1]:
            best_fine = (tol, acc)
    print(f"\n  best tolerance on a fine grid: {best_fine[0]:.4%} -> {best_fine[1]:.1%}")
    print("  Chosen on these same claims, so it is an upper bound, not a result.")
    return rows, best_fine


def coverage(claims):
    """PART 2. Are the gold calculation's operands in what BM25 retrieved?"""
    print("\n" + "=" * 78)
    print("PART 2  COVERAGE: are the operands actually in the retrieved text?")
    print("=" * 78)
    print(f"\n  BM25 at k={K}, the shipped retriever, re-run over each claim's filing.\n")

    covered_exact, covered_scaled, no_operands, fallbacks = {}, {}, 0, 0
    for claim in claims:
        operands, used_fallback = operands_of(claim)
        fallbacks += used_fallback
        if not operands:
            no_operands += 1
            covered_exact[claim.example_id] = False
            covered_scaled[claim.example_id] = False
            continue
        report = read_report(claim.report)
        text = "\n".join(e["context"] for e in retrieve(claim, report, k=K))
        values = parse_text_numbers(text)
        covered_exact[claim.example_id] = all(
            found_in(o, values, allow_scale=False) for o in operands)
        covered_scaled[claim.example_id] = all(
            found_in(o, values, allow_scale=True) for o in operands)

    n = len(claims)
    print(f"  operands extracted from python_calculation   {n - no_operands}/{n}"
          f"   ({fallbacks} via the fallback path, {no_operands} yielded none)")
    exact = sum(covered_exact.values())
    scaled = sum(covered_scaled.values())
    print(f"  ALL operands present, exact match            {exact}/{n} = {exact / n:.1%}")
    print(f"  ALL operands present, scale allowed          {scaled}/{n} = {scaled / n:.1%}")
    print("\n  Scale allowed is the honest figure: trap 7, a filing reporting")
    print("  '(in thousands)' prints 86,724 for an operand of 86,724,037.")
    return covered_scaled


def by_band(claims, covered):
    """Coverage on the 37 tight-band claims, which is kill criterion 1."""
    print("\n  COVERAGE BY MARGIN BAND, refuted claims only")
    print("  The tight band is where §2.19 says the local models fail.\n")
    print(f"  {'band':16}{'claims':>8}{'covered':>10}{'rate':>9}")
    refuted = [c for c in claims if not c.entailment_label]
    tight_covered = 0
    for name, low, high in BUCKETS:
        ids = [c.example_id for c in refuted
               if (m := margin(c)) is not None and low <= m < high]
        hit = sum(covered.get(i, False) for i in ids)
        if name.startswith("tight"):
            tight_covered = hit
        rate = hit / len(ids) if ids else 0.0
        print(f"  {name:16}{len(ids):>8}{hit:>10}{rate:>9.1%}")
    return tight_covered


def oracle(claims, covered, verdict_fn, label):
    """PART 3. Coverage and the comparison rule together, against the 3B."""
    print("\n" + "=" * 78)
    print(f"PART 3  THE ORACLE, {label}: both ceilings together, against the real 3B")
    print("=" * 78)
    print("\n  Perfect arithmetic on a covered claim. On an uncovered claim the skill")
    print("  DECLINES and the claim falls through to the 3B, which is what the")
    print("  pipeline does today.\n")

    run = load_run(BASELINE_RUN)
    scored = [c for c in claims if c.example_id in run]

    base_correct = sum(run[c.example_id]["extracted_label"] == c.entailment_label
                       for c in scored)
    skill_correct, declined, skill_used = 0, 0, 0
    for claim in scored:
        predicted = verdict_fn(claim) if covered.get(claim.example_id) else None
        if predicted is None:
            declined += 1
            predicted = run[claim.example_id]["extracted_label"]
        else:
            skill_used += 1
        skill_correct += predicted == claim.entailment_label

    n = len(scored)
    print(f"  {'3B alone':22}{base_correct}/{n} = {base_correct / n:.1%}")
    print(f"  {'skill + 3B fallback':22}{skill_correct}/{n} = {skill_correct / n:.1%}")
    print(f"  {'gain':22}{skill_correct - base_correct:+d} claims "
          f"= {(skill_correct - base_correct) / n:+.1%}")
    print(f"\n  skill answered {skill_used}/{n} = {skill_used / n:.1%},"
          f" declined {declined}")
    print("\n  Every number here is an upper bound. The real skill must also pick the")
    print("  right operands out of the text and the right number out of the claim,")
    print("  both of which are oracled above.")
    return (skill_correct - base_correct) / n, skill_used


def main():
    claims = [c for c in load_claims() if c.subset == "numeric"]
    print(f"testmini, numeric subset, n={len(claims)}")
    print("test.json ships no python_calculation or execution_result, so this is")
    print("testmini-only and cannot be replicated on the reported split.")

    rows, best_fine = separability(claims)
    precision_rule(claims)
    covered = coverage(claims)
    tight_covered = by_band(claims, covered)

    tuned_gain, _ = oracle(claims, covered,
                           lambda c: (m := margin(c)) is not None and m < best_fine[0],
                           f"flat tolerance {best_fine[0]:.4%}, TUNED on these claims")
    gain, _ = oracle(claims, covered, precision_verdict,
                     "precision rule, nothing tuned")

    print("\n" + "=" * 78)
    print("KILL CRITERIA, written down before these numbers were read")
    print("=" * 78)
    ok_band = tight_covered >= 20
    ok_gain = gain >= 0.05
    print(f"\n  tight-band claims covered   {tight_covered}/37"
          f"   need >= 20   {'PASS' if ok_band else 'FAIL'}")
    print(f"  oracle gain on the subset   {gain:+.1%}"
          f"      need >= +5.0%  {'PASS' if ok_gain else 'FAIL'}")
    print(f"\n  Both figures are upper bounds. The real skill must also find the right")
    print("  operands in the text and the right number in the claim, both oracled here.")
    print(f"\n  for comparison, the tuned flat tolerance reaches {tuned_gain:+.1%}."
          "\n  The untuned rule is the one to build, and it is the better of the two.")
    print(f"\n  VERDICT: {'BUILD IT' if ok_band and ok_gain else 'DO NOT BUILD IT'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
