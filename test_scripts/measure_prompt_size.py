"""Regenerate the prompt size and overflow table in paper_numbers.md §3.2.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. §3.2 was computed on 5 August by throwaway code and
had no reproducer, which was found during the 12 August audit.

The table decides two things that are already settled, so this script exists to
defend them rather than to explore:

    num_ctx 32768 rather than 16384   because 16384 leaves 15 of 700 claims
                                      overflowing at k=10 and 104 at k=20
    k=20 as the practical ceiling     because k=30 leaves 53 of 700 over even
                                      at 32768

There are no model calls. It retrieves with BM25 at each k, builds the real
prompt through `run_loop.build_prompt`, and counts characters.

**Trimming is deliberately disabled** by giving `build_prompt` an enormous
budget. §3.2 measures how large prompts WOULD be, which is what makes the
overflow counts meaningful. Letting the trimmer run would clip every prompt to
the budget and every count would be zero.

**Characters per token is 3.31, not 4.** §3.1 measured 3.31 on table-heavy
content against 4.44 on prose, and this corpus is 18% tables, so 3.31 is the
conservative choice. It is a estimate and the table is an estimate with it.

Usage:
    python3 test_scripts/measure_prompt_size.py
    python3 test_scripts/measure_prompt_size.py 10 20
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# both, because modules in src/ import each other bare ("from loader import ...")
# while bm25_retriever reaches for the package path ("from src.evidence_asserter")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from loader import load_claims
from bm25_retriever import retrieve
from run_loop import build_prompt, read_report

# §3.1: measured on table-heavy content. Prose runs 4.44, so this over-counts
# tokens on prose claims and is the conservative direction for an overflow test.
CHARS_PER_TOKEN = 3.31

# num_ctx minus num_predict, for the two windows the project has used.
# 16384 - 2000 = 14384, and 32768 - 2000 = 30768.
THRESHOLDS = (14384, 30768)

K_VALUES = (10, 15, 20, 25, 30)

# large enough that trim_to_budget never fires, so we measure the untrimmed size
NO_TRIM_BUDGET = 10_000_000


def percentile(values, fraction):
    """Nearest-rank percentile. No numpy dependency for one number."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * len(ordered))) - 1)
    return ordered[max(0, index)]


def prompt_tokens_at_k(claims, template, k):
    """Estimated prompt tokens for every claim at this k."""
    # num_ctx and num_predict are unused here but must be present: build_prompt
    # calls config.get(key, config["num_ctx"] - ...), and Python evaluates that
    # default eagerly even when the key it is defaulting for exists.
    config = {"prompt_budget_tokens": NO_TRIM_BUDGET, "num_ctx": 0, "num_predict": 0}
    tokens = []
    for claim in claims:
        report = read_report(claim.report)
        chunks = retrieve(claim, report, k=k)
        prompt, _, kept = build_prompt(claim, chunks, template, config)
        if len(kept) != len(chunks):
            raise SystemExit(f"trimming fired at k={k} on {claim.example_id}; budget too small")
        tokens.append(len(prompt) / CHARS_PER_TOKEN)
    return tokens


def main():
    ks = [int(a) for a in sys.argv[1:]] or list(K_VALUES)

    template = (ROOT / "prompts" / "baseline_v1.txt").read_text()
    claims = load_claims()
    print(f"{len(claims)} claims, {CHARS_PER_TOKEN} chars/token, trimming disabled\n")

    header = f"  {'k':>3s} {'mean':>8s} {'p90':>8s} {'max':>8s}"
    for threshold in THRESHOLDS:
        header += f" {'over ' + str(threshold):>13s}"
    print(header)

    for k in ks:
        tokens = prompt_tokens_at_k(claims, template, k)
        row = (f"  {k:3d} {sum(tokens) / len(tokens):8,.0f}"
               f" {percentile(tokens, 0.90):8,.0f} {max(tokens):8,.0f}")
        for threshold in THRESHOLDS:
            over = sum(1 for t in tokens if t > threshold)
            row += f" {str(over) + '/' + str(len(tokens)):>13s}"
        print(row)


if __name__ == "__main__":
    main()
