"""Regenerate every number in paper_numbers.md §2.9: what pandas does to SEC tables.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. This script is that script for §2.9, which was first
produced by throwaway code on 11 August and which decided that Tier 1's
tables-as-DataFrames half would not be built.

Five measurements, none of which needs a model call:

    mapping        does context[i] correspond to html_tables[n], and how do we
                   know it is not coincidence
    parsing        how often read_html raises, and how often the numbers in the
                   pipe-delimited copy survive into the DataFrame
    structure      headers, merged-cell duplication, null density, and how far
                   the column count inflates against the text copy
    population     how many CLAIMS have gold evidence that is a real data table
                   which parses cleanly. Elements are not the unit that scores.
    scale          where "(in thousands)" lives, and how often it carries an
                   "except per share" carve-out

TWO MEASUREMENT BUGS WERE MADE ON 11 AUGUST AND BOTH ARE GUARDED AGAINST HERE.

    1. Comparing numbers as STRINGS. pandas turns the cell 45300 into 45300.0,
       so "45300" != "45300.0" and a match scores as a miss. That alone moved
       the parse success rate by six points, from 58.7% to 64.6%. numbers()
       below returns floats for exactly this reason.
    2. A pattern of `\\(?000'?s?\\)?` to find "(000)" scale notes. It matches the
       bare digits 000, which appear inside any figure like 1,000, so it was
       counting ordinary numbers. There is no such check in this file.

Runtime is a few minutes: read_html is not fast and the default sample is
1,200-odd tables. Requires pandas, lxml and beautifulsoup4.

Usage:
    python3 test_scripts/measure_table_parse.py
    python3 test_scripts/measure_table_parse.py --reports 10
"""

import io
import json
import random
import re
import sys
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "FinDVer" / "financial_reports"
sys.path.insert(0, str(REPO_ROOT))
from src.loader import load_claims

warnings.filterwarnings("ignore")

# Defaults are the sample sizes that produced the figures in §2.9. Changing them
# changes the numbers, so they are named here rather than buried in the code.
PARSE_REPORTS = 30       # for read_html fidelity and structure
ALIGN_REPORTS = 40       # for the mapping content check
SAMPLE_SEED = 0

NUMBER = re.compile(r"\d[\d,]*\.?\d*")
SCALE = re.compile(r"in\s+(thousand|million|billion)s?", re.I)
CARVE_OUT = re.compile(r"except|other than", re.I)


def numbers(text):
    """Numeric tokens as FLOATS, deliberately not strings.

    See bug 1 in the module docstring. Single digits are skipped: they are
    footnote markers and list numbers as often as data, and they appear in
    almost every table, so they would match by accident.
    """
    found = set()
    for token in NUMBER.findall(str(text)):
        token = token.replace(",", "").rstrip(".")
        if len(token) < 2:
            continue
        try:
            found.add(float(token))
        except ValueError:
            pass
    return found


def is_data_table(text):
    """A real data table, not an HTML table used for page layout.

    Filings use tables for bulleted lists and indentation constantly. Counting
    those inflates the apparent workload by about a quarter, which is why §7.1
    states the payoff against 13.2% of elements rather than the 18.1% that
    carry type == "table".
    """
    rows = [r for r in text.split("\n") if r.strip()]
    if len(rows) < 2:
        return False
    cells = [c.strip() for r in rows for c in r.split("|") if c.strip()]
    if len(cells) < 4:
        return False
    return sum(1 for c in cells if NUMBER.search(c)) / len(cells) >= 0.25


def table_positions(report):
    """Context indices of the table elements. The nth is html_tables[n]."""
    return [i for i, e in enumerate(report["context"]) if e["type"] == "table"]


def frame_numbers(frames):
    """Every number in a list of DataFrames, values and column labels."""
    found = set()
    for frame in frames:
        found |= numbers(" ".join(map(str, frame.values.ravel().tolist())))
        found |= numbers(" ".join(map(str, frame.columns.tolist())))
    return found


def text_columns(text):
    """Logical column count: the widest pipe-delimited row in the text copy."""
    return max((len(r.split("|")) - 1 for r in text.split("\n") if r.count("|") >= 2),
               default=0)


def load_report(name):
    return json.loads((REPORT_DIR / name).read_text())


# ------------------------------------------------------------------ sections

