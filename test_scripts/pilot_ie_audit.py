"""Pilot: can one extra local call catch the false-entailed FDV-IE verdicts?

Population: the 213 kept-local FDV-IE claims run 1 answered "entailed". 55 are wrong.
Balanced pilot: all 55 wrong + 55 seeded-random right = 110 claims per arm.

Arms
  control   baseline_v1 re-asked on the 7B with a different seed. The noise floor.
  audit_v1  contradiction hunt, must quote the claim part and the filing line.
  audit_v2  enumerate every assertion, label each, then verdict.

No cloud calls. Resumable: each response is cached to disk.
Usage: python3 test_scripts/pilot_ie_audit.py <arm> [n_per_class]
"""
import json, random, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
CACHE  = ROOT/"results"/"pilot_ie_audit"
HOST   = "http://10.0.0.26:11434/api/generate"
MODEL  = "qwen2.5-coder:7b"

ARMS = {"control": ("baseline_v1", 1), "audit_v1": ("ie_audit_v1", 0), "audit_v2": ("ie_audit_v2", 0)}


def evidence_block(prompt):
    """recover the retrieved text from a stored baseline_v1 prompt, so the pilot
    sees exactly what the pipeline saw"""
    a = prompt.split("Financial Report:\n", 1)[1]
    return a.split("\n\nClaim to verify:\n", 1)[0]


def call(prompt, seed):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": seed,
                                   "num_ctx": 32768, "num_predict": 900}}).encode()
    req = urllib.request.Request(HOST, body, {"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    return d["response"], d["prompt_eval_count"], d["eval_count"]


def build_sample(n_per_class):
    rows = [x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))
            if x["kept_local"] and x["routed"] is True]
    wrong = [x for x in rows if x["gold"] is False]
    right = [x for x in rows if x["gold"] is True]
    rng = random.Random(0)
    w = rng.sample(wrong, min(n_per_class, len(wrong)))
    r = rng.sample(right, min(n_per_class, len(right)))
    assert len(w) and len(r), "empty class"
    print(f"sample: {len(w)} gold-refuted (must catch) + {len(r)} gold-entailed (must not break)")
    return w + r


def main():
    arm = sys.argv[1]
    n_per_class = int(sys.argv[2]) if len(sys.argv) > 2 else 55
    tmpl_name, seed = ARMS[arm]
    tmpl = open(ROOT/"prompts"/f"{tmpl_name}.txt").read()
    outdir = CACHE/arm; outdir.mkdir(parents=True, exist_ok=True)

    claims = {c.example_id: c for c in load_claims("test") if c.subset == "ie"}
    sample = build_sample(n_per_class)
    todo = [x for x in sample if not (outdir/f"{x['id']}.json").exists()]
    print(f"arm={arm} template={tmpl_name} seed={seed} model={MODEL}")
    print(f"{len(sample)-len(todo)} cached, {len(todo)} to run")

    t0 = time.time()
    done = [0]

    def work(x):
        rec = json.load(open(ROUTED/f"{x['id']}.json"))
        ev = evidence_block(rec["stages"]["local_b"]["prompt"])
        stmt = claims[x["id"]].statement
        prompt = tmpl.replace("<REPORT>", ev).replace("<STATEMENT>", stmt)
        assert "<REPORT>" not in prompt and "<STATEMENT>" not in prompt
        try:
            resp, pe, ec = call(prompt, seed)
        except Exception as e:
            return x["id"], f"ERROR {e}"
        json.dump(dict(example_id=x["id"], gold=x["gold"], arm=arm, template=tmpl_name,
                       seed=seed, model=MODEL, statement=stmt, response=resp,
                       prompt_eval_count=pe, eval_count=ec, evidence=ev),
                  open(outdir/f"{x['id']}.json", "w"))
        done[0] += 1
        if done[0] % 10 == 0:
            el = time.time()-t0
            print(f"  {done[0]}/{len(todo)}  {el/60:.1f} min  eta {el/done[0]*(len(todo)-done[0])/60:.1f} min",
                  flush=True)
        return x["id"], "ok"

    with ThreadPoolExecutor(max_workers=4) as ex:
        for cid, st in ex.map(work, todo):
            if st != "ok":
                print(f"  {cid}: {st}", flush=True)
    print(f"arm {arm} finished in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
