"""Will the arithmetic skill actually replace cloud calls, or only in theory?

§2.21 gave an ORACLE ceiling: it assumed the model finds the right operands. That
assumption is the whole risk. If the 3B cannot locate the two numbers in the
retrieved text, the skill declines on everything and replaces no cloud calls at
all, and we would have spent a GPU night learning that.

This checks the assumption against evidence already on disk. For every numeric
claim we have the 3B's stored response from condition 1. If the right operands
are ALREADY in that response text, the model can find them, and the skill's job
is only to stop it botching the comparison afterwards. If they are not, the skill
is dead and no code should be written.

    the number that matters: of the numeric claims the pipeline currently sends
    to the cloud, how many could be answered on device instead?

No model calls, no GPU, no cloud quota. testmini only, because test.json ships no
python_calculation (the 16 August trap).

Usage:
    python3 test_scripts/analyse_skill_realistic_ceiling.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse_condition1 import load_run
from analyse_numeric_skill_ceiling import (BASELINE_RUN, K, found_in,
                                           operands_of, parse_text_numbers,
                                           precision_verdict)
from src.bm25_retriever import retrieve
from src.loader import load_claims
from src.run_loop import read_report

CLOUD_RUN = "condition2_flash_v2_full700"


def response_of(record):
    for key in ("response", "raw_response", "model_response", "text"):
        if isinstance(record.get(key), str):
            return record[key]
    return ""


def main():
    claims = [c for c in load_claims() if c.subset == "numeric"]
    run = load_run(BASELINE_RUN)
    cloud = load_run(CLOUD_RUN)

    in_text, in_response, both = [], [], []
    for claim in claims:
        operands, _ = operands_of(claim)
        if not operands:
            continue
        report = read_report(claim.report)
        retrieved = "\n".join(e["context"] for e in retrieve(claim, report, k=K))
        text_values = parse_text_numbers(retrieved)
        present = all(found_in(o, text_values, allow_scale=True) for o in operands)

        record = run.get(claim.example_id)
        said = parse_text_numbers(response_of(record)) if record else set()
        spoken = all(found_in(o, said, allow_scale=True) for o in operands)

        if present:
            in_text.append(claim.example_id)
        if spoken:
            in_response.append(claim.example_id)
        if present and spoken:
            both.append(claim.example_id)

    n = len(claims)
    print(f"testmini numeric, n={n}\n")
    print("CAN THE MODEL FIND THE OPERANDS? The assumption the whole skill rests on.\n")
    print(f"  operands present in the retrieved text      {len(in_text):>4}/{n} = {len(in_text)/n:>5.1%}")
    print(f"  operands present in the 3B's OWN RESPONSE   {len(in_response):>4}/{n} = {len(in_response)/n:>5.1%}")
    print(f"  both                                        {len(both):>4}/{n} = {len(both)/n:>5.1%}")
    print("\n  The second row is the realistic one. It is the model already writing")
    print("  the right numbers down, unprompted, with no skill and no extra call.")

    # What the skill would score on the claims it can actually run on.
    ids = set(both)
    scored = [c for c in claims if c.example_id in ids and c.example_id in run]
    skill_ok = sum(precision_verdict(c) == c.entailment_label for c in scored)
    base_ok = sum(run[c.example_id]["extracted_label"] == c.entailment_label for c in scored)
    cloud_ok = sum(cloud[c.example_id]["extracted_label"] == c.entailment_label
                   for c in scored if c.example_id in cloud)
    cloud_n = sum(1 for c in scored if c.example_id in cloud)

    print(f"\nON THE {len(scored)} CLAIMS THE SKILL COULD RUN ON, all three arms\n")
    print(f"  3B alone            {base_ok}/{len(scored)} = {base_ok/len(scored):.1%}")
    print(f"  cloud alone         {cloud_ok}/{cloud_n} = {cloud_ok/cloud_n:.1%}")
    print(f"  skill (perfect arithmetic, precision rule)"
          f"  {skill_ok}/{len(scored)} = {skill_ok/len(scored):.1%}")

    print("\nCLOUD CALLS REPLACED, if the skill runs wherever it can\n")
    coverage = len(scored) / n
    print(f"  numeric claims kept on device        {coverage:.1%}")
    print("  In run 1 the numeric detector caused 449 of 908 cloud calls on test.json.")
    saved = 449 * coverage
    print(f"  projected calls removed              {saved:.0f} of 449")
    print(f"  total cloud calls 908 -> {908 - saved:.0f}"
          f"   ({(908 - saved)/1700:.1%} of claims, from 53.4%)")
    print("\n  Projection assumes testmini coverage transfers to test.json. It is a")
    print("  projection, not a measurement, and test.json cannot confirm it offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
