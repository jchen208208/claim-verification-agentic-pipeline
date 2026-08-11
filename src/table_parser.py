"""This script turns a FINDVER table into a pandas DataFrame, or states that it could not be done.

Parsing and checking are separate since read_html() never raised an exception while
removing data on about a third of the test samples.
check_table decides whether a parse is usable."""

import io
import pandas

def table_index(report):
    # returns the context positions of the table elements in document order.
    # the n-th element of the list is the context index whose HTML is html_tables[n]
    return [i for i, element in enumerate(report["context"]) if element["type"] == "table"]

def parse_table(report, context_index):
    # creates a list of pandas dataframes for the table at report["context"][context_index] since each table can have multiple dataframes to account for nested tables. None if there's no table to parse (does not mean wrong parse)
    
    positions = table_index(report)

    try:
        nth = positions.index(context_index)  # gets the context index stored at the n-th index of the positions array
    except ValueError:
        return None  # the element corresponding to the context_index is not a table

    try:
        dataframes = pandas.read_html(io.StringIO(report["html_tables"][nth]))
    except Exception:
        return None

    return dataframes or None