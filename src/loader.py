"""Loads FINDVER claim records from test/testmini."""

import json
from collections import Counter
from pathlib import Path
from dataclasses import dataclass

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "FinDVer" / "data"

EXPECTED_COUNTS = {"ie": 250, "numeric": 250, "knowledge": 200}

@dataclass(frozen=True)
class Claim:
    # same 11 fields regardless of the 3 subset
    example_id: str
    subset: str
    split: str
    statement: str
    entailment_label: bool
    relevant_context: tuple[int, ...]
    report: str
    explanation: str

    # subset-specific: None when the subset does not have them
    python_calculation: str | None
    execution_result: float | None
    knowledge: tuple[str, ...] | None

def load_raw():
    # read testmini.json and confirm it is the file we expect.
    path = DATA_DIR / "testmini.json"
    with open(path) as f:
        records = json.load(f)

    counts = Counter(r["subset"] for r in records)
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"unexpected subset counts: {counts}")

    return records

def raw_to_claim(raw):
    # convert one raw record dict to a claim object
    if "explanation" in raw:
        explanation = raw["explanation"]
    else:
        explanation = raw["explaination"]  # numeric subset misspells it

    knowledge = raw.get("knowledge")

    # .get() for non-required field since .get() returns None if key is absent and [] raises KeyError if required field missing
    return Claim(
        example_id=raw["example_id"],
        subset=raw["subset"],
        split=raw["split"],
        statement=raw["statement"],
        entailment_label=raw["entailment_label"],
        relevant_context=tuple(raw["relevant_context"]),
        report=raw["report"],
        explanation=explanation,
        python_calculation=raw.get("python_calculation"),
        execution_result=raw.get("execution_result"),
        knowledge=tuple(knowledge) if knowledge is not None else None,
    )

def load_claims():
    # loads all 700 claims into a list and returns that list
    return [raw_to_claim(r) for r in load_raw()]