def measure_mapping(names, sample):
    """Is the context-to-html_tables correspondence positional?

    The count check alone proves nothing: two lists can be the same length and
    still be in different orders. The shifted control is what settles it. If
    every table in a filing shared similar numbers, both columns would score
    high; the gap between them is the evidence.
    """
    matches = mismatches = 0
    for name in names:
        report = load_report(name)
        if len(table_positions(report)) == len(report.get("html_tables") or []):
            matches += 1
        else:
            mismatches += 1

    aligned, shifted = [], []
    for name in sample:
        report = load_report(name)
        positions = table_positions(report)
        texts = [numbers(BeautifulSoup(h, "lxml").get_text(" "))
                 for h in report["html_tables"]]
        for n, index in enumerate(positions):
            want = numbers(report["context"][index]["context"])
            if not want or not texts[n]:
                continue
            aligned.append(len(want & texts[n]) / len(want))
            other = texts[(n + 1) % len(texts)]
            if other:
                shifted.append(len(want & other) / len(want))

    mean = lambda v: sum(v) / len(v) if v else 0.0
    print("\nMAPPING")
    print(f"  table count == len(html_tables)   {matches}/{matches+mismatches} reports")
    print(f"  aligned   context[i] vs html_tables[i]     {mean(aligned):.3f}")
    print(f"  shifted   context[i] vs html_tables[i+1]   {mean(shifted):.3f}   <- control")


