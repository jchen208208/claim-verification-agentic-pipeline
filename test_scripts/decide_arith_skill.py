"""Is the arithmetic skill worth keeping? One measurement, one decision.

The kill criterion was fixed before this ran: if the skill's label accuracy on
the claims it answers is below the cloud's accuracy on those SAME claims, the
skill is dead and goes into the paper as a negative result.

Two earlier readings were spoiled and are not used here:

    the 9-claim live run   sorted by example_id, which is data trap 2. All nine
                           were refuted. A skill that always says "refuted"
                           scores 100% on such a sample.
    the 30-claim compare   same fault, 30 refuted and 0 entailed.

This samples 30 entailed and 30 refuted, seeded, and asserts the balance before
any model call, which is what the trap requires.

The cloud arm is not re-run. condition2_flash_v2_full700 already holds
deepseek-v4-flash's answer for every testmini claim, so the comparison is paired
and costs no API quota.

Usage:
    python3 test_scripts/decide_arith_skill.py [per_label] [model] [prompt_version]

    per_label        claims per label. 125 is the whole numeric subset.
    model            ollama tag, default qwen2.5-coder:3b
    prompt_version   restrict to one prompt, default both

The model argument exists because the 3B result attributes the failure to operand
identification, and that attribution is untested against a larger local model.
"""

import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse_condition1 import load_run
from src.arithmetic_skill import (compute, grounded, parse_response,
                                  precision_match)
from src.bm25_retriever import retrieve
from src.loader import load_claims
from src.ollama_client import call_ollama
from src.run_loop import build_prompt, load_prompt_template, read_report

PERCENT_OPERATIONS = {"percent_change", "percent_of"}
CLOUD_RUN = "condition2_flash_v2_full700"
SEED = 0

DEFAULT_MODEL = "qwen2.5-coder:3b"

SKILL_CONFIG = {
    "model": DEFAULT_MODEL,
    "num_ctx": 32768,
    "num_predict": 1000,
    "temperature": 0,
    "seed": 0,
    "ollama_host": "10.0.0.26",
}
MAIN_CONFIG = {"num_ctx": 32768, "num_predict": 2000}


def units_agree(operation, claimed_text):
    text = claimed_text or ""
    is_percent = operation in PERCENT_OPERATIONS
    if "%" in text and not is_percent:
        return False
    if "$" in text and is_percent:
        return False
    return True


def run_skill(claim, evidence, template):
    """The full skill on one claim. Returns (verdict, decline_reason)."""
    prompt = template.replace("<REPORT>", evidence).replace("<STATEMENT>", claim.statement)
    response = call_ollama(prompt, SKILL_CONFIG)["response"]

    numbers, operation, claimed = parse_response(response)
    if numbers is None or operation is None or claimed is None:
        return None, "incomplete_extraction"
    if not units_agree(operation, claimed):
        return None, "operation_contradicts_claim"
    if not grounded(numbers, evidence):
        return None, "operands_not_in_evidence"
    computed = compute(operation, numbers)
    if computed is None:
        return None, "computation_failed"
    verdict = precision_match(computed, claimed)
    if verdict is None:
        return None, "no_comparable_value"
    return verdict, None


