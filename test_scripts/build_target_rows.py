"""Build the all-subset row cache: run 1's verdict, the paired cloud-alone verdict,
and the gate decision for every claim of test.json. No model calls."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
CLOUD  = ROOT/"results"/"condition2_flash_v2_test1700"
OUT    = ROOT/"results"/"ie_analysis"/"target_rows.json"

def load(d): return {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}

claims = {c.example_id: c for c in load_claims("test")}
r_, c_ = load(ROUTED), load(CLOUD)
rows = []
for cid, cl in claims.items():
    r = r_[cid]
    rows.append(dict(
        id=cid, subset=cl.subset, gold=cl.entailment_label,
        routed=r["extracted_label"], cloud=c_[cid]["extracted_label"],
        a=r["verdict_local_a"], b=r["verdict_local_b"],
        kept=not r["cloud_called"], reason=r["escalation_reason"],
        # the population the audit skill acts on
        target=(not r["cloud_called"]) and r["extracted_label"] is True,
    ))
OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump(rows, open(OUT, "w"))
t = [x for x in rows if x["target"]]
w = [x for x in t if x["gold"] is False]
print(f"{len(rows)} claims, {sum(1 for x in rows if x['kept'])} kept local, "
      f"{len(t)} target (kept + entailed), {len(w)} of those wrong")
for s in ("ie","numeric","knowledge"):
    ts=[x for x in t if x["subset"]==s]; ws=[x for x in ts if x["gold"] is False]
    print(f"  {s:<10} target {len(ts):>4}  wrong {len(ws):>3}  ({len(ws)/len(ts)*100:.1f}%)")
print(f"wrote {OUT.relative_to(ROOT)}")
