"""What the professor's DeepSeek key has been spent on, per run and in total.

The key belongs to the professor, so spending on it has to be reportable at any
time and traceable to a run rather than to a lump sum.

Two independent figures, and they answer different questions.

    from result files   exact token counts we recorded, priced at the published
                        USD rates. Attributes every cent to a named experiment.
    live balance        DeepSeek's own number, in CNY, authoritative for what was
                        actually charged.

They will not match exactly. The account is denominated in CNY and DeepSeek's
CNY price list is not the USD list at spot rate, so treat the USD figure as an
attribution of where the money went and the CNY balance as the truth about how
much. Record the balance each time this runs and the delta becomes exact.

Usage:
    python3 test_scripts/api_cost_tally.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "results"

# USD per million tokens, (input cache-miss, output). Published 8 August 2026.
# DeepSeek's pricing page warns of a significant increase, so re-read it before
# quoting any of this. Cache hits are cheaper and are not modelled: every run so
# far reported cached_tokens 0, so assuming all-miss is exact, not conservative.
PRICING = {
    "deepseek-v4-pro": (0.435, 0.87),
    "deepseek-v4-flash": (0.14, 0.28),
}

# Calls made by hand rather than through run.py, so they appear in no result
# file. Recorded here from the printed usage blocks so the tally stays honest.
# 8-9 August 2026: the first real-claim probe, the three-call determinism test,
# and the model-name probes. The rejected DeepSeek-V4-Flash-0731 call returned
# HTTP 400 and was not billed.
AD_HOC = [
    ("deepseek-v4-pro", 3004, 2123, "8 Aug, first real claim, numeric-val-41"),
    ("deepseek-v4-pro", 6, 48, "8 Aug, seed-accepted probe"),
    ("deepseek-v4-pro", 6, 27, "8 Aug, call_deepseek code-path check"),
    ("deepseek-v4-pro", 3004, 1235, "9 Aug, determinism A, seed 0"),
    ("deepseek-v4-pro", 3004, 1357, "9 Aug, determinism B, seed 0"),
    ("deepseek-v4-pro", 3004, 1883, "9 Aug, determinism C, seed 12345"),
    ("deepseek-v4-flash", 6, 20, "9 Aug, flash model-name probe, output estimated"),
]

CNY_PER_USD = 7.2   # rough, for orientation only


def cost(model, prompt_tokens, output_tokens):
    rate_in, rate_out = PRICING[model]
    return prompt_tokens / 1e6 * rate_in + output_tokens / 1e6 * rate_out


def scan_runs():
    """Every results directory whose records were produced by a priced model."""
    rows = []
    for directory in sorted(RESULTS_ROOT.rglob("*")):
        if not directory.is_dir():
            continue
        files = list(directory.glob("*.json"))
        if not files:
            continue

        prompt_tokens = output_tokens = 0
        model = None
        for path in files:
            record = json.loads(path.read_text())
            # results/archive holds decompositions_v1.json, which is one analysis
            # blob rather than a per-claim Record, so it has no config to read
            if not isinstance(record, dict) or "config" not in record:
                break
            model = record["config"].get("model")
            if model not in PRICING:
                break
            prompt_tokens += record.get("prompt_eval_count") or 0
            output_tokens += record.get("eval_count") or 0
        else:
            rows.append((directory.relative_to(RESULTS_ROOT).as_posix(), model,
                         len(files), prompt_tokens, output_tokens))
    return rows


def live_balance():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None, "DEEPSEEK_API_KEY not set, run: source .env"

    request = urllib.request.Request(
        "https://api.deepseek.com/user/balance",
        headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        return None, f"could not read balance: {error}"

    info = data["balance_infos"][0]
    return info, None


def main():
    rows = scan_runs()

    print("\nDeepSeek spend by experiment, from our own recorded token counts")
    print("=" * 96)
    print(f"{'experiment':<40}{'model':<20}{'n':>5}{'in tok':>12}{'out tok':>12}{'USD':>9}")
    print("-" * 96)

    total = 0.0
    for name, model, n, prompt_tokens, output_tokens in rows:
        usd = cost(model, prompt_tokens, output_tokens)
        total += usd
        print(f"{name:<40}{model:<20}{n:>5}{prompt_tokens:>12,}{output_tokens:>12,}{usd:>9.3f}")

    print("-" * 96)
    print(f"{'ad-hoc calls, not in any result file':<40}{'':<20}{len(AD_HOC):>5}"
          f"{sum(r[1] for r in AD_HOC):>12,}{sum(r[2] for r in AD_HOC):>12,}"
          f"{sum(cost(m, i, o) for m, i, o, _ in AD_HOC):>9.3f}")
    for model, prompt_tokens, output_tokens, note in AD_HOC:
        print(f"    {note:<62}{cost(model, prompt_tokens, output_tokens):>9.4f}")

    total += sum(cost(m, i, o) for m, i, o, _ in AD_HOC)
    print("=" * 96)
    print(f"{'TOTAL, estimated':<78}{total:>9.3f} USD")
    print(f"{'':<78}{total * CNY_PER_USD:>9.2f} CNY at {CNY_PER_USD}/USD, rough")

    info, error = live_balance()
    print("\nLive account balance, DeepSeek's own figure")
    print("-" * 96)
    if error:
        print(f"  {error}")
    else:
        print(f"  remaining   {info['total_balance']} {info['currency']}")
        print(f"  topped up   {info['topped_up_balance']}   granted {info['granted_balance']}")
        print("\n  This is what is left, not what was spent. Record it each time this runs;")
        print("  the difference between two readings is the only exact spend figure.")
        print("  Readings, CNY:  9 Aug 142.38 (after the two n=102 runs)")
        print("                 10 Aug 115.42 (after both n=700 runs, delta 26.96)")
        print("                 11 Aug 115.14 (no cloud calls that day; the 0.28 is settlement lag)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
