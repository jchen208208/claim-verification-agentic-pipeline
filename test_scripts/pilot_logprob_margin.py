"""Does the 3B's logprob margin at the verdict token predict its errors?

Round 1 (13 Aug, n=100 random) established: the margin varies, low-margin claims
are wrong more often (54.0% vs 70.0%, Fisher p = 0.149, not significant), and as
a **replacement** for the 3B/7B gate it is dominated - 72.0% at 51% cloud calls
against the gate's 77.0% at 39%.

That was the wrong comparison. It does not test whether the margin **adds** to
the gate. This script tests the two additive variants:

    VARIANT 1  inside the agreement set. The 3B and 7B agree on 449/700 at
               76.8%, so ~104 errors sit where no disagreement signal can reach
               them. If low margin flags any, that is accuracy the gate cannot
               get.
    VARIANT 2  inside the disagreement set. Where the two differ but the 3B is
               very confident, keeping its answer trades a little accuracy for
               fewer cloud calls.

Sampling is **stratified by gate agreement**, because a random draw underfills
the agreement set, which is where variant 1 lives.

**Rows are saved to results/pilot_logprob_margin.json.** Round 1's margins were
lost when temp files were cleared, which cost a re-run. If the file exists this
script skips collection entirely and only re-analyses, so no GPU is needed to
try a different threshold.

Usage:
    python3 test_scripts/pilot_logprob_margin.py              # collect + analyse
    python3 test_scripts/pilot_logprob_margin.py --analyse    # analyse saved rows
"""

import json
import random
import statistics
import sys
import urllib.request
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test_scripts"))

from analyse_condition1 import load_run
from label_extractor import (
    _ANCHORED, _BARE, _HEDGE_BEFORE, _NEGATION_BEFORE, _OPPOSITE, TAIL_CHARS,
)

LOCAL_A, LOCAL_B = "condition1_3b_full700", "condition1_7b_full700"
CLOUD = "condition2_flash_v2_full700"
HOST = "10.0.0.26"
TOP_LOGPROBS = 20
SAMPLE_SEED = 0
N_AGREE, N_DIFFER = 150, 100          # stratified: variant 1 needs the agreement set
ROWS_PATH = ROOT / "results" / "pilot_logprob_margin.json"