def two_sided_binomial(hits, n):
    """Exact two-sided binomial at p=0.5, which is McNemar without the chi-square
    approximation. Used because the discordant count here can be small."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(hits + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def mcnemar(skill, cloud, gold, ids):
    """Paired test on the claims where exactly one of the two is right."""
    skill_only = sum(1 for i in ids if skill[i] == gold[i] and cloud[i] != gold[i])
    cloud_only = sum(1 for i in ids if cloud[i] == gold[i] and skill[i] != gold[i])
    n = skill_only + cloud_only
    p = two_sided_binomial(min(skill_only, cloud_only), n)
    return skill_only, cloud_only, n, p


def balanced_sample(per_label):
    claims = [c for c in load_claims() if c.subset == "numeric"]
    entailed = [c for c in claims if c.entailment_label]
    refuted = [c for c in claims if not c.entailment_label]
    per_label = min(per_label, len(entailed), len(refuted))
    rng = random.Random(SEED)
    sample = rng.sample(entailed, per_label) + rng.sample(refuted, per_label)

    hits = sum(c.entailment_label for c in sample)
    if hits != per_label or len(sample) != 2 * per_label:
        raise ValueError(f"balance check failed: {hits} entailed of {len(sample)}")
    print(f"sample asserted balanced: {hits} entailed / {len(sample) - hits} refuted")
    rng.shuffle(sample)
    return sample


def main():
    per_label = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    if len(sys.argv) > 2:
        SKILL_CONFIG["model"] = sys.argv[2]
    only_prompt = sys.argv[3] if len(sys.argv) > 3 else None

    sample = balanced_sample(per_label)
    cloud = load_run(CLOUD_RUN)
    main_template = load_prompt_template("baseline_v1")

    versions = {}
    candidates = (only_prompt,) if only_prompt else ("arithmetics_v1", "arithmetics_v2")
    for name in candidates:
        path = REPO_ROOT / "prompts" / f"{name}.txt"
        text = path.read_text() if path.exists() else ""
        if "<REPORT>" not in text:
            raise SystemExit(f"{path} is empty or has no <REPORT> placeholder")
        versions[name] = text

    print(f"{len(sample)} claims, {SKILL_CONFIG['model']}, temperature 0, seed 0\n")

    outcomes = {name: {} for name in versions}
    for index, claim in enumerate(sample, 1):
        report = read_report(claim.report)
        chunks = retrieve(claim, report, k=10)
        _, evidence, _ = build_prompt(claim, chunks, main_template, MAIN_CONFIG)
        for name, template in versions.items():
            outcomes[name][claim.example_id] = run_skill(claim, evidence, template)
        print(f"  [{index}/{len(sample)}] {claim.example_id}   ", end="\r", flush=True)
    print(" " * 70, end="\r")

    gold = {c.example_id: c.entailment_label for c in sample}

    print(f"  {'prompt':18}{'answered':>11}{'skill acc':>12}{'CLOUD acc':>12}"
          f"{'same claims':>13}")
    verdicts = {}
    for name in versions:
        answered = [i for i, (v, _) in outcomes[name].items() if v is not None]
        if not answered:
            print(f"  {name:18}{0:>11}{'-':>12}{'-':>12}")
            continue
        skill_ok = sum(outcomes[name][i][0] == gold[i] for i in answered)
        cloud_ok = sum(cloud[i]["extracted_label"] == gold[i] for i in answered if i in cloud)
        cloud_n = sum(1 for i in answered if i in cloud)
        verdicts[name] = (skill_ok / len(answered), cloud_ok / cloud_n if cloud_n else 0,
                          len(answered))
        print(f"  {name:18}{len(answered):>7}/{len(sample)}"
              f"{skill_ok / len(answered):>11.1%}{cloud_ok / cloud_n:>12.1%}{cloud_n:>13}")

    print(f"\n  what the skill predicted, where gold is {per_label} entailed"
          f" / {per_label} refuted")
    for name in versions:
        answered = [i for i, (v, _) in outcomes[name].items() if v is not None]
        says_true = sum(outcomes[name][i][0] is True for i in answered)
        print(f"  {name:18}entailed {says_true}, refuted {len(answered) - says_true}")

    print("\n  DECLINE REASONS")
    for name in versions:
        counts = {}
        for _, reason in outcomes[name].values():
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
        print(f"  {name:18}{counts if counts else 'none'}")

    print("\n  PAIRED McNEMAR, skill against cloud on the claims the skill answered")
    for name in versions:
        answered = [i for i, (v, _) in outcomes[name].items()
                    if v is not None and i in cloud]
        skill_labels = {i: outcomes[name][i][0] for i in answered}
        cloud_labels = {i: cloud[i]["extracted_label"] for i in answered}
        a, b, n, p = mcnemar(skill_labels, cloud_labels, gold, answered)
        verdict = "SIGNIFICANT" if p < 0.05 else "tie"
        print(f"  {name:18}skill right/cloud wrong {a:>4}   cloud right/skill wrong {b:>4}"
              f"   n={n:>4}  p={p:.5f}  {verdict}")

    print("\n" + "=" * 66)
    print("  DECISION, criterion fixed before the run:")
    print("  skill accuracy on the claims it answers must beat the cloud's")
    print("  accuracy on those same claims.")
    for name, (skill_acc, cloud_acc, n) in verdicts.items():
        keep = skill_acc > cloud_acc
        print(f"    {name:18}{skill_acc:.1%} vs cloud {cloud_acc:.1%} on {n} claims"
              f"   -> {'KEEP' if keep else 'DEAD'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
