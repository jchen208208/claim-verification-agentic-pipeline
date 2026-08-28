"""Sweep 3: can a free string check separate wrong-entailed IE claims from right ones?

Idea under test: FDV-IE refuted claims alter exactly one conjunct. When the altered
conjunct is a number, the asserted number appears nowhere in the filing.
No model calls. Pure string work over data already on disk.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims
from src.run_loop import read_report

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

def variants(tok):
    """surface forms the same magnitude could be written as in a filing"""
    bare = tok.replace(",", "")
    out = {tok, bare}
    if "." in bare:
        out.add(bare.rstrip("0").rstrip("."))
    try:
        v = float(bare)
    except ValueError:
        return out
    # 8.5 million -> 8,500 / 8500 ; 1,768 million -> 1768
    for mult in (1, 1_000, 1_000_000):
        s = v * mult
        if s == int(s):
            i = int(s)
            out.add(str(i)); out.add(f"{i:,}")
    return {x for x in out if len(x) >= 2}

def claim_numbers(text):
    """numbers in the claim, skipping bare years and tiny integers"""
    out = []
    for m in NUM.finditer(text):
        tok = m.group(0)
        bare = tok.replace(",", "")
        try: v = float(bare)
        except ValueError: continue
        if "." not in bare and 1900 <= v <= 2100:  # a year
            continue
        if v < 2:                                   # "one of", "1.5" kept, "1" dropped
            continue
        out.append(tok)
    return out

def main():
    claims = {c.example_id: c for c in load_claims("test") if c.subset == "ie"}
    rows = json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))
    rows = [x for x in rows if x["kept_local"] and x["routed"] is True]
    print(f"population: kept-local FDV-IE claims the routed system called ENTAILED, n={len(rows)}")
    print(f"  gold entailed (must keep) {sum(1 for x in rows if x['gold'] is True)}")
    print(f"  gold refuted  (must flip) {sum(1 for x in rows if x['gold'] is False)}\n")

    report_cache = {}
    out = []
    for x in rows:
        c = claims[x["id"]]
        if c.report not in report_cache:
            rep = read_report(c.report)
            report_cache[c.report] = " ".join(e["context"] for e in rep["context"])
        full = report_cache[c.report]
        prompt = json.load(open(ROUTED/f"{x['id']}.json"))["stages"]["local_a"]["prompt"]

        nums = claim_numbers(c.statement)
        miss_full = [n for n in nums if not any(v in full for v in variants(n))]
        miss_ret  = [n for n in nums if not any(v in prompt for v in variants(n))]
        out.append(dict(x, n_nums=len(nums), miss_full=len(miss_full),
                        miss_ret=len(miss_ret), missed=miss_full))

    def report(name, pred):
        fired = [x for x in out if pred(x)]
        tp = sum(1 for x in fired if x["gold"] is False)   # correctly caught a refuted claim
        fp = sum(1 for x in fired if x["gold"] is True)    # would wrongly flip a true claim
        tot_r = sum(1 for x in out if x["gold"] is False)
        prec = tp/len(fired)*100 if fired else 0
        rec = tp/tot_r*100 if tot_r else 0
        # net verdicts gained if we flipped every fired claim
        print(f"  {name:<42} fires {len(fired):>3}   catches {tp:>3}/{tot_r}  "
              f"breaks {fp:>3}   precision {prec:>5.1f}%  recall {rec:>5.1f}%   net {tp-fp:+d}")

    print("DETECTOR RULES (fire = predict this 'entailed' verdict is wrong)")
    print(f"  {'baseline: flip everything':<42} fires {len(out):>3}   "
          f"catches {sum(1 for x in out if x['gold'] is False)}/"
          f"{sum(1 for x in out if x['gold'] is False)}  "
          f"breaks {sum(1 for x in out if x['gold'] is True):>3}   "
          f"precision {sum(1 for x in out if x['gold'] is False)/len(out)*100:>5.1f}%  "
          f"recall 100.0%   net "
          f"{sum(1 for x in out if x['gold'] is False)-sum(1 for x in out if x['gold'] is True):+d}")
    report("a claim number missing from whole filing", lambda x: x["miss_full"] >= 1)
    report("2+ claim numbers missing from filing",     lambda x: x["miss_full"] >= 2)
    report("a claim number missing from retrieved",    lambda x: x["miss_ret"] >= 1)
    report("missing from filing AND claim has 2+ nums",lambda x: x["miss_full"] >= 1 and x["n_nums"] >= 2)

    print("\nHOW MANY OF THESE CLAIMS CONTAIN ANY NUMBER AT ALL?")
    print("  ", Counter(("has numbers" if x["n_nums"] else "no numbers") for x in out))
    for g in (False, True):
        sub=[x for x in out if x["gold"] is g]
        wn=[x for x in sub if x["n_nums"]]
        print(f"   gold={str(g):<5} n={len(sub):>3}  with numbers {len(wn)} ({len(wn)/len(sub)*100:.0f}%)")

    print("\nCEILING IF THE RULE ONLY APPLIED TO NUMBER-BEARING CLAIMS")
    sub=[x for x in out if x["n_nums"]]
    tp=sum(1 for x in sub if x["gold"] is False and x["miss_full"]>=1)
    fp=sum(1 for x in sub if x["gold"] is True and x["miss_full"]>=1)
    print(f"  among {len(sub)} number-bearing: catches {tp}, breaks {fp}")

    print("\nEXAMPLES THE RULE CAUGHT (gold refuted, fired)")
    for x in [y for y in out if y["gold"] is False and y["miss_full"]>=1][:4]:
        print(f"  {x['id']:<14} missing {x['missed']}")
        print(f"     {claims[x['id']].statement[:150]}")
    print("\nEXAMPLES THE RULE BROKE (gold entailed, fired)")
    for x in [y for y in out if y["gold"] is True and y["miss_full"]>=1][:4]:
        print(f"  {x['id']:<14} missing {x['missed']}")
        print(f"     {claims[x['id']].statement[:150]}")

    json.dump(out, open(ROOT/"results"/"ie_analysis"/"ie_numsig.json","w"))

if __name__ == "__main__":
    main()
