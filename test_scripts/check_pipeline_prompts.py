"""Check that the routed pipeline builds byte-identical prompts to the runs it
has to reproduce.

Verdicts cannot be used for this. Identical reruns of one model on one machine
move about one claim in ten (2.3.2), so a verdict mismatch proves nothing either
way. The prompt can: retrieval, sampling, trimming and prompt building have no
floating-point in them, and `prompt_eval_count` was identical across machines on
all six claims of the 7 August cross-machine test.

So the rule this enforces is:

    prompts match, verdicts differ    the plumbing is right, the model is the model
    prompts differ                    a real bug, and the run is not comparable

Each pipeline stage is compared against the single-model run whose config it
mirrors. A stage only appears when it ran, so the cloud comparison covers the
escalated claims only.

Usage:
    python3 test_scripts/check_pipeline_prompts.py
    python3 test_scripts/check_pipeline_prompts.py pipeline_trial
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyse_condition1 import load_run

# stage -> the single-model run it must reproduce. Each pair shares a retriever,
# a top_k, a prompt_version and a token budget, so the prompts must be equal.
REFERENCE = {
    "local_a": "condition1_3b_full700",
    "local_b": "condition1_7b_full700",
    "cloud": "condition2_flash_v2_full700",
}


def compare(routed, reference, stage):
    """Per-claim prompt comparison for one stage. Returns (matches, mismatches)."""
    matches, mismatches = [], []
    for example_id in sorted(routed):
        record = routed[example_id]
        if stage not in record.get("stages", {}):
            continue                      # the stage did not run on this claim
        if example_id not in reference:
            continue                      # not in the reference run
        ours = record["stages"][stage]["prompt"]
        theirs = reference[example_id]["prompt"]
        (matches if ours == theirs else mismatches).append(example_id)
    return matches, mismatches


def describe(example_id, ours, theirs):
    """First point of divergence, so a mismatch is debuggable without a diff tool."""
    if len(ours) != len(theirs):
        detail = f"length {len(ours)} vs {len(theirs)}"
    else:
        detail = "same length, different bytes"
    for position, (a, b) in enumerate(zip(ours, theirs)):
        if a != b:
            return f"{detail}, first differs at char {position}: {ours[position:position+60]!r}"
    return f"{detail}, one is a prefix of the other"


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "pipeline_trial"
    routed = load_run(name)
    print(f"routed run: {name}, {len(routed)} claims\n")

    failures = 0
    for stage, reference_name in REFERENCE.items():
        try:
            reference = load_run(reference_name)
        except SystemExit:
            print(f"  {stage:9} SKIP   {reference_name} not on disk")
            continue

        matches, mismatches = compare(routed, reference, stage)
        ran = len(matches) + len(mismatches)
        if ran == 0:
            print(f"  {stage:9} SKIP   this stage ran on no comparable claim")
            continue

        status = "ok  " if not mismatches else "FAIL"
        print(f"  {stage:9} {status}   {len(matches)}/{ran} prompts byte-identical"
              f"  vs {reference_name}")

        for example_id in mismatches[:3]:
            ours = routed[example_id]["stages"][stage]["prompt"]
            theirs = reference[example_id]["prompt"]
            print(f"      {example_id}: {describe(example_id, ours, theirs)}")
        if len(mismatches) > 3:
            print(f"      ... and {len(mismatches) - 3} more")
        failures += len(mismatches)

    # Token counts are a second, independent check on the same thing: they come
    # from the server rather than from our string building.
    print()
    for stage, reference_name in REFERENCE.items():
        try:
            reference = load_run(reference_name)
        except SystemExit:
            continue
        pairs = [(routed[i]["stages"][stage].get("prompt_eval_count"),
                  reference[i].get("prompt_eval_count"))
                 for i in sorted(routed)
                 if stage in routed[i].get("stages", {}) and i in reference]
        if not pairs:
            continue
        same = sum(a == b for a, b in pairs)
        print(f"  {stage:9} prompt_eval_count matches {same}/{len(pairs)}")

    print()
    if failures:
        print(f"{failures} prompt mismatches. The pipeline is NOT building the same "
              f"prompts as the runs it is compared against.")
        return 1
    print("Every prompt the pipeline built is byte-identical to its reference run.\n"
          "Verdict differences from here are the model, not the plumbing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
