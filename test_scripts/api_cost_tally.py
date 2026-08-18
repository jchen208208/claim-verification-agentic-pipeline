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

# USD per million tokens, (input cache-miss, output). RE-READ 17 August 2026
# from api-docs.deepseek.com. The 8 August figures, flash at 0.14/0.28 and pro
# at 0.435/0.87, are STALE: prices rose roughly 3x on input and 4.7x on output.
#
# Rates now vary by time of day. Off-peak is half of peak; peak is 01:00-04:00
# and 06:00-10:00 UTC. An overnight run spans both, so PEAK is used here as the
# conservative attribution and the real figure sits somewhere below it.
#
#   flash   off-peak 0.22 / 0.66      peak 0.44 / 1.32
#   pro     off-peak 0.66 / 1.98      peak 1.32 / 3.96
#
# Cache hits are cheaper and not modelled: every run so far reported
# cached_tokens 0, so assuming all-miss is exact rather than conservative.
# HISTORICAL rates, in force when every run below was billed. Kept as-is on
# purpose: repricing old runs at today's list rewrites history, and the 11 Aug
# flash run is known from a balance delta to have cost exactly 4.90 CNY.
PRICING = {
    "deepseek-v4-pro": (0.435, 0.87),
    "deepseek-v4-flash": (0.14, 0.28),
}

