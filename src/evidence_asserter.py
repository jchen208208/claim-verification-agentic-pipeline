"""Check that the relevant context (gold evidence) actually reached the model

evidence_present: after the prompt is built, look for a rare token from each gold
context element in the prompt string. This runs beside the pipeline, never inside it.
The gold indices are not passed to any pipeline stage and the prompt is not changed
by the result, so the retriever is still doing the retrieving.

context_overflow: after the call, prompt_eval_count + eval_count >= num_ctx. Ollama
0.12.3 evicts the oldest prompt tokens when generation fills the window and still
reports done_reason "stop", so evidence that was present at ingestion can be destroyed
mid-response.

This helps us understand if the failure was caused by a corrupted input or a reasoning failure"""

