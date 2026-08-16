"""The entire process: run one experiment described by a config file.
    python3 run.py configs/trial_run_3b.json"""

import functools
import json
import sys
import random
from pathlib import Path

from src.loader import load_claims, EXPECTED_COUNTS
from src.ollama_client import call_ollama, get_ollama_version
from src.deepseek_client import call_deepseek
from src.bm25_retriever import retrieve as bm25_retrieve
from src.placeholder_retriever import retrieve as placeholder_retrieve
from src.gold_retriever import retrieve as gold_retrieve
from src.gold_padded_retriever import retrieve as gold_padded_retrieve
from src.run_loop import run_sample
from src.sampler import stratified_sample
from src.routed_loop import run_routed_sample

REPO_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = REPO_ROOT / "results"

# the two different retrievers, we will only use bm25
RETRIEVERS = {
    "bm25": bm25_retrieve,
    "placeholder_token_overlap": placeholder_retrieve,
    "gold": gold_retrieve,
    "gold_padded": gold_padded_retrieve,
}

# the two model clients, selected by the config's "client" key
CLIENTS = {
    "ollama": call_ollama,
    "deepseek": call_deepseek,
}

def build_sample(config):
    """If per_cell is null, that means it's a full run so no need for sampling."""
    split = config.get("split", "testmini")
    claims = list(load_claims(split))

    if config["per_cell"] is not None:
        return stratified_sample(claims, config["per_cell"], seed=config["sample_seed"])

    expected = sum(EXPECTED_COUNTS[split].values())
    if len(claims) != expected:
        raise ValueError(f"expected {expected} claims in {split}, loaded {len(claims)}")

    random.Random(config["sample_seed"]).shuffle(claims)
    return claims


def run_pipeline(config, sample, results_dir, retriever):

    print(f"experiment    {config['experiment']}   PIPELINE")
    print(f"system        {config['model']}")
    for name in ("local_a", "local_b", "cloud"):
        stage = config[name]
        print(f"  {name:9}   {stage['model']:22}"
              f" prompt {stage['prompt_version']:12}"
              f" client {stage.get('client', 'ollama')}")
    print(f"escalate_numeric            {config.get('escalate_numeric', True)}")
    print(f"skip_local_when_escalating  {config.get('skip_local_when_escalating', False)}")
    print(f"retriever     {config['retriever']}, k={config['top_k']}")
    print(f"sample        {len(sample)} examples, "
          f"{config.get('split', 'testmini')}, seed {config['sample_seed']}")
    print(f"results       {results_dir}\n", flush=True)

    # both local models must run on the same host
    host = config["local_a"].get("ollama_host", "localhost")
    if config["local_b"].get("ollama_host", "localhost") != host:
        print("\nWarning: local_a and local_b are on different hosts.")
        return 1

    ollama_version = get_ollama_version(host)
    print(f"ollama        {ollama_version} on {host}", flush=True)

    expected = config.get("expect_ollama_version")
    if expected is not None and ollama_version != expected:
        print(f"\nError: config expects Ollama {expected}, this server is {ollama_version}.")
        return 1

    run_routed_sample(sample, config, results_dir, CLIENTS, retriever, ollama_version)
    return 0


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
    split = config.get("split", "testmini")
    scope = f"full {split}" if config["per_cell"] is None else f"{config['per_cell']} per cell"

    results_dir = RESULTS_ROOT / config["experiment"]

    # If we're running a pipeling, the single-model path is skipped over.
    if config.get("pipeline"):
        return run_pipeline(config, sample, results_dir, retriever)

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

    client_name = config.get("client", "ollama")
    client = CLIENTS[client_name]

    # Only Ollama has a version to read.
    ollama_version = None
    if client_name == "ollama":
        ollama_version = get_ollama_version(config.get("ollama_host", "localhost"))
        print(f"ollama        {ollama_version}", flush=True)

        expected = config.get("expect_ollama_version")
        if expected is not None and ollama_version != expected:
            print(f"\nERROR: config expects Ollama {expected}, this server is {ollama_version}.")
            return 1  # exit out of the run because the ollama version updated. shouldn't be an issue anymore sicne auto-update is now toggled off
        
    run_sample(sample, config, results_dir, client, retriever, ollama_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())