def locate_verdict(response):
    """(label, source, char_index), mirroring label_extractor.extract_label_with_source.

    The extractor returns no position, so its two levels are repeated with
    finditer. char_index is the START of the verdict word: "refuted" arrives as
    "Ref" then "uted", and the decision is already made at the first piece.
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
    pos = 0
    for i, entry in enumerate(logprobs):
        pos += len(entry["token"])
        if pos > char_index:
            return i
    return None


def margin_at(entry, label):
    """(margin, censored). Censored means no listed alternative meant the
    opposite verdict, so the value is a floor rather than a measurement."""
    want = "ent" if label == "refuted" else "ref"
    rivals = [a["logprob"] for a in entry["top_logprobs"]
              if a["token"].strip().lower().startswith(want)]
    if rivals:
        return entry["logprob"] - max(rivals), False
    return entry["logprob"] - min(a["logprob"] for a in entry["top_logprobs"]), True


def call(prompt):
    payload = {"model": "qwen2.5-coder:3b", "prompt": prompt, "stream": False,
               "options": {"num_ctx": 32768, "num_predict": 2000,
                           "temperature": 0, "seed": 0},
               "logprobs": True, "top_logprobs": TOP_LOGPROBS}
    request = urllib.request.Request(
        f"http://{HOST}:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read())


def fisher(a, b, c, d):
    """Two-sided Fisher exact on a 2x2 table."""
    n = a + b + c + d
    p0 = comb(a + b, a) * comb(c + d, c) / comb(n, a + c)
    total = 0.0
    for x in range(0, min(a + b, a + c) + 1):
        y, z, w = a + b - x, a + c - x, c + d - (a + c - x)
        if y < 0 or z < 0 or w < 0:
            continue
        p = comb(a + b, x) * comb(c + d, z) / comb(n, a + c)
        if p <= p0 + 1e-12:
            total += p
    return min(1.0, total)


def collect(a, b):
    """Run the model over a stratified sample and return one row per claim."""
    shared = sorted(set(a) & set(b))
    agree = [i for i in shared if a[i]["extracted_label"] == b[i]["extracted_label"]]
    differ = [i for i in shared if i not in set(agree)]
    rng = random.Random(SAMPLE_SEED)
    ids = (rng.sample(agree, min(N_AGREE, len(agree)))
           + rng.sample(differ, min(N_DIFFER, len(differ))))
    rng.shuffle(ids)

    rows = []
    for k, cid in enumerate(ids, 1):
        d = call(a[cid]["prompt"])
        label, source, char_index = locate_verdict(d["response"])
        idx = token_at_char(d["logprobs"], char_index) if label else None
        margin, censored = (margin_at(d["logprobs"][idx], label)
                            if idx is not None else (None, None))
        rows.append({
            "id": cid, "source": source, "margin": margin, "censored": censored,
            "label": label,
            "changed_vs_stored": d["response"] != a[cid]["response"],
            "agree": a[cid]["extracted_label"] == b[cid]["extracted_label"],
        })
        print(f"  [{k}/{len(ids)}] {cid:20s} {source:9s} "
              f"margin={margin if margin is None else round(margin, 3)}", flush=True)
    return rows


def report(rows, a, b, cloud):
    gold = {r["id"]: a[r["id"]]["gold_label"] for r in rows}
    usable = [r for r in rows if r["margin"] is not None]
    for r in usable:
        r["correct"] = (r["label"] == "entailed") == gold[r["id"]]

    print(f"\n{'='*72}")
    print(f"n={len(rows)}  usable={len(usable)}  no verdict={len(rows)-len(usable)}  "
          f"changed vs stored={sum(r['changed_vs_stored'] for r in rows)}  "
          f"censored={sum(bool(r['censored']) for r in usable)}")

    m = sorted(r["margin"] for r in usable)
    print(f"\nmargin spread: min {m[0]:.3f}  median {statistics.median(m):.3f}  max {m[-1]:.3f}")

    def split_test(group, name):
        if len(group) < 8:
            print(f"\n{name}: n={len(group)}, too few to test"); return
        mid = statistics.median(r["margin"] for r in group)
        low = [r for r in group if r["margin"] <= mid]
        high = [r for r in group if r["margin"] > mid]
        lc, hc = sum(r["correct"] for r in low), sum(r["correct"] for r in high)
        p = fisher(lc, len(low) - lc, hc, len(high) - hc)
        print(f"\n{name}   (n={len(group)}, median margin {mid:.2f})")
        print(f"  low  margin  n={len(low):3d}  accuracy {lc/len(low):6.1%}")
        print(f"  high margin  n={len(high):3d}  accuracy {hc/len(high):6.1%}")
        print(f"  Fisher exact p = {p:.3f}"
              f"{'   <- significant' if p < 0.05 else '   <- not significant'}")

    agree_rows = [r for r in usable if r["agree"]]
    differ_rows = [r for r in usable if not r["agree"]]
    split_test(usable, "ALL CLAIMS")
    split_test(agree_rows, "VARIANT 1 - inside the AGREEMENT set (the gate is blind here)")
    split_test(differ_rows, "VARIANT 2 - inside the DISAGREEMENT set (the gate already escalates)")

    # what variant 1 would buy, on the sampled claims only
    if agree_rows:
        mid = statistics.median(r["margin"] for r in agree_rows)
        rescued = [r for r in agree_rows
                   if r["margin"] <= mid and not r["correct"]
                   and (cloud[r["id"]]["extracted_label"] == gold[r["id"]])]
        broken = [r for r in agree_rows
                  if r["margin"] <= mid and r["correct"]
                  and (cloud[r["id"]]["extracted_label"] != gold[r["id"]])]
        print(f"\nVARIANT 1 payoff on the sampled agreement claims:")
        print(f"  escalating the low-margin half would FIX {len(rescued)} and BREAK {len(broken)}"
              f"  (net {len(rescued)-len(broken):+d} over {len(agree_rows)} claims)")


def main():
    a, b, cloud = load_run(LOCAL_A), load_run(LOCAL_B), load_run(CLOUD)
    if "--analyse" in sys.argv:
        if not ROWS_PATH.exists():
            raise SystemExit(f"no saved rows at {ROWS_PATH}; run without --analyse first")
        rows = json.loads(ROWS_PATH.read_text())
        print(f"re-analysing {len(rows)} saved rows, no GPU used")
    else:
        rows = collect(a, b)
        ROWS_PATH.parent.mkdir(exist_ok=True)
        ROWS_PATH.write_text(json.dumps(rows, indent=1))
        print(f"\nrows saved to {ROWS_PATH}")
    report(rows, a, b, cloud)


if __name__ == "__main__":
    main()
