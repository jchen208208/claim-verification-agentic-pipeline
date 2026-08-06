"""This script keeps a prompt inside the model's context window by dropping the lowest scored retrieved chunks.

Our BM25 retriever at k=10 with num_ctx 16384 has about 15/700 claims overflow.
At k=20 it jumps to 104/700. Raising num_ctx to 32768 drops those to 0 and 6, so this module is for the last 6.
After the condition 1 test, if we decide to stick with k = 10, then this script won't be used at all, but this is just a safety measure.
There is no tokenizer on this machine so token counts are estimated from
characters.
"""

# the measured prompt_eval_count is 3.31 chars/token on table-heavy content so
# 3.31 is the floor. We want to always overestimate the token count.
CHARS_PER_TOKEN = 3.31

def estimate_tokens(text):
    return len(text) / CHARS_PER_TOKEN


SEPARATOR = "\n\n" # what build_prompt joins the evidence block together with

def _total_tokens(chunks, overhead_chars):
    # Estimated tokens for the whole prompt: template + claim + evidence block.
    # overhead_chars = len(template) - len("<REPORT>") - len("<STATEMENT>") + len(claim.statement)

    chars = overhead_chars + sum(len(c["context"]) + len(SEPARATOR) for c in chunks)
    return chars / CHARS_PER_TOKEN


def trim_to_budget(chunks, overhead_chars, budget_tokens):
    """Drop the lowest-ranked chunks until the prompt fits. Returns the kept list.
    Makes sure to never return an empty list since a prompt can't have no evidence at all"""
    # budget_tokens = num_ctx - num_predict = 32768 - 2000 = 30,768

    kept = list(chunks)
    # while the number of prompt tokens exceed 30,768, we pop thet last (worst) element in the chunks list
    while len(kept) > 1 and _total_tokens(kept, overhead_chars) > budget_tokens:
        kept.pop()

    # Through measurements, the largest prompt size is always within the cap
    # so this cannot fire currently. It raises an error rather than truncating because if it ever does fire, our assumption is wrong and we would need to troubleshoot
    if _total_tokens(kept, overhead_chars) > budget_tokens:
        # this block only runs if len(kept) == 1 or there's only one context element left in the list
        raise ValueError(f"single chunk of {len(kept[0]['context'])} chars exceeds the {budget_tokens:.0f} token budget; chunking or num_ctx changed")
    return kept