def measure_parse_and_structure(sample):
    """read_html fidelity, and what it does to the table's shape.

    "Did it throw" is not a usable test and this section is what proves it.
    The numeric round-trip works because the pipe-delimited copy never went
    through pandas, so it acts as an answer key for which numbers should be
    present. It cannot check SHAPE, which is what the structure block covers.
    """
    threw = multi = 0
    containment = {"data": [], "layout": []}
    int_cols = merged_dup = 0
    nulls, all_null_cols, inflation = [], [], []

    for name in sample:
        report = load_report(name)
        positions = table_positions(report)
        for n, index in enumerate(positions):
            text = report["context"][index]["context"]
            try:
                frames = pd.read_html(io.StringIO(report["html_tables"][n]))
            except Exception:
                threw += 1
                continue
            if not frames:
                threw += 1
                continue
            if len(frames) > 1:
                multi += 1

            want = numbers(text)
            if want:
                score = len(want & frame_numbers(frames)) / len(want)
                containment["data" if is_data_table(text) else "layout"].append(score)

            if not is_data_table(text):
                continue
            frame = max(frames, key=lambda d: d.size)
            if all(str(c).isdigit() for c in frame.columns):
                int_cols += 1
            nulls.append(float(frame.isna().mean().mean()))
            all_null_cols.append(float((frame.isna().mean() == 1.0).mean()))
            wide = text_columns(text)
            if wide:
                inflation.append(frame.shape[1] / wide)
            head = frame.head(3).astype(str)
            if any((row.values[:-1] == row.values[1:]).sum() >= 2
                   for _, row in head.iterrows()):
                merged_dup += 1

    total = threw + sum(len(v) for v in containment.values())
    mean = lambda v: sum(v) / len(v) if v else 0.0
    median = lambda v: sorted(v)[len(v) // 2] if v else 0.0

    print("\nPARSING")
    print(f"  tables attempted            {total}")
    print(f"  read_html raised            {threw}  ({threw/total:.1%})")
    print(f"  returned >1 dataframe       {multi}  (nested tables)")
    for label, values in (("REAL DATA TABLES", containment["data"]),
                          ("layout tables", containment["layout"])):
        if not values:
            continue
        print(f"\n  {label}  n={len(values)}  mean containment {mean(values):.3f}")
        for threshold in (0.999, 0.95, 0.90, 0.50):
            share = sum(1 for x in values if x >= threshold) / len(values)
            print(f"    >= {threshold:<6} {share:6.1%}")
        print(f"    <  0.50   {sum(1 for x in values if x < 0.50)/len(values):6.1%}")

    n = len(nulls)
    print("\nSTRUCTURE  (real data tables only)")
    print(f"  columns are integers only         {int_cols:5}  {int_cols/n:6.1%}")
    print(f"  merged-cell duplication, rows 1-3 {merged_dup:5}  {merged_dup/n:6.1%}")
    print(f"  null fraction, whole frame        mean {mean(nulls):.2f}  median {median(nulls):.2f}")
    print(f"  columns entirely null             mean {mean(all_null_cols):.2f}")
    print(f"  column inflation vs the text copy mean {mean(inflation):.2f}x "
          f"median {median(inflation):.2f}x")
    print(f"    >= 2.0x  {sum(1 for x in inflation if x >= 2.0)/len(inflation):6.1%}")
    print(f"    <= 1.2x  {sum(1 for x in inflation if x <= 1.2)/len(inflation):6.1%}")


def measure_population(claims):
    """How many CLAIMS can table parsing reach.

    Elements are not the unit that gets scored. A tier that improves 13% of
    elements may reach far more or far fewer claims, and only this number
    tells you which.
    """
    cache = {}
    stats = {}
    for claim in claims:
        if claim.report not in cache:
            report = load_report(claim.report)
            report["_positions"] = table_positions(report)
            cache[claim.report] = report
        report = cache[claim.report]

        gold = sorted(set(claim.relevant_context))
        tables = [i for i in gold if report["context"][i]["type"] == "table"]
        data = [i for i in tables if is_data_table(report["context"][i]["context"])]

        for key in ("ALL", claim.subset):
            s = stats.setdefault(key, {"n": 0, "table": 0, "data": 0, "parse": 0})
            s["n"] += 1
            s["table"] += bool(tables)
            s["data"] += bool(data)

        if not data:
            continue
        clean = True
        for index in data:
            html = report["html_tables"][report["_positions"].index(index)]
            try:
                frames = pd.read_html(io.StringIO(html))
            except Exception:
                clean = False
                break
            want = numbers(report["context"][index]["context"])
            if want and len(want & frame_numbers(frames)) / len(want) < 0.999:
                clean = False
                break
        if clean:
            for key in ("ALL", claim.subset):
                stats[key]["parse"] += 1

    print("\nADDRESSABLE POPULATION  (all 700 claims)")
    print(f"  {'subset':12}{'claims':>8}{'gold has table':>16}{'gold has DATA':>16}{'all parse ok':>15}")
    for key in ("ALL", "ie", "knowledge", "numeric"):
        s = stats[key]
        print(f"  {key:12}{s['n']:>8}{s['table']:>9} {s['table']/s['n']:5.1%}"
              f"{s['data']:>9} {s['data']/s['n']:5.1%}{s['parse']:>8} {s['parse']/s['n']:5.1%}")


def measure_scale(names):
    """Where the scaling note lives, and how often it carves out an exception.

    The carve-out share is the whole reason `scale` is metadata rather than a
    multiplier. "In thousands, except per share data" means one table holds two
    scales, and no rule we can write knows which rows are the exception.
    """
    found = {"own": 0, "before": 0, "absent": 0}
    phrases, carve_outs, tables = {}, 0, 0

    for name in names:
        report = load_report(name)
        context = report["context"]
        for i, element in enumerate(context):
            if element["type"] != "table" or not is_data_table(element["context"]):
                continue
            tables += 1
            own = SCALE.search(element["context"])
            before = SCALE.search(context[i - 1]["context"]) if i else None
            found["own" if own else "before" if before else "absent"] += 1

            match = own or before
            if not match:
                continue
            phrases[match.group(0).lower()] = phrases.get(match.group(0).lower(), 0) + 1
            window = element["context"] if own else context[i - 1]["context"]
            start = max(0, match.start() - 120)
            if CARVE_OUT.search(window[start:match.end() + 120]):
                carve_outs += 1

    detected = tables - found["absent"]
    print("\nSCALING NOTES  (all reports, real data tables)")
    print(f"  real data tables                {tables}")
    print(f"    phrase in the table itself    {found['own']:5}  {found['own']/tables:6.1%}")
    print(f"    phrase in the element before  {found['before']:5}  {found['before']/tables:6.1%}")
    print(f"    not found in either place     {found['absent']:5}  {found['absent']/tables:6.1%}")
    print(f"  phrases: {dict(sorted(phrases.items(), key=lambda kv: -kv[1]))}")
    print(f"  CARVE-OUT near the phrase       {carve_outs:5}  {carve_outs/detected:6.1%} of those found")
    print("  -> scale is METADATA, never a multiplier. 'Not found' is a third")
    print("     state and must never be recorded as scale = 1 (data trap 7).")


def main():
    args = sys.argv[1:]
    n_reports = int(args[args.index("--reports") + 1]) if "--reports" in args else PARSE_REPORTS

    claims = list(load_claims())
    names = sorted({c.report for c in claims})
    shuffled = list(names)
    random.Random(SAMPLE_SEED).shuffle(shuffled)

    print("=" * 78)
    print("WHAT pandas.read_html DOES TO SEC FILING TABLES")
    print(f"reports referenced by testmini: {len(names)}   "
          f"parse sample: {n_reports}, seed {SAMPLE_SEED}")
    print("=" * 78)

    measure_mapping(names, shuffled[:ALIGN_REPORTS])
    measure_parse_and_structure(shuffled[:n_reports])
    measure_population(claims)
    measure_scale(names)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
