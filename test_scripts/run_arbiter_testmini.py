"""Replication of the arbiter on testmini's disagreement set. Same prompt, same rules,
nothing re-tuned. The gate is reconstructed from the three arms on disk, as in 2.24.
No cloud calls. Resumable.
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.loader import load_claims
from src.numeric_detector import is_numeric_claim

B7=ROOT/"results"/"condition1_7b_full700"
HOST="http://10.0.0.26:11434"

def main():
    pv=sys.argv[1] if len(sys.argv)>1 else "arbiter_v1"
    model=sys.argv[2] if len(sys.argv)>2 else "qwen2.5-coder:7b"
    tmpl=open(ROOT/"prompts"/f"{pv}.txt").read()
    outdir=ROOT/"results"/"arbiter_testmini"/f"{pv}_{model.replace(':','-')}"
    outdir.mkdir(parents=True,exist_ok=True)
    cl={c.example_id:c for c in load_claims("testmini")}
    rows=json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows_testmini.json"))
    pop=[x for x in rows if x["a"]!=x["b"] and not is_numeric_claim(cl[x["id"]].statement)]
    pop.sort(key=lambda x:x["id"])
    print(f"testmini population {len(pop)}  keep-7B "
          f"{sum(1 for x in pop if x['b']==x['gold'])/len(pop)*100:.1f}%  cloud "
          f"{sum(1 for x in pop if x['cloud']==x['gold'])/len(pop)*100:.1f}%")
    todo=[x for x in pop if not (outdir/f"{x['id']}.json").exists()]
    print(f"{len(pop)-len(todo)} cached, {len(todo)} to run",flush=True)
    t0=time.time(); done=[0]
    def work(x):
        p=json.load(open(B7/f"{x['id']}.json"))["prompt"]
        ev=p.split("Financial Report:\n",1)[1].split("\n\nClaim to verify:\n",1)[0]
        st=p.split("\n\nClaim to verify:\n",1)[1].rsplit("\n\nFollow the instructions",1)[0]
        pr=tmpl.replace("<REPORT>",ev).replace("<STATEMENT>",st)
        assert "<REPORT>" not in pr and "<STATEMENT>" not in pr
        body=json.dumps({"model":model,"prompt":pr,"stream":False,
            "options":{"temperature":0,"seed":0,"num_ctx":32768,"num_predict":1200}}).encode()
        for a in range(3):
            try:
                d=json.loads(urllib.request.urlopen(urllib.request.Request(
                    HOST+"/api/generate",body,{"Content-Type":"application/json"}),timeout=1200).read())
                break
            except Exception as e:
                if a==2: return x["id"],f"ERROR {e}"
                time.sleep(15)
        json.dump(dict(example_id=x["id"],subset=x["subset"],gold=x["gold"],a=x["a"],b=x["b"],
                       cloud=x["cloud"],statement=st,evidence=ev,model=model,prompt_version=pv,
                       response=d["response"],prompt_eval_count=d["prompt_eval_count"],
                       eval_count=d["eval_count"]),open(outdir/f"{x['id']}.json","w"))
        done[0]+=1
        if done[0]%25==0:
            el=time.time()-t0
            print(f"  {done[0]}/{len(todo)}  {el/60:.1f} min  eta {el/done[0]*(len(todo)-done[0])/60:.1f} min",flush=True)
        return x["id"],"ok"
    errs=0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for cid,st in ex.map(work,todo):
            if st!="ok": errs+=1; print(f"  {cid}: {st}",flush=True)
    missing=[x for x in pop if not (outdir/f"{x['id']}.json").exists()]
    print(f"done in {(time.time()-t0)/60:.1f} min, {errs} errors, {len(missing)} missing")
    sys.exit(1 if missing else 0)

if __name__=="__main__":
    main()
