"""Return only the gold evidence elements for a claim.
Used for troubleshooting and not a real retriever.
Its job is to measure what the model does when retrieval is perfect,
which limits what any retrieval improvement could do."""

def retrieve(claim, report, k=None):
    elements = report["context"]

    return [elements[index] for index in sorted(claim.relevant_context)]