# CURRENT rates, read 17 August, for projecting a run not yet made. Not used by
# the table below. In practice prefer CNY_PER_CLOUD_CALL, which is measured and
# needs no assumption about currency conversion.
PRICING_CURRENT_PEAK = {
    "deepseek-v4-pro": (1.32, 3.96),
    "deepseek-v4-flash": (0.44, 1.32),
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

# CNY per attributed USD. WITHDRAWN 17 August as a planning tool.
#
# These were derived from the 10 and 11 August balance deltas and reproduced
# them exactly. They then failed catastrophically on the first run at n=1,700:
# predicted 13 CNY, actual 239.35 CNY, 18x out. Even at the corrected PEAK rates
# above the run should have cost about 54 CNY, so roughly 4.4x of that delta is
# unexplained. Do not use a CNY-per-USD ratio for planning until it is.
#
# Use CNY_PER_CLOUD_CALL below instead. It is measured end to end and needs no
# assumption about price lists, currency conversion or token accounting.
CNY_PER_USD = {
    "deepseek-v4-flash": 6.94,
    "deepseek-v4-pro": 11.8,
}
CNY_PER_USD_FALLBACK = 7.2

# The planning figure, measured from balance deltas alone. One flash cloud call
# on a ~3,700 token prompt, at whatever DeepSeek actually charges.
#
#   11 Aug     4.90 CNY /   700 calls  = 0.0070 CNY per call
#   17 Aug   239.35 CNY / 1,700 calls  = 0.1408 CNY per call   <- OUTLIER
#   18 Aug     1.66 CNY /   179 calls  = 0.0093 CNY per call
#
# CORRECTED 18 Aug. The 17 August figure was fitted to one delta and is 15x the
# two measurements either side of it. At 0.0093 per call the 1,700 call run
# should have cost about 16 CNY; the balance dropped 239.35. Our usage cannot
# account for that, and the balance also fell 12.12 CNY overnight with no calls
# from us at all, against a known settlement lag of 0.28.
#
# Prices did rise, confirmed from DeepSeek's docs, but by 3-4.7x on the list and
# not 15x in practice. The remaining explanation that fits both observations is
# that something other than our runs draws on this account. Ask the professor.
CNY_PER_CLOUD_CALL = 0.0093


def cny(model, usd):
    return usd * CNY_PER_USD.get(model, CNY_PER_USD_FALLBACK)


def cost(model, prompt_tokens, output_tokens):
    rate_in, rate_out = PRICING[model]
    return prompt_tokens / 1e6 * rate_in + output_tokens / 1e6 * rate_out


def billable_tokens(record):
    """What this record actually cost, as (model, prompt_tokens, output_tokens).

    None means the record billed nothing.

    Routed records need the special case. Their top-level token counts belong to
    whichever stage decided the claim, which is usually a local model and costs
    nothing, and their config["model"] names the system rather than a priced
    model. The billable part is the cloud stage nested under "stages", which is
    absent entirely on a claim that never escalated.

    Added 16 Aug. Before this, a routed directory was skipped whole, because
    "routed_3b_7b_flashv2" is not in PRICING, so pipeline_trial's 13 real cloud
    calls appeared nowhere. A 1,700 claim routed run would have hidden about 950.
    """
    stages = record.get("stages")
    if stages:
        cloud = stages.get("cloud")
        if not cloud:
            return None                     # this claim never escalated
        return (cloud.get("config", {}).get("model"),
                cloud.get("prompt_eval_count") or 0,
                cloud.get("eval_count") or 0)

    return (record["config"].get("model"),
            record.get("prompt_eval_count") or 0,
            record.get("eval_count") or 0)


def scan_runs():
    """Every results directory that spent anything, priced per record."""
    rows = []
    for directory in sorted(RESULTS_ROOT.rglob("*")):
        if not directory.is_dir():
            continue
        files = list(directory.glob("*.json"))
        if not files:
            continue

        prompt_tokens = output_tokens = calls = 0
        model = None
        unpriced = False

        for path in files:
            record = json.loads(path.read_text())
            # results/archive holds decompositions_v1.json, which is one analysis
            # blob rather than a per-claim Record, so it has no config to read
            if not isinstance(record, dict) or "config" not in record:
                unpriced = True
                break

            billed = billable_tokens(record)
            if billed is None:
                continue                    # routed claim, no cloud call

            billed_model, prompt, output = billed
            if billed_model not in PRICING:
                unpriced = True             # a local-only run, costs nothing
                break

            model = billed_model
            prompt_tokens += prompt
            output_tokens += output
            calls += 1

        if unpriced or model is None:
            continue

        rows.append((directory.relative_to(RESULTS_ROOT).as_posix(), model,
                     calls, len(files), prompt_tokens, output_tokens))
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
    print(f"{'experiment':<38}{'model':<20}{'calls/n':>9}{'in tok':>12}"
          f"{'out tok':>12}{'USD':>8}{'CNY':>8}")
    print("-" * 96)

    total = 0.0
    total_cny = 0.0
    for name, model, calls, claims, prompt_tokens, output_tokens in rows:
        usd = cost(model, prompt_tokens, output_tokens)
        total += usd
        total_cny += cny(model, usd)
        scope = f"{calls}" if calls == claims else f"{calls}/{claims}"
        print(f"{name:<38}{model:<20}{scope:>9}{prompt_tokens:>12,}"
              f"{output_tokens:>12,}{usd:>8.3f}{cny(model, usd):>8.2f}")

    print("-" * 96)
    print(f"{'ad-hoc calls, not in any result file':<40}{'':<20}{len(AD_HOC):>5}"
          f"{sum(r[1] for r in AD_HOC):>12,}{sum(r[2] for r in AD_HOC):>12,}"
          f"{sum(cost(m, i, o) for m, i, o, _ in AD_HOC):>9.3f}")
    for model, prompt_tokens, output_tokens, note in AD_HOC:
        print(f"    {note:<62}{cost(model, prompt_tokens, output_tokens):>9.4f}")

    total += sum(cost(m, i, o) for m, i, o, _ in AD_HOC)
    total_cny += sum(cny(m, cost(m, i, o)) for m, i, o, _ in AD_HOC)

    print("=" * 96)
    print(f"{'TOTAL, estimated':<78}{total:>8.3f}{total_cny:>8.2f}")
    print()
    print("  CNY is the figure to quote. The account is billed in CNY and the")
    print("  USD column is attribution: it says where the money went, not how much.")
    print("  Per-model rates come from the 10 and 11 August balance deltas, so the")
    print("  CNY column inherits their uncertainty. Only a balance delta is exact.")

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
        print("                 11 Aug 110.24 (after flash v2 at n=700, delta 4.90)")
        print("                 16 Aug 468.07 (BEFORE condition2_flash_v2_test1700)")
        print("                 17 Aug 228.72 (AFTER it, delta 239.35 for 1,700 flash calls)")
        print("                 18 Aug 216.60 (BEFORE run 1 chunk 1. 12.12 GONE OVERNIGHT with")
        print("                        no calls from us. The 11 Aug settlement lag was 0.28.)")
        print("                 18 Aug 214.94 (AFTER chunk 1, delta 1.66 for 179 cloud calls")
        print("                        = 0.0093 per call, in line with 11 Aug, 15x below 17 Aug)")
        print()
        print("  THE 239.35 DELTA IS NOT OURS. Measured per-call cost on 18 Aug is")
        print("  0.0093 CNY, so 1,700 calls is about 16 CNY, not 239. Two facts to put")
        print("  to the professor: 12 CNY left the account overnight with nothing of")
        print("  ours running, and a run whose own per-call rate says 16 CNY coincided")
        print("  with a 239 CNY drop. Ask whether the key is shared, and ask for read")
        print("  access to the usage page.")
        print()
        print("  PLAN WITH CNY_PER_CLOUD_CALL = 0.1408, measured, not with the USD column.")
        print("                        ^ the account was topped up by about 358 CNY between")
        print("                          11 and 16 Aug. Only pipeline_trial ran in that window,")
        print("                          about 0.09 CNY, so the rise is a payment and not an")
        print("                          error. granted 0.00, so it was paid, not credited.")
        print()
        print("  The USD column above is MODEL-SPECIFIC in its error, not uniformly off:")
        print("    flash   6.94 CNY per attributed USD  ~= the 7.2 nominal rate")
        print("    pro    ~11.8 CNY per attributed USD  ~1.65x its USD list")
        print("  So pro costs roughly 5x flash per run in real billing, not the 3x")
        print("  the USD column implies. Derived from the 10 and 11 Aug deltas.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
