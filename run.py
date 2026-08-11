"""The entire process: run one experiment described by a config file.
    python3 run.py configs/trial_run_3b.json"""

import functools
import json
import sys
import random
from pathlib import Path

from src.loader import load_claims
from src.ollama_client import call_ollama
from src.deepseek_client import call_deepseek
from src.bm25_retriever import retrieve as bm25_retrieve
from src.placeholder_retriever import retrieve as placeholder_retrieve
from src.gold_retriever import retrieve as gold_retrieve
from src.run_loop import run_sample
from src.sampler import stratified_sample

REPO_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = REPO_ROOT / "results"

# the two different retrievers, we will only use bm25
RETRIEVERS = {
    "bm25": bm25_retrieve,
    "placeholder_token_overlap": placeholder_retrieve,
    "gold": gold_retrieve
}

# the two model clients, selected by the config's "client" key
CLIENTS = {
    "ollama": call_ollama,
    "deepseek": call_deepseek,
}

def build_sample(config):
    """If per_cell is null, that means it's a full 700 run so no need for sampling. Sampling caps at 600 total claims."""
    claims = list(load_claims())

    if config["per_cell"] is not None:
        return stratified_sample(claims, config["per_cell"], seed=config["sample_seed"])

    if len(claims) != 700:
        raise ValueError(f"expected 700 claims, loaded {len(claims)}")

    random.Random(config["sample_seed"]).shuffle(claims)
    return claims


def main():
    # example command: python3 run.py configs/condition1_7b_full700.json 2>&1 | tee logs/condition1_7b_full700.txt, here python's sys.argv = ['run.py', 'config...']
    # 'tee' command writes the same stream to a file and also let's you see it on your screen/terminal. with just '>', all the output get redirected to the file without showing on screen.
    #if more or less than two cli arguments, wrong command
    if len(sys.argv) != 2:
        print("usage: python3 run.py configs/<name>.json")
        return 1

    # loads in configs/<name>.json
    with open(sys.argv[1]) as f:
        config = json.load(f)

    # uses the retriever specified in the config json file
    retriever = functools.partial(RETRIEVERS[config["retriever"]], k=config["top_k"])

    sample = build_sample(config)
    scope = "full 700" if config["per_cell"] is None else f"{config['per_cell']} per cell"

    results_dir = RESULTS_ROOT / config["experiment"]

    print(f"experiment    {config['experiment']}")
    print(f"model         {config['model']}")
    print(f"num_ctx       {config['num_ctx']}")
    print(f"num_predict   {config['num_predict']}")
    print(f"temperature   {config['temperature']}")
    print(f"seed          {config['seed']}")
    print(f"prompt        {config['prompt_version']}")
    print(f"retriever     {config['retriever']}, k={config['top_k']}")
    print(f"sample        {len(sample)} examples, {scope}, seed {config['sample_seed']}")
    print(f"results       {results_dir}\n", flush=True)
    print(f"client        {config.get('client', 'ollama')}")

    client = CLIENTS[config.get("client", "ollama")]
    run_sample(sample, config, results_dir, client, retriever)
    return 0


if __name__ == "__main__":
    sys.exit(main())