"""Score the 16 published FINDVER baselines with our strict extractor.

`paper_numbers.md` section 2.4, generalised from one model to all sixteen. No
model run, no cloud quota: the upstream repo ships the raw response and the
label gpt-4o-mini extracted from it for 700 claims per model.

The point of the comparison. FINDVER's official evaluation replaces a response
with no stated verdict by `random.choice(["entailed", "refuted"])`, and stores
the result without recording that it happened. For a strong model that is a
rounding error. For a small one it is a large fraction of the reported score.
This script measures how large, across the whole model-size range.

Five columns, and only some of them may be quoted:

    published        their own reported accuracy, after the coin flip
    strict           our extractor, unparseable counted wrong
    unparseable      our extractor found no verdict
    no verdict word  the response contains neither "entail" nor "refut"
    truncated        the response ends without terminal punctuation

**"no verdict word" is the only defensible imputation figure.** A response
containing neither word cannot be extracted by any method, including
gpt-4o-mini, so those went to the coin flip regardless of extractor quality.
The rest of the unparseable column is our regex being weaker than theirs, which
is our limitation and not evidence about them.

**The published column may not be compared with our own strict numbers.** These
runs used temperature 1.0, a 1024-token generation cap, and a different
retriever. Section 2.4 records the confounds in full.

Usage:
    python3 test_scripts/score_published_baselines.py
    python3 test_scripts/score_published_baselines.py --sample    our 102 claims only
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.label_extractor import extract_label_with_source
from src.loader import load_claims
from src.sampler import stratified_sample

OUTPUT_DIR = (REPO_ROOT / "FinDVer" / "outputs" / "testmini_outputs" / "rag"
              / "processed_cot_outputs")

LABEL_TO_BOOL = {"entailed": True, "refuted": False}
PER_CELL = 17
SAMPLE_SEED = 0

# A response ending in anything else is treated as cut off mid-sentence. The
# markdown characters matter: gemini-1.5-pro ends 446 of its 700 responses with
# `*`, closing a bold "**refuted**", and Mistral-Large ends 124 the same way.
# Counting those as truncation reports a 63.7% truncation rate for a model whose
# unparseable rate is 6.7%, which is obviously wrong. Verified by inspecting the
# final character of every unpunctuated response, 9 August 2026.
TERMINAL_CHARS = ".!?\"')]}*`"


def response_text(record):
    """The model's raw response. Upstream stores it as a list of strings."""
    output = record["output"]
    return "\n".join(output) if isinstance(output, list) else str(output)


def to_val_id(example_id):
    """`ie-testmini-0` -> `ie-val-0`, the id scheme our loader uses."""
    return example_id.replace("-testmini-", "-val-")


def score_model(path, keep_ids=None):
    records = json.loads(path.read_text())
    if keep_ids is not None:
        records = [r for r in records if to_val_id(r["example_id"]) in keep_ids]
    if not records:
        return None

    published = strict = unparseable = no_verdict_word = unpunctuated = 0

    for record in records:
        text = response_text(record)
        gold = record["entailment_label"]

        # their stored result is already post-coin-flip
        published += bool(record["result"])

        label, _ = extract_label_with_source(text)
        predicted = LABEL_TO_BOOL.get(label)
        strict += predicted == gold

        if predicted is None:
            unparseable += 1
            lowered = text.lower()
            if "entail" not in lowered and "refut" not in lowered:
                no_verdict_word += 1

        stripped = text.strip()
        if stripped and stripped[-1] not in TERMINAL_CHARS:
            unpunctuated += 1

    n = len(records)
    return {
        "n": n,
        "published": published / n,
        "strict": strict / n,
        "unparseable": unparseable / n,
        "no_verdict_word": no_verdict_word / n,
        "regex_missed": (unparseable - no_verdict_word) / n,
        "unpunctuated": unpunctuated / n,
    }


def our_sample_ids():
    """The 102 claims every one of our runs uses, so the comparison is matched."""
    return {claim.example_id for claim in
            stratified_sample(load_claims(), PER_CELL, seed=SAMPLE_SEED)}


def main():
    keep_ids = our_sample_ids() if "--sample" in sys.argv else None
    scope = "our 102 claims" if keep_ids else "all 700 claims"

    paths = sorted(OUTPUT_DIR.glob("*.json"))
    if not paths:
        raise SystemExit(f"no upstream outputs in {OUTPUT_DIR}")

    rows = [(p.stem, score_model(p, keep_ids)) for p in paths]
    rows = [(name, s) for name, s in rows if s]
    rows.sort(key=lambda row: row[1]["published"], reverse=True)

    header = (f"{'model':<40}{'n':>5}{'published':>11}{'strict':>9}"
              f"{'unparse':>9}{'no word':>9}{'regex':>8}{'unpunct':>9}")
    print(f"\nFINDVER published baselines, RAG chain-of-thought, {scope}")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name, s in rows:
        print(f"{name:<40}{s['n']:>5}{s['published']:>10.1%}{s['strict']:>9.1%}"
              f"{s['unparseable']:>9.1%}{s['no_verdict_word']:>9.1%}"
              f"{s['regex_missed']:>8.1%}{s['unpunctuated']:>9.1%}")

    print("-" * len(header))
    print("\npublished  their accuracy, already including coin-flipped unparseables")
    print("strict     our extractor, unparseable counted wrong")
    print("no word    neither 'entail' nor 'refut' appears: no extractor could have")
    print("           read these, so they were imputed regardless. Half of them land")
    print("           correct by chance, so the imputed contribution to the published")
    print("           column is roughly half this figure.")
    print("regex      a verdict word is present but our regex missed it. Our weakness,")
    print("           not theirs, and not quotable as evidence about their evaluation.")
    print("unpunct    response ends mid-sentence, evidence of the 1024-token cap")

    print("\nImputation lower bound, published column, in accuracy points:")
    for name, s in rows:
        print(f"  {name:<40} {s['no_verdict_word'] * 50:5.1f} pts"
              f"   of {s['published']:.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
