"""Can the audit skill work with NO cloud escalation, by raising precision enough
to flip verdicts on device? Three free precision filters, no model calls.

  A. intersect with the free number-absence check
  B. mechanically verify the alleged contradiction from the model's own two quotes
  C. require a short, localised claim part rather than the whole sentence
"""
import json, re, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.loader import load_claims
from src.run_loop import read_report

D=ROOT/"results"/"audit_full"/"ie_audit_v3_qwen2.5-coder-7b"
rows={x["id"]:x for x in json.load(open(ROOT/"results"/"ie_analysis"/"target_rows.json"))}
recs={json.load(open(p))["example_id"]:json.load(open(p)) for p in D.glob("*.json")}
ALLOWED={"ie","numeric"}

def mcnemar(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)

NUM=re.compile(r"\d[\d,]*(?:\.\d+)?")
UP=re.compile(r"\b(increas\w*|rose|rise|grew|growth|higher|gain\w*|up)\b",re.I)
DOWN=re.compile(r"\b(decreas\w*|fell|fall\w*|declin\w*|drop\w*|lower|loss|down|reduc\w*)\b",re.I)

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

def quoted(r,tag):
    m=re.search(rf"{tag}\s*:?\s*(.+)",r,re.I); return m.group(1).strip() if m else ""

def fires(r): return bool(re.search(r"\bUNCONFIRMED\b",r["response"]))

# free number-absence, per claim
def variants(tok):
    bare=tok.replace(",",""); out={tok,bare}
    if "." in bare: out.add(bare.rstrip("0").rstrip("."))
    try: v=float(bare)
    except ValueError: return out
    for m in (1,1000,1000000):
        x=v*m
        if x==int(x): out.add(str(int(x))); out.add(f"{int(x):,}")
    return {y for y in out if len(y)>=2}

cl={c.example_id:c for c in load_claims("test")}
cache={}
def num_absent(cid,stmt):
    fn=cl[cid].report
    if fn not in cache: cache[fn]=" ".join(e["context"] for e in read_report(fn)["context"])
    full=cache[fn]
    for m in NUM.finditer(stmt):
        tok=m.group(0); b=tok.replace(",","")
        try: v=float(b)
        except ValueError: continue
        if "." not in b and 1900<=v<=2100: continue
        if v<2: continue
        if not any(x in full for x in variants(tok)): return True
    return False

def mech_conflict(r):
    """do the model's own two quotes actually disagree?"""
    cp,fs=quoted(r["response"],"CLAIM PART"),quoted(r["response"],"FILING SAYS")
    if not cp or not fs or re.match(r"^\W*NOT\s*FOUND",fs,re.I): return False
    a,b=nums(cp),nums(fs)
    if a and b and not (a & b): return True          # different figures
    ca,cb=(bool(UP.search(cp)),bool(DOWN.search(cp)))
    da,db=(bool(UP.search(fs)),bool(DOWN.search(fs)))
    if (ca and db and not da) or (cb and da and not db): return True   # opposite direction
    return False

pop=[x for x in rows.values() if x["target"] and x["subset"] in ALLOWED and x["id"] in recs]
F=[x for x in pop if fires(recs[x["id"]])]
print(f"population {len(pop)}  fires {len(F)}  of which truly refuted "
      f"{sum(1 for x in F if x['gold'] is False)}")

def report(name,keep):
    sel=[x for x in F if keep(x)]
    if not sel: print(f"  {name:<44} 0 fires"); return
    tp=sum(1 for x in sel if x["gold"] is False); fp=len(sel)-tp
    p=tp/len(sel)*100
    # FLIP only, no cloud at all
    b,c=tp,fp
    allr=list(rows.values())
    base=sum(1 for x in allr if x["routed"]==x["gold"])
    now=base+tp-fp
    ie=[x for x in allr if x["subset"]=="ie"]
    ie_base=sum(1 for x in ie if x["routed"]==x["gold"])
    ie_d=sum(1 for x in sel if x["subset"]=="ie" and x["gold"] is False)-\
         sum(1 for x in sel if x["subset"]=="ie" and x["gold"] is True)
    print(f"  {name:<44}{len(sel):>6}{p:>9.1f}%{tp:>6}{fp:>6}{now/1700*100:>9.1f}"
          f"{(now-base)/1700*100:>+7.1f}{mcnemar(b,c):>9.4f}{(ie_base+ie_d)/600*100:>8.1f}")

print(f"\nLOCAL-ONLY, FLIP THE VERDICT, NO CLOUD CALLS. run 1 = 75.8%, FDV-IE 77.5%")
print(f"  {'precision filter':<44}{'fires':>6}{'prec':>10}{'gain':>6}{'lose':>6}"
      f"{'overall':>9}{'delta':>7}{'p':>9}{'FDV-IE':>8}")
report("none (v3 raw)", lambda x: True)
report("A. AND free number-absence", lambda x: num_absent(x["id"],recs[x["id"]]["statement"]))
report("B. quotes mechanically disagree", lambda x: mech_conflict(recs[x["id"]]))
report("A or B", lambda x: num_absent(x["id"],recs[x["id"]]["statement"]) or mech_conflict(recs[x["id"]]))
report("A and B", lambda x: num_absent(x["id"],recs[x["id"]]["statement"]) and mech_conflict(recs[x["id"]]))
report("C. claim part <= 12 words", lambda x: 0<len(quoted(recs[x["id"]]["response"],"CLAIM PART").split())<=12)
report("B and C", lambda x: mech_conflict(recs[x["id"]]) and 0<len(quoted(recs[x["id"]]["response"],"CLAIM PART").split())<=12)
