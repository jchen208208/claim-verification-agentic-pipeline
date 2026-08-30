"""The same two components on testmini, the split the design was not selected on.

The routed pipeline never ran on testmini, so the gate is reconstructed from the three
arms on disk (2.24). Same prompts, same rules, nothing re-tuned. No cloud calls.
"""
import json, re, glob, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.loader import load_claims
from src.run_loop import read_report
from src.numeric_detector import is_numeric_claim

def mc(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)
def av(t):
    m=re.search(r"VERDICT\s*:?\s*(REFUTED|ENTAILED)",t,re.I)
    if m: return m.group(1).upper()=="ENTAILED"
    if re.search(r"^\s*REFUTED\b",t,re.I|re.M): return False
    if re.search(r"^\s*ENTAILED\b",t,re.I|re.M): return True
    hr=bool(re.search(r"\bREFUTED\b",t,re.I)); he=bool(re.search(r"\bENTAILED\b",t,re.I))
    if hr!=he: return he
    return None

rows=json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows_testmini.json"))
arb={json.load(open(p))["example_id"]:json.load(open(p))
     for p in glob.glob(str(ROOT/"results"/"arbiter_testmini"/"arbiter_v1_qwen2.5-coder-7b"/"*.json"))}
aud={json.load(open(p))["example_id"]:json.load(open(p))
     for p in glob.glob(str(ROOT/"results"/"audit_testmini"/"ie_audit_v3_qwen2.5-coder-7b"/"*.json"))}
cl={c.example_id:c for c in load_claims("testmini")}

NUM=re.compile(r"\d[\d,]*(?:\.\d+)?")
def _v(t):
    b=t.replace(",",""); o={t,b}
    if "." in b: o.add(b.rstrip("0").rstrip("."))
    try: x=float(b)
    except ValueError: return o
    for m in (1,1000,1000000):
        y=x*m
        if y==int(y): o.add(str(int(y))); o.add(f"{int(y):,}")
    return {z for z in o if len(z)>=2}
cache={}
def num_absent(cid,st):
    fn=cl[cid].report
    if fn not in cache: cache[fn]=" ".join(e["context"] for e in read_report(fn)["context"])
    for m in NUM.finditer(st):
        t=m.group(0); b=t.replace(",","")
        try: x=float(b)
        except ValueError: continue
        if "." not in b and 1900<=x<=2100: continue
        if x<2: continue
        if not any(z in cache[fn] for z in _v(t)): return True
    return False

# base escalation: numeric detector fires, or the locals disagree
def base_called(x): return is_numeric_claim(cl[x["id"]].statement) or x["a"]!=x["b"]

def build(use_audit,use_arb):
    out=[];calls=0
    for x in rows:
        v=x["routed"]; called=base_called(x)
        if use_audit and x["kept"] and x["routed"] is True and x["subset"] in ("ie","numeric") \
           and x["id"] in aud:
            if re.search(r"\bUNCONFIRMED\b",aud[x["id"]]["response"]) or \
               num_absent(x["id"],aud[x["id"]]["statement"]):
                v=x["cloud"]; called=True
        if use_arb and x["id"] in arb:
            a=arb[x["id"]]; vv=av(a["response"])
            if vv is not None and vv==x["b"]:
                v=x["b"]; called=False
        out.append(dict(x,new=v)); calls+=called
    return out,calls

def show(name,rs,calls):
    N=len(rs); ok=sum(1 for x in rs if x["new"]==x["gold"])
    b=sum(1 for x in rs if x["new"]==x["gold"] and x["cloud"]!=x["gold"])
    c=sum(1 for x in rs if x["new"]!=x["gold"] and x["cloud"]==x["gold"])
    per=[sum(1 for x in rs if x["subset"]==s and x["new"]==x["gold"])/
         sum(1 for x in rs if x["subset"]==s)*100 for s in ("ie","numeric","knowledge")]
    print(f"  {name:<34}{ok/N*100:>7.1f}{per[0]:>8.1f}{per[1]:>8.1f}{per[2]:>8.1f}"
          f"{calls:>8}{calls/N*100:>8.1f}{mc(b,c):>9.4f}")

print("testmini, n=700, reconstructed gate.  p is paired McNemar vs CLOUD ALONE.")
print(f"  {'system':<34}{'overall':>7}{'FDV-IE':>8}{'MATH':>8}{'KNOW':>8}{'calls':>8}{'%esc':>8}{'p vs cloud':>9}")
b0,c0=build(False,False); show("reconstructed run 1",b0,c0)
a,ca=build(True,False);   show("+ audit trigger",a,ca)
b_,cb=build(False,True);  show("+ arbiter",b_,cb)
c_,cc=build(True,True);   show("+ both",c_,cc)
show("cloud alone",[dict(x,new=x["cloud"]) for x in rows],700)
