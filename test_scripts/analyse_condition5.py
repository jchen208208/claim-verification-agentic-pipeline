"""Condition 5: the routed pipeline with the audit trigger and the arbiter, run for real.

Every earlier figure for these two components (paper_numbers sections 2.26 to 2.30) was a
simulation: run 1's records, plus the components' verdicts from separate test-script runs,
with a newly escalated claim REUSING condition 2's cloud verdict instead of making a call.
This run makes the calls. Its job is to confirm or refute that simulation.

Reproduce: python3 test_scripts/analyse_condition5.py
"""
import json, sys, statistics as st, re
from math import comb
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

C5    = ROOT/"results"/"condition5_audit_arbiter_test1700"
RUN1  = ROOT/"results"/"condition4_pipeline_test1700"
CLOUD = ROOT/"results"/"condition2_flash_v2_test1700"

def mc(b, c):
    """Exact two-sided McNemar. b = we right / they wrong, c = the reverse."""
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, sum(comb(n, i) for i in range(k+1)) / (2**n) * 2)

def load(d):
    return {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}

c5, r1, cloud = load(C5), load(RUN1), load(CLOUD)
ids = sorted(c5)
assert len(ids) == 1700, len(ids)
assert set(ids) == set(r1) == set(cloud), "the three runs cover different claims"

def subset(i): return i.split("-")[0]
SUBS = ("ie", "numeric", "knowledge")
NAME = {"ie": "FDV-IE", "numeric": "MATH", "knowledge": "KNOW"}

def acc(pred, sub=None):
    xs = [i for i in ids if sub is None or subset(i) == sub]
    return sum(1 for i in xs if pred[i] == c5[i]["gold_label"]) / len(xs) * 100

def verdicts(run): return {i: run[i]["extracted_label"] for i in ids}

V5, V1, VC = verdicts(c5), verdicts(r1), verdicts(cloud)
calls5 = sum(1 for i in ids if c5[i]["cloud_called"])
calls1 = sum(1 for i in ids if r1[i]["cloud_called"])

def row(label, V, calls, ref):
    g = lambda i: c5[i]["gold_label"]
    b = sum(1 for i in ids if V[i] == g(i) and ref[i] != g(i))
    c = sum(1 for i in ids if V[i] != g(i) and ref[i] == g(i))
    per = "".join(f"{acc(V, s):>8.1f}" for s in SUBS)
    print(f"  {label:<30}{acc(V):>7.1f}{per}{calls:>8}{calls/17:>8.1f}"
          f"{mc(b,c):>10.4f}{b:>6}{c:>6}")

print("=" * 96)
print("CONDITION 5, MEASURED. test.json, n=1,700. Strict scoring, unparseable counts wrong.")
print("=" * 96)
hdr = f"  {'system':<30}{'overall':>7}{'FDV-IE':>8}{'MATH':>8}{'KNOW':>8}{'calls':>8}{'%esc':>8}"
print(hdr + f"{'p vs cloud':>10}{'win':>6}{'loss':>6}")
row("run 1, measured", V1, calls1, VC)
row("condition 5, measured", V5, calls5, VC)
row("cloud alone, measured", VC, 1700, VC)

print()
print("  Against run 1 rather than against cloud alone:")
g = lambda i: c5[i]["gold_label"]
b = sum(1 for i in ids if V5[i] == g(i) and V1[i] != g(i))
c = sum(1 for i in ids if V5[i] != g(i) and V1[i] == g(i))
print(f"    condition 5 vs run 1     net {b-c:+d}   won {b}  lost {c}   p = {mc(b,c):.4f}")

print()
print("  What the simulation predicted (paper_numbers 2.30) against what was measured:")
print(f"    {'':22}{'predicted':>11}{'measured':>10}{'delta':>8}")
for nm, pred, meas in (("overall accuracy", 76.9, acc(V5)),
                       ("FDV-IE", 79.3, acc(V5, "ie")),
                       ("MATH", 78.0, acc(V5, "numeric")),
                       ("KNOW", 72.6, acc(V5, "knowledge")),
                       ("cloud calls", 719, calls5),
                       ("escalation %", 42.3, calls5/17)):
    print(f"    {nm:<22}{pred:>11.1f}{meas:>10.1f}{meas-pred:>+8.1f}")

print()
print("  Escalation reasons, condition 5:")
reasons = {}
for i in ids:
    reasons[c5[i]["escalation_reason"]] = reasons.get(c5[i]["escalation_reason"], 0) + 1
for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
    print(f"    {str(k):<22}{v:>6}{v/17:>8.1f}%")

print()
print("  The two components, as they actually fired:")
af = [i for i in ids if c5[i]["audit_fired"] is not None]
fired = [i for i in af if c5[i]["audit_fired"]]
print(f"    audit ran on            {len(af):>6} claims (locals agreed on entailed)")
print(f"    audit fired             {len(fired):>6} = {len(fired)/max(len(af),1)*100:.1f}% of those, each one a cloud call added")
if fired:
    print(f"      of the ones it fired on, the cloud was right on {sum(1 for i in fired if V5[i]==g(i))/len(fired)*100:.1f}%")
    kept = [i for i in af if not c5[i]['audit_fired']]
    print(f"      of the ones it passed,   the local was right on {sum(1 for i in kept if V5[i]==g(i))/len(kept)*100:.1f}%")

