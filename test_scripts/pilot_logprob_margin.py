"""Pilot: does the 3B's logprob margin at the verdict token predict its errors?

**This is a go/no-go test, not a result.** Self consistency at temperature 0 was
closed on 13 August because the model turned out to be deterministic, so three
samples were one sample repeated. Logprobs measure the same underlying quantity
directly: how close the model was to saying the opposite. If the margin carries
no signal here, then temperature-0.7 sampling will not either, since sampling is
a noisier estimate of the same thing. **So this one 12-minute run can close both
ideas.**

It reuses the stored prompts from `condition1_3b_full700`, so no retrieval or
prompt building happens and nothing in `src/` is touched.

Two readings, in this order:

    1. does the margin vary at all?   If the model is confident everywhere there
                                      is nothing to gate on. Stop here.
    2. does a small margin predict a  Split at the median and compare accuracy.
       wrong answer?                  This is the whole idea.

**Known complication, reported rather than hidden:** enabling logprobs changes
the generated text on some claims, so responses here will not always match the
stored run. Labels are therefore re-extracted from the new response, never taken
from the stored record.

Usage:
    python3 test_scripts/pilot_logprob_margin.py            # 100 claims
    python3 test_scripts/pilot_logprob_margin.py 40         # fewer, faster
"""

import json
import random
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test_scripts"))

from analyse_condition1 import load_run
# Import the extractor's own patterns so this cannot drift from what ships.
from label_extractor import (
    _ANCHORED, _BARE, _HEDGE_BEFORE, _NEGATION_BEFORE, _OPPOSITE, TAIL_CHARS,
)

SOURCE_RUN = "condition1_3b_full700"
HOST = "10.0.0.26"
TOP_LOGPROBS = 20   # high, because a confident model pushes the opposite verdict
                    # out of a short list and that shows up as censoring, not signal
SAMPLE_SEED = 0


def locate_verdict(response):
    """(label, source, char_index) mirroring label_extractor.extract_label_with_source.

    The extractor returns no position, so the same two levels are repeated here
    with `finditer` to recover one. char_index is the START of the verdict word,
    because that is the token at which the model commits: "refuted" arrives as
    "Ref" then "uted", and the decision is already made by the first piece.
    """
    anchored = list(_ANCHORED.finditer(response))
    if anchored:
        m = anchored[-1]
        return m.group(1).lower(), "anchored", m.start(1)

    offset = max(0, len(response) - TAIL_CHARS)
    tail = response[offset:]
    bare = list(_BARE.finditer(tail))
    if not bare:
        return None, "none", None

    last = bare[-1]
    before = tail[: last.start()]
    label = last.group(1).lower()
    if _HEDGE_BEFORE.search(before):
        return None, "hedged", None
    if _NEGATION_BEFORE.search(before):
        return _OPPOSITE[label], "negated", offset + last.start(1)
    return label, "bare", offset + last.start(1)


def token_at_char(logprobs, char_index):
    """Index of the token containing this character offset, or None."""
    pos = 0
    for i, entry in enumerate(logprobs):
        pos += len(entry["token"])
        if pos > char_index:
            return i
    return None


def margin_at(entry, label):
    """Gap in logprob between the chosen token and the best opposite-verdict rival.

    Returns (margin, censored). censored is True when no alternative in the list
    means the opposite verdict, which means the true margin is at least as large
    as the gap to the weakest listed rival. A censored value is a floor, not a
    measurement, and the two must not be averaged together.
    """
    want = "ent" if label == "refuted" else "ref"
    chosen = entry["logprob"]
    rivals = [a["logprob"] for a in entry["top_logprobs"]
              if a["token"].strip().lower().startswith(want)]
    if rivals:
        return chosen - max(rivals), False
    weakest = min(a["logprob"] for a in entry["top_logprobs"])
    return chosen - weakest, True


def call(prompt):
    payload = {
        "model": "qwen2.5-coder:3b",
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 32768, "num_predict": 2000, "temperature": 0, "seed": 0},
        "logprobs": True,
        "top_logprobs": TOP_LOGPROBS,
    }
    request = urllib.request.Request(
        f"http://{HOST}:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run = load_run(SOURCE_RUN)
    ids = random.Random(SAMPLE_SEED).sample(sorted(run), n)

    rows, no_verdict, unlocatable, changed = [], 0, 0, 0
    for k, cid in enumerate(ids, 1):
        d = call(run[cid]["prompt"])
        text = d["response"]
        changed += text != run[cid]["response"]

        label, source, char_index = locate_verdict(text)
        if label is None:
            no_verdict += 1
            continue
        idx = token_at_char(d["logprobs"], char_index)
        if idx is None:
            unlocatable += 1
            continue

        margin, censored = margin_at(d["logprobs"][idx], label)
        rows.append({
            "id": cid, "source": source, "margin": margin, "censored": censored,
            "correct": (label == "entailed") == run[cid]["gold_label"],
        })
        print(f"  [{k}/{n}] {cid:20s} {source:9s} margin={margin:7.3f}"
              f"{' (censored)' if censored else ''}", flush=True)

    print(f"\n{'='*70}\nn={n}   usable={len(rows)}   no verdict={no_verdict}   "
          f"token not found={unlocatable}   response changed vs stored={changed}")
    if not rows:
        raise SystemExit("no usable claims; nothing to report")

    clean = [r for r in rows if not r["censored"]]
    print(f"censored (opposite verdict absent from top {TOP_LOGPROBS}): "
          f"{len(rows)-len(clean)}/{len(rows)}")

    m = sorted(r["margin"] for r in rows)
    q = statistics.quantiles(m, n=4) if len(m) > 3 else [float('nan')]*3
    print(f"\nREADING 1 - does the margin vary?")
    print(f"  min {m[0]:.3f}   q1 {q[0]:.3f}   median {statistics.median(m):.3f}"
          f"   q3 {q[2]:.3f}   max {m[-1]:.3f}")
    print("  A narrow spread means the model is uniformly confident and there is")
    print("  nothing to gate on. Stop here if so.")

    mid = statistics.median(m)
    low = [r for r in rows if r["margin"] <= mid]
    high = [r for r in rows if r["margin"] > mid]
    acc = lambda g: sum(r["correct"] for r in g) / len(g) if g else float("nan")
    print(f"\nREADING 2 - does a small margin predict a wrong answer?")
    print(f"  low  margin  n={len(low):3d}  accuracy {acc(low):.1%}")
    print(f"  high margin  n={len(high):3d}  accuracy {acc(high):.1%}")
    print(f"  overall      n={len(rows):3d}  accuracy {acc(rows):.1%}")
    print("\n  The idea works only if low-margin accuracy is clearly the worse of")
    print("  the two. A gap inside a few points on n=100 is not a result.")


if __name__ == "__main__":
    main()
