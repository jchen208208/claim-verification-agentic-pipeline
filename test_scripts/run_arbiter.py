"""Can a LOCAL arbiter replace the cloud on the disagreement set?

Population: the 575 claims of test.json where the 3B and the 7B disagreed. On 549 of
them exactly one local model is already right, so the answer is on the device; the
gate just cannot tell which. Today all 459 escalated ones go to the cloud.

Bars, from run 1:
  59.7%  keep the 7B, today's fallback if we simply stopped escalating
  73.4%  what the cloud scores on the escalated subset -> break-even, cloud halves for free
  95.5%  oracle, pick the correct local model every time

No cloud calls. Resumable.
Usage: python3 test_scripts/run_arbiter.py <prompt> [model] [n]
"""
import json, random, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R    = ROOT/"results"/"condition4_pipeline_test1700"
HOST = "http://10.0.0.26:11434"


def population():
    out = []
    for p in R.glob("*.json"):
        r = json.load(open(p))
        if r["verdict_local_a"] == r["verdict_local_b"]:
            continue
        prompt = r["stages"]["local_b"]["prompt"]
        ev = prompt.split("Financial Report:\n", 1)[1].split("\n\nClaim to verify:\n", 1)[0]
        st = prompt.split("\n\nClaim to verify:\n", 1)[1].rsplit("\n\nFollow the instructions", 1)[0]
        out.append(dict(id=r["example_id"], subset=r["subset"], gold=r["gold_label"],
                        a=r["verdict_local_a"], b=r["verdict_local_b"],
                        cloud=r["verdict_cloud"], evidence=ev, statement=st))
    out.sort(key=lambda x: x["id"])
    return out


def main():
    prompt_v = sys.argv[1]
    model    = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-coder:7b"
    n        = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    tmpl = open(ROOT/"prompts"/f"{prompt_v}.txt").read()
    outdir = ROOT/"results"/"arbiter"/f"{prompt_v}_{model.replace(':','-')}"
    outdir.mkdir(parents=True, exist_ok=True)

    pop = population()
    if n and n < len(pop):
        pop = random.Random(0).sample(pop, n)          # fixed seed, whole-set draw
    ne = sum(1 for x in pop if x["gold"] is True)
    print(f"disagreement population {len(pop)}, gold entailed {ne} ({ne/len(pop)*100:.1f}%)")
    print(f"bars: keep-7B {sum(1 for x in pop if x['b']==x['gold'])/len(pop)*100:.1f}%  "
          f"cloud {sum(1 for x in pop if x['cloud']==x['gold'])/len(pop)*100:.1f}%")

    todo = [x for x in pop if not (outdir/f"{x['id']}.json").exists()]
    print(f"{len(pop)-len(todo)} cached, {len(todo)} to run", flush=True)
    t0 = time.time(); done = [0]

    def work(x):
        p = tmpl.replace("<REPORT>", x["evidence"]).replace("<STATEMENT>", x["statement"])
        assert "<REPORT>" not in p and "<STATEMENT>" not in p
        body = json.dumps({"model": model, "prompt": p, "stream": False,
                           "options": {"temperature": 0, "seed": 0,
                                       "num_ctx": 32768, "num_predict": 1200}}).encode()
        for a in range(3):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(
                    HOST+"/api/generate", body, {"Content-Type": "application/json"}),
                    timeout=1200).read())
                break
            except Exception as e:
                if a == 2: return x["id"], f"ERROR {e}"
                time.sleep(15)
        rec = {k: x[k] for k in ("id", "subset", "gold", "a", "b", "cloud", "statement", "evidence")}
        rec.update(example_id=x["id"], model=model, prompt_version=prompt_v,
                   response=d["response"], prompt_eval_count=d["prompt_eval_count"],
                   eval_count=d["eval_count"])
        json.dump(rec, open(outdir/f"{x['id']}.json", "w"))
        done[0] += 1
        if done[0] % 25 == 0:
            el = time.time()-t0
            print(f"  {done[0]}/{len(todo)}  {el/60:5.1f} min  "
                  f"eta {el/done[0]*(len(todo)-done[0])/60:5.1f} min", flush=True)
        return x["id"], "ok"

    errs = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for cid, st in ex.map(work, todo):
            if st != "ok": errs += 1; print(f"  {cid}: {st}", flush=True)
    missing = [x for x in pop if not (outdir/f"{x['id']}.json").exists()]
    print(f"done in {(time.time()-t0)/60:.1f} min, {errs} errors, {len(missing)} missing")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
