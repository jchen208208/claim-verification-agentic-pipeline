"""Does splitting the trigger by FAILURE TYPE beat escalating everything?

ie_audit_v3 already reports either a conflicting filing line (the claim states
something the filing contradicts) or NOT FOUND (the filing does not say).
Idea under test: flip the contradicted ones locally, escalate only the unfound ones.
No model calls.
"""
import json, re, sys
from math import comb
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ROWS = ROOT/"results"/"ie_analysis"/"target_rows.json"
D    = ROOT/"results"/"audit_full"/"ie_audit_v3_qwen2.5-coder-7b"

def mcnemar(b, c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0, sum(comb(n,i) for i in range(k+1))/(2**n)*2)

recs={json.load(open(p))["example_id"]: json.load(open(p)) for p in D.glob("*.json")}
rows=json.load(open(ROWS))
ALLOWED={"ie","numeric"}

def classify(r):
    """returns None (no fire), 'conflict' or 'not_found'"""
    if not re.search(r"\bUNCONFIRMED\b", r["response"]): return None
    m=re.search(r"FILING SAYS\s*:?\s*(.+)", r["response"], re.I)
    q=(m.group(1) if m else "").strip()
    if not q or re.match(r"^\W*NOT\s*FOUND", q, re.I): return "not_found"
    return "conflict"

fires={}
for x in rows:
    if x["target"] and x["subset"] in ALLOWED and x["id"] in recs:
        c=classify(recs[x["id"]])
        if c: fires[x["id"]]=c

print("THE MODEL'S OWN SPLIT, on all fired claims (ie+numeric)")
print(f"{'type':<12}{'n':>5}{'truly refuted':>15}{'precision':>11}")
for t in ("conflict","not_found"):
    ids=[i for i,v in fires.items() if v==t]
    w=sum(1 for i in ids if not next(x for x in rows if x["id"]==i)["gold"])
    print(f"  {t:<10}{len(ids):>5}{w:>15}{w/len(ids)*100 if ids else 0:>10.1f}%")
print(f"  {'TOTAL':<10}{len(fires):>5}")

def run(name, policy):
    """policy: id -> 'flip' | 'escalate' | 'keep'"""
    new=[]
    for x in rows:
        v=x["routed"]
        act=policy(x["id"])
        if act=="flip": v=False
        elif act=="escalate": v=x["cloud"]
        new.append(dict(x,new=v))
    base=sum(1 for x in rows if x["routed"]==x["gold"])/len(rows)*100
    now =sum(1 for x in new  if x["new"]==x["gold"])/len(new)*100
    b=sum(1 for x in new if x["new"]==x["gold"] and x["routed"]!=x["gold"])
    c=sum(1 for x in new if x["new"]!=x["gold"] and x["routed"]==x["gold"])
    calls=sum(1 for i in fires if policy(i)=="escalate")
    ie=[x for x in new if x["subset"]=="ie"]
    ie_a=sum(1 for x in ie if x["new"]==x["gold"])/len(ie)*100
    print(f"  {name:<38}{now:>7.1f}{now-base:>+7.1f}{b:>6}{c:>6}{mcnemar(b,c):>10.4f}"
          f"{calls:>8}{ie_a:>8.1f}")

print(f"\nPOLICIES. run 1 = 75.8%, cloud alone = 77.4%, FDV-IE run 1 = 77.5%")
print(f"  {'policy':<38}{'overall':>7}{'delta':>7}{'gain':>6}{'lose':>6}{'p':>10}"
      f"{'calls':>8}{'FDV-IE':>8}")
run("escalate everything that fires",  lambda i: "escalate" if i in fires else "keep")
run("flip conflict, escalate not_found",lambda i: ("flip" if fires[i]=="conflict"
                                                   else "escalate") if i in fires else "keep")
run("flip conflict, keep not_found",   lambda i: ("flip" if fires[i]=="conflict"
                                                   else "keep") if i in fires else "keep")
run("escalate conflict, keep not_found",lambda i: ("escalate" if fires[i]=="conflict"
                                                   else "keep") if i in fires else "keep")
run("flip everything that fires",      lambda i: "flip" if i in fires else "keep")
