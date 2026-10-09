# findver-agent

**Accepted to NeurIPS 2026.** *Verifying Financial Claims with On-Device Models* was accepted as a
poster at the NeurIPS 2026 workshop *On-Device Intelligence: Foundation Models under Real-World
Constraints* (ODI 2026). The workshop is non-archival. It takes place on Saturday 12 December 2026 at
the International Convention Centre Sydney.

This repository holds the code, configs, measurement scripts and paper source behind it.

## What the project does

The system checks short financial claims against long SEC filings and answers ENTAILED (the filing
supports the claim) or REFUTED. It is evaluated on the FINDVER benchmark
([yilunzhao/FinDVer](https://github.com/yilunzhao/FinDVer)). The aim is to settle as many claims as
possible on a local device and send only the hard ones to a cloud model. No model is trained or
fine-tuned.

## Method

Each claim goes through the following steps.

1. **Retrieval.** Our own BM25 keyword retriever picks the 10 most relevant passages from the filing.
   The pipeline is retrieval-only. The full filing is never passed to a model.
2. **Two local models.** `qwen2.5-coder:3b` and `qwen2.5-coder:7b`, served through Ollama, each read
   the claim and the passages and give a verdict.
3. **Arithmetic trigger.** A plain-Python detector, with no model involved, flags claims that need
   calculation. Flagged claims always go to the cloud, because both local models tend to fail them
   in the same way.
4. **Disagreement gate.** If the two local models agree, their verdict stands and the claim stays on
   the device. If they disagree, the claim goes to the cloud model, `deepseek-v4-flash`.
5. **Arbiter.** When the two local models disagree, the 7B is asked one more question first. If the
   answer matches the 7B's verdict, the claim stays local. This removes cloud calls.
6. **Audit trigger.** When both local models agree on ENTAILED, two checks look for a shared
   mistake: a plain-Python check for a figure in the claim that appears nowhere in the filing, and a
   local model asked to confirm every detail or name the weakest one. If either fires, the claim goes
   to the cloud. This adds cloud calls and recovers accuracy.

The arbiter and the audit act on separate groups of claims, so they combine without conflict.

## Headline results

All 1,700 claims of the held-out `test.json` split. Every number was measured on one machine, an AMD
RX 7600 XT GPU running Ollama 0.32.9. Full tables and caveats are in `docs/paper_numbers.md`
(§2.31 for the final run).

| system | accuracy | claims sent to the cloud |
|---|---|---|
| Cloud model alone | 77.4% | 100% |
| Routed: gate and arithmetic trigger | 75.8% | 53.4% |
| Routed: plus arbiter and audit | **76.8%** | **44.9%** |

- The full routed system is statistically tied with the cloud model alone (p = 0.58) while making
  44.9% of its cloud calls.
- The tie hides a loss on one subset. On information-extraction claims the gate keeps local, the
  routed system is 8.7 points below the cloud. Two models of the same family tend to make the same
  mistakes, so their agreement is false confidence.
- The routed system is slower per claim on the GPU machine (median 26.0 s against 8.0 s for the
  cloud alone), because both local models run before the gate can compare them.
- The audit trigger's gain is not significant (+9 correct verdicts for 102 extra calls, p = 0.34).
  The arbiter removed 269 cloud calls with no measurable accuracy cost.

Things that were built, measured and dropped, with the evidence, are listed in
`docs/paper_numbers.md` §4.5. The largest was an on-device arithmetic tool, which lost to the cloud by
22 points.

## Next steps

These are directions for an archival follow-up paper. None of them can extend the workshop table,
because the GPU machine that produced it is no longer available and verdicts differ across machines.

1. **Cross-family local pair.** Replace one Qwen model with a model from another family, such as
   Llama or Gemma, and test whether agreement stops hiding shared errors. All three reviewers asked
   for this, and it directly tests the paper's main finding.
2. **Re-run on a second device.** Repeat every arm on the new RTX 5070 Ti laptop with Ollama pinned,
   and check whether the conclusions (the tie, the cloud-call reduction, the extraction-subset loss)
   replicate. This is a full re-run, about 32 hours for the two main runs alone, plus every cloud call
   again.
3. **A second benchmark**, to test whether the routing rule transfers beyond FINDVER.
4. **More skills and routing logic**, each aimed at a named error category and with its ceiling
   measured before it is built.
5. **arXiv preprint and public release** of this repository, after confirming with the organisers.

Current status and open items are tracked in `docs/working_state.md`.

## Setup

The benchmark data is not committed. It is 1.3 GB and already public. Clone it into the project
root at the commit this project was developed against:

```bash
git clone https://github.com/yilunzhao/FinDVer.git
cd FinDVer && git checkout e8bb237 && cd ..
```

The claims are then at `FinDVer/data/` (`testmini.json`, 700 claims, and `test.json`, 1,700) and the
filings at `FinDVer/financial_reports/`.

Ollama versions are pinned per machine, and each config carries `expect_ollama_version` so a run
stops if the version changed. Turn Ollama auto-update off before any run. The paper's results came
from 0.32.9. The development MacBook (macOS 13) cannot go past 0.12.3.

The cloud client reads its API key from the environment. Keys are never committed.

To run an experiment, pass the test harness first, then run one config:

```bash
python3 test_scripts/test_harness.py && \
python3 run.py configs/<name>.json 2>&1 | tee logs/<name>.txt
```

## Layout

```
src/            pipeline code: loader, sampler, retriever, routed loop, arbiter, audit, clients
run.py          entry point, takes one config path
configs/        one config file per experiment
prompts/        versioned prompt templates
test_scripts/   test harness and one measurement script per reported number
docs/           working state, paper numbers, architecture plan, build log
paper/          LaTeX source (workshop.tex is the submitted version), numbers as macros, PDFs
FinDVer/        benchmark data, not tracked, see Setup
results/        per-claim JSON output, not tracked
logs/           console output, not tracked
```
