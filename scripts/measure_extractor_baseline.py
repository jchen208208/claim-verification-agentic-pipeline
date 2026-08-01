"""Measure a deterministic regex extractor against gpt-4o-mini's labels.

Regenerates the table cited in docs/working_state.md, docs/build_log.md, and
sections 9.1 and 11.8 of docs/architecture_plan.md.

The upstream repo ships 700 records per model for 16 models, each storing the
raw model response and the label gpt-4o-mini extracted from it. That is 11,200
response/label pairs, so the regex can be developed and scored offline with no
model run and no cloud quota.

Two columns are reported:

    regex fires  what fraction of responses contain the pattern at all.
                 This is coverage: can the cheap method find an answer?
    agrees       of those, how often the regex answer equals gpt-4o-mini's.
                 This is accuracy against the reference.

Caveat: extracted_label is stored AFTER the official evaluation replaces
unparseable outputs with random.choice(["entailed", "refuted"]), so imputed
labels are indistinguishable from real ones. A miss is therefore an
unseparated mix of "no verdict stated" and "verdict phrased differently", and
the agreement figure is measured only where a clean sentence exists.

Usage:
    python3 scripts/measure_extractor_baseline.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.label_extractor import extract_label

OUTPUT_DIR = (REPO_ROOT / "FinDVer" / "outputs" / "testmini_outputs" / "rag"
              / "processed_cot_outputs")

def response_text(record):
    """The raw response. Stored as a one-element list in these files."""
    out = record["output"]
    return (out[0] if isinstance(out, list) else out) or ""


def measure(path):
    """Return (n, fires, agrees) for one model's output file."""
    records = json.load(open(path))
    fires = agrees = 0
    for record in records:
        label = extract_label(response_text(record))
        if label:
            fires += 1
            if label == record["extracted_label"]:
                agrees += 1
    return len(records), fires, agrees


def main():
    files = sorted(OUTPUT_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no model outputs under {OUTPUT_DIR}")

    print(f"{'model':40s} {'n':>5s} {'regex fires':>12s} {'agrees':>8s}")
    print("-" * 68)

    total_n = total_fires = total_agrees = 0
    for path in files:
        n, fires, agrees = measure(path)
        total_n += n
        total_fires += fires
        total_agrees += agrees
        print(f"{path.stem:40s} {n:5d} {fires / n:11.1%} "
              f"{agrees / fires if fires else 0:8.1%}")

    print("-" * 68)
    print(f"{f'TOTAL ({len(files)} models)':40s} {total_n:5d} "
          f"{total_fires / total_n:11.1%} {total_agrees / total_fires:8.1%}")


if __name__ == "__main__":
    main()
