"""Run the routed pipeline: 3B, then 7B, then cloud only when needed."""

from dataclasses import dataclass, field

@dataclass
class RoutedRecord:
    # one claim through the pipeline as one JSON file.

    # same as Record object
    example_id: str
    subset: str
    gold_label: bool
    gold_explanation: str
    config: dict

    extracted_label: bool | None = None
    extraction_source: str | None = None
    evidence_present: bool | None = None
    context_overflow: bool | None = None
    done_reason: str | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    elapsed_seconds: float | None = None   # this covers the whole claim including every stage that ran
    thinking: str | None = None
    served_model: str | None = None
    system_fingerprint: str | None = None
    chunks_requested: int | None = None
    chunks_kept: int | None = None

    # these fields determine the routing decision
    verdict_local_a: bool | None = None  # the 3B's verdict, None if skipped
    verdict_local_b: bool | None = None  # the 7B's verdict, None if skipped
    verdict_cloud: bool | None = None  # None when the cloud was not called
    cloud_called: bool = False
    final_source: str | None = None  # "local_b" or "cloud"
    escalation_reason: str | None = None  # "numeric_detector", "disagreement", or None when nothing escalated
    locals_skipped: bool = False  # the detector fired = true

    # the full stage's records: {"local_a": {...}, "local_b": {...}, "cloud": {...}}
    stages: dict = field(default_factory=dict)

    status: str = "ok"
    traceback: str | None = None