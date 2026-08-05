"""Targeted test: does claim decomposition improve retrieval where it should?

Not a full build. This decides whether src/decomposer.py is worth writing at
all, and it is deliberately restricted to the population where the mechanism
has something to fix.

Why these claims. Measured 5 Aug, our BM25's recall by number of gold elements
needed:

    1 element   79.8%      4 elements  60.2%
    2 elements  81.5%      5+          53.6%
    3 elements  78.6%

The deficit is entirely in claims needing 4 or more, which is 174 of 700. A
20-40 point hole is large enough that a real effect shows through the noise,
which a 2-point effect on the full set would not (see section 3.4.2).

Why the test is needed at all. A naive rule-based split with round-robin merge
was measured first and made things WORSE, 73.39% against 74.60% over all 700,
with no consistent pattern by complexity. So the multi-query mechanism carries
no free lunch, and any gain has to come from the quality of the split. That
rests entirely on a 3B model, which is where quality is least reliable.

Decompositions cache to disk, so scoring can be re-run and rewritten freely
without paying model time twice. Delete the cache file to force a re-run.

    python3 test_scripts/measure_decomposition.py            decompose, then score
    python3 test_scripts/measure_decomposition.py --score    score the cache only
"""

import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "test_scripts"))

from src.loader import load_claims
from src.run_loop import read_report, load_prompt_template
from src.ollama_client import call_ollama
from src.evidence_asserter import tokenize
import src.bm25_retriever as bm
from measure_recall import aggregate

CONFIG_PATH = REPO_ROOT / "configs" / "decompose_v1.json"
CACHE_PATH = REPO_ROOT / "results" / "decompositions_v1.json"
MIN_GOLD = 4      # the population with the deficit
TOP_K = 10

# A numbered line, tolerating "1." / "1)" / "1:" and leading whitespace or bullets.
_NUMBERED = re.compile(r"^\s*[-*]?\s*\d+\s*[.):]\s*(.+?)\s*$")


def parse_response(text):
    """Model response -> list of sub-claims. Never raises, may return [].

    Only numbered lines are taken, which drops preamble like "Sure! Here are
    the facts:" without needing to recognise it. Sub-claims shorter than three
    tokens are dropped: they cannot function as a retrieval query and would
    spend a slot in the round-robin on noise.
    """
    out = []
    for line in text.splitlines():
        match = _NUMBERED.match(line)
        if match:
            candidate = match.group(1).strip().strip("*").strip()
            if len(tokenize(candidate)) >= 3:
                out.append(candidate)
    return out[:5]


def decompose_all(claims, config):
    """Call the model once per claim, resuming from the cache."""
    CACHE_PATH.parent.mkdir(exist_ok=True)
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

    template = load_prompt_template(config["prompt_version"])
    todo = [c for c in claims if c.example_id not in cache]
    print(f"{len(claims)} claims, {len(cache)} cached, {len(todo)} to run", flush=True)

    started = time.time()
    for i, claim in enumerate(todo, start=1):
        prompt = template.replace("<STATEMENT>", claim.statement)
        try:
            response = call_ollama(prompt, config)
            text = response.get("response", "")
            cache[claim.example_id] = {
                "subclaims": parse_response(text),
                "raw": text,
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
                "done_reason": response.get("done_reason"),
            }
        except Exception as exc:
            # One failure must not end a 50-minute run.
            cache[claim.example_id] = {"subclaims": [], "error": repr(exc)}
            print(f"  [{i}/{len(todo)}] FAILED {claim.example_id}: {exc}", flush=True)

        # Written every claim, not at the end: a crash costs one claim.
        CACHE_PATH.write_text(json.dumps(cache, indent=1))

        if i % 10 == 0 or i == len(todo):
            elapsed = time.time() - started
            eta = (len(todo) - i) * elapsed / i
            print(f"  [{i}/{len(todo)}] elapsed {elapsed / 60:5.1f} min  "
                  f"eta {eta / 60:5.1f} min", flush=True)
    return cache


def rank_all(query, stats):
    """Full ranking of one report's elements against one query string."""
    tokens = set(tokenize(query))
    scored = sorted(((bm.score_element(tokens, i, stats), i)
                     for i in range(stats["n"])), key=lambda row: (-row[0], row[1]))
    return [index for _, index in scored]


def round_robin(lists, k, head=0):
    """Interleave ranked lists, taking each list's best first.

    Not RRF. RRF rewards agreement between lists, which is backwards here: if a
    claim needs facts A and B we want the A element AND the B element, so an
    element every sub-claim likes is the least interesting one.

    `head` reserves the first `head` slots for lists[0], the whole claim. With
    four lists and k=10, plain round-robin cuts the whole claim down to about
    three slots, which is a large bet on the sub-claims being good.
    """
    out = list(lists[0][:head])
    seen = set(out)
    depth = 0
    while len(out) < k and depth < max(len(l) for l in lists):
        for ranking in lists:
            if depth < len(ranking) and ranking[depth] not in seen and len(out) < k:
                seen.add(ranking[depth])
                out.append(ranking[depth])
        depth += 1
    return out


def main():
    score_only = "--score" in sys.argv
    config = json.loads(CONFIG_PATH.read_text())

    claims = [c for c in load_claims() if len(set(c.relevant_context)) >= MIN_GOLD]
    print(f"{len(claims)} claims needing >= {MIN_GOLD} gold elements")

    if score_only:
        cache = json.loads(CACHE_PATH.read_text())
    else:
        cache = decompose_all(claims, config)

    gold = {c.example_id: (c.subset, frozenset(c.relevant_context)) for c in claims}
    whole, plain_rr, head_rr, subs_only = {}, {}, {}, {}
    counts, empty = [], 0

    for claim in claims:
        entry = cache.get(claim.example_id, {})
        subclaims = entry.get("subclaims", [])
        counts.append(len(subclaims))
        if not subclaims:
            empty += 1

        stats = bm.report_stats(read_report(claim.report))
        whole_ranking = rank_all(claim.statement, stats)
        sub_rankings = [rank_all(s, stats) for s in subclaims]

        whole[claim.example_id] = whole_ranking[:TOP_K]
        # Fallback: no parsed sub-claims means the whole claim, never an empty list.
        lists = [whole_ranking] + sub_rankings
        plain_rr[claim.example_id] = round_robin(lists, TOP_K)
        head_rr[claim.example_id] = round_robin(lists, TOP_K, head=5)
        subs_only[claim.example_id] = round_robin(sub_rankings or [whole_ranking], TOP_K)

    print(f"\nsub-claims per claim: mean {sum(counts) / len(counts):.2f}, "
          f"{empty} claims parsed to nothing (fell back to the whole claim)")

    print(f"\n{'variant':<38} {'macro':>8} {'element':>9} {'all-gold':>9}")
    for label, retrievals in (("bm25, whole claim only", whole),
                              ("round-robin, whole + sub-claims", plain_rr),
                              ("round-robin, whole keeps top 5", head_rr),
                              ("round-robin, sub-claims only", subs_only)):
        m = aggregate(retrievals, gold)["overall"]
        print(f"{label:<38} {m['macro']:>7.2f}% {m['element']:>8.1f}% "
              f"{m['all_gold']:>8.1f}%")


if __name__ == "__main__":
    main()
