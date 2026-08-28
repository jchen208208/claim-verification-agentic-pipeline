"""A skill to verify an arithmetic claim by computing it in Python instead of in the model.
The model doesn't write code. It provides numbers and the name of an operation,
and we look that name up in the table below."""


def _percent_change(new, old):
    return (new - old) / old * 100.0


def _difference(a, b):
    return a - b


def _percent_of(part, whole):
    return part / whole * 100.0


def _ratio(a, b):
    return a / b


def _sum(*values):
    return sum(values)


# the allowed operations chosen from analyzing testmini's numeric claims' patterns
OPERATIONS = {
    "percent_change": _percent_change,
    "difference": _difference,
    "percent_of": _percent_of,
    "ratio": _ratio,
    "sum": _sum,
}


def compute(operation, operands):
    # run one operationa dn return the value or None if it cannot run.

    function = OPERATIONS.get(operation)
    if function is None:
        return None

    try:
        return float(function(*operands))  # '*' unpacks the list to comma separated operands
    except (TypeError, ZeroDivisionError, ValueError, OverflowError):
        return None