ar = [i for i in ids if c5[i]["arbiter_verdict"] is not None or (c5[i].get("arbiter_detail") or {})]
ran = [i for i in ids if c5[i].get("arbiter_detail")]
sided7 = [i for i in ran if c5[i]["arbiter_verdict"] is not None
          and c5[i]["arbiter_verdict"] == c5[i]["verdict_local_b"]]
sided3 = [i for i in ran if c5[i]["arbiter_verdict"] is not None and i not in sided7]
unread = [i for i in ran if c5[i]["arbiter_verdict"] is None]
print(f"    arbiter ran on          {len(ran):>6} claims (locals disagreed, not numeric)")
print(f"    sided with the 7B       {len(sided7):>6}  kept local, cloud call removed")
if sided7:
    print(f"      local was right on {sum(1 for i in sided7 if V5[i]==g(i))/len(sided7)*100:.1f}% of those")
print(f"    sided with the 3B       {len(sided3):>6}  escalated")
print(f"    unreadable answer       {len(unread):>6}  escalated")

print()
unp = lambda V: sum(1 for i in ids if V[i] is None) / 17
print(f"  Unparseable, strict:  condition 5 {unp(V5):.2f}%   run 1 {unp(V1):.2f}%   cloud alone {unp(VC):.2f}%")

CLEAN = [(10,55),(56,437),(445,553),(562,693),(694,1127),(1128,1700)]
order = [json.load(open(p))["example_id"] for p in sorted(C5.glob("*.json"))]
lat = {}
for l in open(ROOT/"logs"/"condition5_test1700.txt"):
    m = re.match(r"\[(\d+)/1700\]\s+(\S+)\s+([\d.]+)s", l)
    if m: lat[int(m.group(1))] = float(m.group(3))
cleanv = [lat[i] for a,bb in CLEAN for i in range(a,bb+1) if i in lat]
allv = [lat[i] for i in sorted(lat)]
print(f"  Latency, GPU box:     clean chunks median {st.median(cleanv):.1f} s (n={len(cleanv)})"
      f"   all logged median {st.median(allv):.1f} s (n={len(allv)})")
print("=" * 96)

# --- what each component actually bought or cost, measured -------------------
print()
print("WHAT EACH COMPONENT BOUGHT OR COST, on the claims it actually fired on")
print("=" * 96)

# The audit fires only on claims where both locals said ENTAILED, so the local
# verdict on every one of them is True. Compare that against what happened.
if fired:
    loc_ok = sum(1 for i in fired if True == g(i))
    got_ok = sum(1 for i in fired if V5[i] == g(i))
    print(f"  AUDIT, on the {len(fired)} claims it escalated:")
    print(f"    keeping the local verdict would have scored  {loc_ok:>4} / {len(fired)} = {loc_ok/len(fired)*100:.1f}%")
    print(f"    sending them to the cloud actually scored    {got_ok:>4} / {len(fired)} = {got_ok/len(fired)*100:.1f}%")
    print(f"    net                                          {got_ok-loc_ok:+4d} verdicts for {len(fired)} extra cloud calls"
          f"   p = {mc(sum(1 for i in fired if V5[i]==g(i) and True!=g(i)), sum(1 for i in fired if V5[i]!=g(i) and True==g(i))):.4f}")

# The arbiter keeps claims local that run 1 would have sent to the cloud.
if sided7:
    kept_ok = sum(1 for i in sided7 if V5[i] == g(i))
    r1_ok   = sum(1 for i in sided7 if V1[i] == g(i))
    cl_ok   = sum(1 for i in sided7 if VC[i] == g(i))
    print(f"  ARBITER, on the {len(sided7)} claims it kept on the device:")
    print(f"    the local verdict it kept scored             {kept_ok:>4} / {len(sided7)} = {kept_ok/len(sided7)*100:.1f}%")
    print(f"    run 1 sent these to the cloud and scored     {r1_ok:>4} / {len(sided7)} = {r1_ok/len(sided7)*100:.1f}%")
    print(f"    cloud alone on the same claims scored        {cl_ok:>4} / {len(sided7)} = {cl_ok/len(sided7)*100:.1f}%")
    print(f"    net against cloud alone                      {kept_ok-cl_ok:+4d} verdicts for {len(sided7)} cloud calls removed")
    print(f"    separation: sided-with-7B local correct {kept_ok/len(sided7)*100:.1f}%, "
          f"sided-with-3B local correct "
          f"{sum(1 for i in sided3 if c5[i]['verdict_local_b']==g(i))/max(len(sided3),1)*100:.1f}%")
print("=" * 96)
