"""What does the routed pipeline score if the audit trigger is added?

Measured end to end on all 1,700 claims of test.json. A claim the audit fires on is
escalated, and its cloud verdict is taken from condition 2, which ran the same claims
with the same prompt (baseline_v2), model and config. That is an approximation to the
extent of run-to-run variance (paper_numbers 2.3.2, about one verdict in ten), and it
costs no new cloud calls.

Usage: python3 test_scripts/analyse_audit_full.py <tag> [rule]
  tag  e.g. ie_audit_v1_qwen2.5-coder-7b
"""
import json, re, sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT/"results"/"ie_analysis"/"target_rows.json"


def mcnemar(b, c):
    """exact two-sided binomial test on the discordant pairs"""
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k+1)) / (2**n) * 2
    return min(1.0, p)


def norm(s):
    s = s.lower().replace("’", "'")
    s = re.sub(r"[\"'*`]", "", s)
    return re.sub(r"\s+", " ", s).strip()


NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

def _variants(tok):
    bare = tok.replace(",", ""); out = {tok, bare}
    if "." in bare: out.add(bare.rstrip("0").rstrip("."))
    try: v = float(bare)
    except ValueError: return out
    for mult in (1, 1_000, 1_000_000):
        x = v*mult
        if x == int(x): out.add(str(int(x))); out.add(f"{int(x):,}")
    return {y for y in out if len(y) >= 2}


def number_absent(rec, full_text):
    """free check: the claim asserts a number that appears nowhere in the filing"""
    for m in NUM.finditer(rec["statement"]):
        tok = m.group(0); bare = tok.replace(",", "")
        try: v = float(bare)
        except ValueError: continue
        if "." not in bare and 1900 <= v <= 2100: continue
        if v < 2: continue
        if not any(x in full_text for x in _variants(tok)): return True
    return False


def fired(rec, rule):
    r = rec["response"]
    # v1/v2 fire on CONTRADICTED, v3 fires on UNCONFIRMED
    has = bool(re.search(r"\bCONTRADICTED\b|\bUNCONFIRMED\b", r))
    if rule == "raw":
        return has
    if rule == "union":
        return has or rec.get("_numabs", False)
    if rule == "quote_guard":
        m = re.search(r"FILING SAYS\s*:?\s*(.+)", r, re.I)
        q = norm(m.group(1)) if m else ""
        return has and len(q) >= 12 and (q in norm(rec["evidence"])
                                         or (len(q) > 40 and q[:40] in norm(rec["evidence"])))
    raise ValueError(rule)


def acc(rows, key):
    return sum(1 for x in rows if x[key] == x["gold"]) / len(rows) * 100


def main():
    tag  = sys.argv[1]
    rule = sys.argv[2] if len(sys.argv) > 2 else "raw"
    # subsets the trigger is allowed to fire on. FDV-KNOW is excluded by default:
    # escalating it is net negative on BOTH splits (working_state, 28 Aug late).
    allowed = set((sys.argv[3] if len(sys.argv) > 3 else "ie,numeric").split(","))
    d = ROOT/"results"/"audit_full"/tag
    recs = {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}
    if rule == "union":
        sys.path.insert(0, str(ROOT))
        from src.loader import load_claims
        from src.run_loop import read_report
        cl = {c.example_id: c for c in load_claims("test")}
        cache = {}
        for cid, r in recs.items():
            fn = cl[cid].report
            if fn not in cache:
                cache[fn] = " ".join(e["context"] for e in read_report(fn)["context"])
            r["_numabs"] = number_absent(r, cache[fn])
    rows = json.load(open(ROWS))
    target = [x for x in rows if x["target"]]
    covered = [x for x in target if x["id"] in recs]
    print(f"tag={tag}  rule={rule}")
    print(f"target population {len(target)}, audited {len(covered)}")
    if len(covered) < len(target):
        print(f"  WARNING: {len(target)-len(covered)} not yet run, numbers below are partial")

    fire = {x["id"] for x in covered
            if x["subset"] in allowed and fired(recs[x["id"]], rule)}
    print(f"trigger allowed on: {','.join(sorted(allowed))}")
    tp = [x for x in covered if x["id"] in fire and x["gold"] is False]
    fp = [x for x in covered if x["id"] in fire and x["gold"] is True]
    elig = [x for x in covered if x["subset"] in allowed]
    nw = sum(1 for x in elig if x["gold"] is False)
    nr = len(elig) - nw
    print(f"\nDETECTOR, exact on the real population")
    print(f"  fires {len(fire)}   catches {len(tp)}/{nw}   breaks {len(fp)}/{nr}")
    print(f"  recall {len(tp)/nw*100:.1f}%   false-positive rate {len(fp)/nr*100:.1f}%   "
          f"precision {len(tp)/len(fire)*100 if fire else 0:.1f}%")

    # rebuild the pipeline two ways
    for mode in ("escalate", "flip"):
        new = []
        for x in rows:
            v = x["routed"]
            if x["id"] in fire:
                v = x["cloud"] if mode == "escalate" else False
            new.append(dict(x, new=v))
        base = acc(rows, "routed"); now = acc(new, "new")
        b = sum(1 for x in new if x["new"] == x["gold"] and x["routed"] != x["gold"])
        c = sum(1 for x in new if x["new"] != x["gold"] and x["routed"] == x["gold"])
        print(f"\n=== MODE: {mode.upper()} ===")
        print(f"  routed  {base:.1f}%  ->  {now:.1f}%   ({now-base:+.1f})   "
              f"McNemar vs run 1: {b} gained, {c} lost, p={mcnemar(b,c):.4f}")
        if mode == "escalate":
            print(f"  extra cloud calls {len(fire)} on top of 908 = "
                  f"{(908+len(fire))/1700*100:.1f}% of claims escalated "
                  f"(was 53.4%), {len(fire)/1700*100:+.1f} points")
        cl = acc(rows, "cloud")
        b2 = sum(1 for x in new if x["new"] == x["gold"] and x["cloud"] != x["gold"])
        c2 = sum(1 for x in new if x["new"] != x["gold"] and x["cloud"] == x["gold"])
        print(f"  vs cloud alone {cl:.1f}%: {b2} we win, {c2} cloud wins, p={mcnemar(b2,c2):.4f}")
        print(f"  {'subset':<11}{'run 1':>8}{'new':>8}{'delta':>8}{'cloud':>8}")
        for s in ("ie", "numeric", "knowledge"):
            o = [x for x in rows if x["subset"] == s]
            n_ = [x for x in new if x["subset"] == s]
            print(f"  {s:<11}{acc(o,'routed'):>8.1f}{acc(n_,'new'):>8.1f}"
                  f"{acc(n_,'new')-acc(o,'routed'):>+8.1f}{acc(o,'cloud'):>8.1f}")


if __name__ == "__main__":
    main()
