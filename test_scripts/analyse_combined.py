"""The whole system: run 1, plus each new component, plus both, against cloud alone.

The two components act on disjoint claim sets, so they compose:
  audit trigger  fires on claims the gate KEPT (locals agreed) whose verdict is entailed
  arbiter        fires on claims where the locals DISAGREED and the numeric detector is silent
No cloud calls. Newly escalated claims reuse condition 2's verdict on the same claim
(same prompt, model and config), an approximation worth about one verdict in ten.
"""
import json, re, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.loader import load_claims
from src.run_loop import read_report
from src.numeric_detector import is_numeric_claim

import os
ALLOW=None if os.environ.get("AUDIT_ALL") else ("ie","numeric")
R=ROOT/"results"/"condition4_pipeline_test1700"
AUD=ROOT/"results"/"audit_full"/"ie_audit_v3_qwen2.5-coder-7b"
ARB=ROOT/"results"/"arbiter"/"arbiter_v1_qwen2.5-coder-7b"

def mc(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)

rows={x["id"]:x for x in json.load(open(ROOT/"results"/"ie_analysis"/"target_rows.json"))}
aud={json.load(open(p))["example_id"]:json.load(open(p)) for p in AUD.glob("*.json")}
arb={json.load(open(p))["example_id"]:json.load(open(p)) for p in ARB.glob("*.json")}
cl={c.example_id:c for c in load_claims("test")}
raw={json.load(open(p))["example_id"]:json.load(open(p)) for p in R.glob("*.json")}

NUM=re.compile(r"\d[\d,]*(?:\.\d+)?")
def _var(t):
    b=t.replace(",",""); o={t,b}
    if "." in b: o.add(b.rstrip("0").rstrip("."))
    try: v=float(b)
    except ValueError: return o
    for m in (1,1000,1000000):
        x=v*m
        if x==int(x): o.add(str(int(x))); o.add(f"{int(x):,}")
    return {y for y in o if len(y)>=2}
cache={}
def num_absent(cid,st):
    fn=cl[cid].report
    if fn not in cache: cache[fn]=" ".join(e["context"] for e in read_report(fn)["context"])
    for m in NUM.finditer(st):
        t=m.group(0); b=t.replace(",","")
        try: v=float(b)
        except ValueError: continue
        if "." not in b and 1900<=v<=2100: continue
        if v<2: continue
        if not any(x in cache[fn] for x in _var(t)): return True
    return False

def av(t):
    m=re.search(r"VERDICT\s*:?\s*(REFUTED|ENTAILED)",t,re.I)
    if m: return m.group(1).upper()=="ENTAILED"
    if re.search(r"^\s*REFUTED\b",t,re.I|re.M): return False
    if re.search(r"^\s*ENTAILED\b",t,re.I|re.M): return True
    hr=bool(re.search(r"\bREFUTED\b",t,re.I)); he=bool(re.search(r"\bENTAILED\b",t,re.I))
    if hr!=he: return he
    return None

def build(use_audit, use_arb):
    out=[]; calls=0
    for cid,x in rows.items():
        r=raw[cid]; v=x["routed"]; called=r["cloud_called"]
        if use_audit and x["target"] and (ALLOW is None or x["subset"] in ALLOW) and cid in aud:
            fired = re.search(r"\bUNCONFIRMED\b",aud[cid]["response"]) or \
                    num_absent(cid,aud[cid]["statement"])
            if fired: v=x["cloud"]; called=True
        if use_arb and cid in arb:
            a=arb[cid]
            if not is_numeric_claim(a["statement"]):
                vv=av(a["response"])
                if vv is not None and vv==a["b"]:
                    v=a["b"]; called=False        # kept on device, cloud call removed
        out.append(dict(x,new=v)); calls+=called
    return out,calls

def show(name,rowsx,calls):
    ok=sum(1 for x in rowsx if x["new"]==x["gold"])
    cl_ok=sum(1 for x in rowsx if x["cloud"]==x["gold"])
    b=sum(1 for x in rowsx if x["new"]==x["gold"] and x["cloud"]!=x["gold"])
    c=sum(1 for x in rowsx if x["new"]!=x["gold"] and x["cloud"]==x["gold"])
    per=[]
    for s in ("ie","numeric","knowledge"):
        sub=[x for x in rowsx if x["subset"]==s]
        per.append(sum(1 for x in sub if x["new"]==x["gold"])/len(sub)*100)
    print(f"  {name:<34}{ok/1700*100:>7.1f}{per[0]:>8.1f}{per[1]:>8.1f}{per[2]:>8.1f}"
          f"{calls:>8}{calls/1700*100:>8.1f}{mc(b,c):>9.4f}")

print("test.json, n=1,700.  p is paired McNemar against CLOUD ALONE (77.4%).")
print(f"  {'system':<34}{'overall':>7}{'FDV-IE':>8}{'MATH':>8}{'KNOW':>8}{'calls':>8}{'%esc':>8}{'p vs cloud':>9}")
base,_=build(False,False)
show("run 1, as published",base,908)
a,ca=build(True,False);  show("+ audit trigger",a,ca)
b_,cb=build(False,True);  show("+ arbiter",b_,cb)
c_,cc=build(True,True);   show("+ both",c_,cc)
cl_rows=[dict(x,new=x["cloud"]) for x in rows.values()]
show("cloud alone",cl_rows,1700)
