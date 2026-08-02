"""Logs the data and results of each test example,
one JSON file per claim and stored in the /results folder"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass
class Record:
    # known fields before the model call
    example_id: str
    subset: str
    gold_label: bool
    gold_explanation: str
    prompt: str
    config: dict # contains model, num_ctx, num_predict, temperature, seed, prompt_version

    # filled in after the model call
    response: str | None = None
    extracted_label: bool | None = None
    extraction_source: str | None = None # which regex did the extraction
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    done_reason: str | None = None # Ollama either returns "stop" if the model finished generation on its own or "length" if the model was truncated due to hitting the num_predict cap
    elapsed_seconds: float | None = None # total generation time

    # filled in by the evidence asserter
    evidence_present: bool | None = None
    context_overflow: bool | None = None

    # set by the run loop's try/except
    status: str = "ok" # if run loop catches an exception, status = "failed"
    traceback: str | None = None # then puts traceback error message string into here

def write_result(record, results_dir):
    # one JSON file per claim and written as soon as the example finishes
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    path = results_dir / f"{record.example_id}.json"
    with open(path, "w") as f:
        json.dump(asdict(record), f, indent=2)

    return path

def has_result(example_id, results_dir):
    # returns true only if a completed, readable result already exists with the results directory
    path = Path(results_dir) / f"{example_id}.json"
    if not path.exists():
        return False

    try:
        with open(path, "r") as f:
            record = json.load(f)
    except json.JSONDecodeError:
        return False # json file was truncated by a crash mid-write so we need to re-run this example

    return record["status"] == "ok"