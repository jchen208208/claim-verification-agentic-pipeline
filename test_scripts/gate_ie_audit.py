"""GATE for the FDV-IE audit skill. Ceiling first, pipeline code later.

Question: given a claim both local models wrongly called entailed, and given the gold
evidence itself, can the local model find the one altered conjunct?

This is the upper bound. Retrieval only makes it harder, so a failure here kills the
skill for about three hours of local compute instead of a night.

KILL CRITERIA, written before any number is seen:
  recall on gold-refuted claims  < 50%   -> stop
  false-positive rate on gold-entailed claims > 25%  -> stop
Both must pass. A detector that fires on everything is not a detector.

Usage: python3 test_scripts/gate_ie_audit.py [n_per_class] [model] [prompt] [evidence_mode]
  evidence_mode: gold (default) | retrieved
"""
import json, random, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims
from src.run_loop import read_report

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
HOSTS  = ["http://10.0.0.26:11434", "http://localhost:11434"]


def pick_host():
    for h in HOSTS:
        try:
            urllib.request.urlopen(h + "/api/tags", timeout=6).read()
            return h
        except Exception:
            continue
    raise SystemExit("no ollama host reachable")


def gold_evidence(claim):
    rep = read_report(claim.report)
    idx = sorted(set(claim.relevant_context))          # data trap 8: not a set
    return "\n\n".join(rep["context"][i]["context"] for i in idx if i < len(rep["context"]))


def retrieved_evidence(cid):
    p = json.load(open(ROUTED/f"{cid}.json"))["stages"]["local_b"]["prompt"]
    return p.split("Financial Report:\n", 1)[1].split("\n\nClaim to verify:\n", 1)[0]


def main():
    n_per_class = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    model  = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-coder:7b"
    prompt_v = sys.argv[3] if len(sys.argv) > 3 else "ie_audit_v1"
    mode   = sys.argv[4] if len(sys.argv) > 4 else "gold"

    host = pick_host()
    tmpl = open(ROOT/"prompts"/f"{prompt_v}.txt").read()
    tag  = f"{mode}_{prompt_v}_{model.replace(':','-')}"
    outdir = ROOT/"results"/"gate_ie_audit"/tag
    outdir.mkdir(parents=True, exist_ok=True)

    claims = {c.example_id: c for c in load_claims("test") if c.subset == "ie"}
    rows = [x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))
            if x["kept_local"] and x["routed"] is True]
    wrong = [x for x in rows if x["gold"] is False]
    right = [x for x in rows if x["gold"] is True]
    rng = random.Random(0)
    sample = (rng.sample(wrong, min(n_per_class, len(wrong)))
              + rng.sample(right, min(n_per_class, len(right))))

    # balance assertion before any model call, data trap 2
    nw = sum(1 for x in sample if x["gold"] is False)
    nr = len(sample) - nw
    assert nw and nr, "sample is single-label"
    print(f"host={host}  model={model}  prompt={prompt_v}  evidence={mode}")
    print(f"sample: {nw} gold-refuted (must catch) + {nr} gold-entailed (must not break)")

    todo = [x for x in sample if not (outdir/f"{x['id']}.json").exists()]
    print(f"{len(sample)-len(todo)} cached, {len(todo)} to run", flush=True)
    t0 = time.time(); done = [0]

    def work(x):
        c = claims[x["id"]]
        ev = gold_evidence(c) if mode == "gold" else retrieved_evidence(x["id"])
        p = tmpl.replace("<REPORT>", ev).replace("<STATEMENT>", c.statement)
        assert "<REPORT>" not in p and "<STATEMENT>" not in p
        body = json.dumps({"model": model, "prompt": p, "stream": False,
                           "options": {"temperature": 0, "seed": 0,
                                       "num_ctx": 32768, "num_predict": 300}}).encode()
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                host + "/api/generate", body, {"Content-Type": "application/json"}),
                timeout=1800).read())
        except Exception as e:
            return x["id"], f"ERROR {e}"
        json.dump(dict(example_id=x["id"], gold=x["gold"], model=model, prompt_version=prompt_v,
                       evidence_mode=mode, statement=c.statement, evidence=ev,
                       response=d["response"], prompt_eval_count=d["prompt_eval_count"],
                       eval_count=d["eval_count"]), open(outdir/f"{x['id']}.json", "w"))
        done[0] += 1
        el = time.time()-t0
        print(f"  {done[0]}/{len(todo)}  {el/60:5.1f} min  "
              f"eta {el/done[0]*(len(todo)-done[0])/60:5.1f} min  {x['id']}", flush=True)
        return x["id"], "ok"

    workers = 4 if "10.0.0.26" in host else 1     # the MacBook cannot overlap calls
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cid, st in ex.map(work, todo):
            if st != "ok":
                print(f"  {cid}: {st}", flush=True)
    print(f"done in {(time.time()-t0)/60:.1f} min -> results/gate_ie_audit/{tag}")


if __name__ == "__main__":
    main()
