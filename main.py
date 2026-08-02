"""The entire process: run one experiment described by a config file.
    python3 run_experiment.py configs/trial_run_3b.json"""

import functools
import json
import sys
from pathlib import Path

from src.loader import load_claims
from src.ollama_client import call_ollama
from src.placeholder_retriever import retrieve
from src.run_loop import run_sample
from src.sampler import stratified_sample

REPO_ROOT = Path(__file__).resolve().parent
RESULTS_ROOT = REPO_ROOT / "results"


def main():
    if len(sys.argv) != 2:
        print("usage: python3 run_experiment.py configs/<name>.json")
        return 1

    results_dir = RESULTS_ROOT / config["experiment"]

    # everything the code reads is printed here, so a missing or misspelled key shows now
    print(f"experiment    {config['experiment']}")
    print(f"model         {config['model']}")
    print(f"num_ctx       {config['num_ctx']}")
    print(f"num_predict   {config['num_predict']}")
    print(f"temperature   {config['temperature']}")
    print(f"seed          {config['seed']}")
    print(f"prompt        {config['prompt_version']}")
    print(f"retriever     {config['retriever']}, k={config['top_k']}")
    print(f"sample        {len(sample)} examples, {config['per_cell']} per cell, ")
    print(f"seed {config['sample_seed']}")
    print(f"results       {results_dir}\n", flush=True)

    run_sample(sample, config, results_dir, call_ollama, retriever)
    return 0


if __name__ == "__main__":
    sys.exit(main())