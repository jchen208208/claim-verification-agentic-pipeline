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