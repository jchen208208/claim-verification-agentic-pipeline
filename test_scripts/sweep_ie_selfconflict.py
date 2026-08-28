"""Sweep 5: does the local model already state the contradicting value in its own response?

The §2.19 failure shape: the model finds the right number, then calls it equal to the
claimed one. If so, a free comparison of numbers-in-claim against numbers-in-response
detects the refutation with no extra model call.
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims
ROUTED = ROOT/"results"/"condition4_pipeline_test1700"

claims={c.example_id:c for c in load_claims("test") if c.subset=="ie"}
rows=[x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))
      if x["kept_local"] and x["routed"] is True]

NUM=re.compile(r"\d[\d,]*(?:\.\d+)?")
def nums(t):
    out=set()
    for m in NUM.finditer(t):
        b=m.group(0).replace(",","")
        try: v=float(b)
        except ValueError: continue
        if "." not in b and 1900<=v<=2100: continue
        if v<2: continue
        out.add(v)
    return out

def near(a,b):
    """same order of magnitude and within 20%: a plausible 'the real figure' pair"""
    if a==0 or b==0: return False
    r=max(a,b)/min(a,b)
    return 1.0001 < r < 1.25

out=[]
for x in rows:
    r=json.load(open(ROUTED/f"{x['id']}.json"))
    c=claims[x["id"]]
    cn=nums(c.statement)
    ra=nums(r["stages"]["local_a"]["response"]); rb=nums(r["stages"]["local_b"]["response"])
    # a claim number the model never repeats, but a *near* value it does state
    def conflicts(rn):
        hits=[]
        for v in cn:
            if v in rn: continue
            for w in rn:
                if near(v,w): hits.append((v,w)); break
        return hits
    ca,cb=conflicts(ra),conflicts(rb)
    unmentioned_a=[v for v in cn if v not in ra]
    out.append(dict(x, conf_a=len(ca),conf_b=len(cb),
                    conf_either=len(ca)+len(cb), conf_both=min(len(ca),len(cb)),
                    unment_a=len(unmentioned_a), n_claimnums=len(cn),
                    ex=(ca[:2] or cb[:2])))

def rule(name,pred):
    f=[x for x in out if pred(x)]
    tp=sum(1 for x in f if x["gold"] is False); fp=len(f)-tp
    tot=sum(1 for x in out if x["gold"] is False)
    print(f"  {name:<44} fires {len(f):>3}  catches {tp:>3}/{tot}  breaks {fp:>3}  "
          f"prec {tp/len(f)*100 if f else 0:>5.1f}%  rec {tp/tot*100:>5.1f}%  net {tp-fp:+d}")

print("population n=213 (55 wrong, 158 right)")
print("SELF-CONFLICT RULES")
rule("3B states a near-miss value for a claim number", lambda x:x["conf_a"]>=1)
rule("7B states a near-miss value",                    lambda x:x["conf_b"]>=1)
rule("either model does",                              lambda x:x["conf_either"]>=1)
rule("both models do",                                 lambda x:x["conf_both"]>=1)
rule("2+ near-misses from either",                     lambda x:x["conf_either"]>=2)
print("COVERAGE RULES")
rule("3B never repeats 1+ claim number",               lambda x:x["unment_a"]>=1)
rule("3B never repeats 2+ claim numbers",              lambda x:x["unment_a"]>=2)
rule("claim has no numbers at all",                    lambda x:x["n_claimnums"]==0)

print("\nCOMBINED with the filing-absence rule from sweep 3")
numsig={x["id"]:x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_numsig.json"))}
rule("filing-absence OR self-conflict",
     lambda x: numsig[x["id"]]["miss_full"]>=1 or x["conf_either"]>=1)
rule("filing-absence only (sweep 3 best)", lambda x: numsig[x["id"]]["miss_full"]>=1)

print("\nEXAMPLES, self-conflict fired on a gold-refuted claim (claimed -> model said)")
for x in [y for y in out if y["gold"] is False and y["conf_either"]>=1][:5]:
    print(f"  {x['id']:<14} {x['ex']}")
