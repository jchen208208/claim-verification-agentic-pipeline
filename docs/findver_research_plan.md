# FINDVER Claim Verification Project — Complete Plan & Reference Document

**Project:** LLM agents / skills for verifying financial claims against long, hybrid-content documents (FINDVER benchmark)
**Context:** Two-month remote research internship. Professor expects the student to propose solution ideas first; professor will refine. Possible outcomes: academic paper (stretch), technical blog post, or research report.
**Prepared:** July 2026

---

## 1. Project Overview

Unverified claims about companies' financial performance circulate online and can mislead investors. Verifying such claims requires checking them against primary sources — SEC filings like 10-K (annual) and 10-Q (quarterly) reports. These documents are long (~41,000 words on average), dense, and *hybrid*: they mix narrative text with ~79 tables per document.

The FINDVER benchmark (Zhao et al., EMNLP 2024, Yale NLP) tests whether LLMs can (1) classify a claim as **entailed** or **refuted** by a given financial document, and (2) generate a step-by-step **explanation** of the reasoning. At publication time, the best model (Claude-3.5-Sonnet) reached **77.2%** accuracy vs. **93.3%** for human financial experts (CFA holders) — a large gap.

**Our goal:** build an LLM agent equipped with purpose-built *skills* (code execution, structured table querying, decomposed retrieval, a finance glossary, a faithfulness verifier) that closes part of this gap — and, regardless of the final accuracy number, produces a rigorous analysis of *which* interventions fix *which* error types.

---

## 2. The FINDVER Benchmark in Detail

### 2.1 Task formulation
Given a financial document *d* (text *P* + tables *T*) and a claim *c*:
1. **Entailment classification:** output label ∈ {entailed, refuted} (binary — no "not enough info" class).
2. **Reasoning-process explanation:** generate a natural-language explanation grounded solely in the document.

### 2.2 Three subsets (each mirrors a real-world scenario)
| Subset | Skill tested | Example difficulty |
|---|---|---|
| **FDV-IE** (information extraction) | Locating facts across text + tables in a long document | Evidence scattered; avg ~1.8 text + 1.0 table evidence pieces per claim |
| **FDV-MATH** (numerical reasoning) | Calculations / statistical analysis over document data | e.g., "customers 120+ days past due increased by 65,300 from Mar 31 2023 to Mar 31 2024" — requires two lookups + subtraction |
| **FDV-KNOW** (knowledge-intensive) | Applying external finance domain knowledge / regulations | Longest explanations (avg ~100 words); most text evidence (~2.6 pieces) |

### 2.3 Key statistics
- 2,400 expert-annotated examples total: **testmini** = 600 (200/subset, public, for development) and **test** = 1,500 (500/subset, labels withheld; scored via an online leaderboard).
- Documents: 10-K/10-Q filings first released Jan–Apr 2024 (chosen to post-date most 2024-era training cutoffs, reducing contamination — but see §10.3 for why this no longer holds for 2026 models).
- ~66–71% of claims require table evidence. Tables were serialized as flattened pipe-delimited text — the authors themselves flag this as a limitation.
- Annotated by financial professionals; refuted claims created by expertly perturbing entailed claims so the error is directly contradicted by annotated evidence.
- Every example includes gold **evidence labels** (indices of relevant paragraphs/tables) — this is what makes retrieval recall directly measurable (§3.4).

### 2.4 Original results worth memorizing
- Best model: Claude-3.5-Sonnet, 77.2% (long-context) / 75.0% (RAG) on testmini; GPT-4o close behind.
- Human expert 93.3%; human non-expert 86.7%; random 50%.
- **Long-context beat RAG for the strongest models** but RAG beat long-context for weaker models. Interpretation: frontier models can *find* evidence in a full document; their bottleneck is reasoning/computation over it. This is a clue that tool-use may be higher leverage than retrieval for strong models — verify early.
- Chain-of-Thought prompting adds ~5–7 accuracy points over direct labeling (so all our baselines use CoT).
- Their error taxonomy from manual analysis of Claude-3.5-Sonnet failures — **this is our organizing instrument**:
  1. **Extraction error** — wrong/missed information retrieved from context
  2. **Numerical reasoning error** — wrong mathematical approach
  3. **Domain knowledge deficiency** — missing finance knowledge
  4. **Computation error** — right reasoning, wrong arithmetic

---

## 3. Core Concepts (plain-language reference)

### 3.1 LLM agent
A system in which the model decides, **in a loop**, which action or tool to invoke next (retrieve more evidence, run code, re-plan, verify) based on intermediate results — instead of producing one answer in a single pass. In practice, for a fixed pipeline like ours, an "agent" is a Python script that calls LLM APIs several times with different system prompts, with branching (e.g., retry on error) between calls.

### 3.2 LLM skill
A packaged, reusable capability — instructions plus optionally scripts or reference material — loaded into the model's context to make it reliably good at one specific procedure. In this project each pipeline module (claim decomposition, table querying, numerical verification, glossary lookup, faithfulness checking) is framed as a skill that the agent orchestrates. This framing matches the professor's own "agents and skills" language.

### 3.3 Long-context vs. RAG settings
- **Long-context:** feed the entire ~41K-word document into the model. Expensive per call; possible only for large-context models; precise cell-level lookup degrades in huge contexts ("lost in the middle").
- **RAG (retrieval-augmented generation):** embed the claim, retrieve the top-k (k=10 in FINDVER) most similar paragraphs/tables, and show only those to the model. Cheap, but capped by retrieval quality.

### 3.4 Recall and the "recall ceiling"
**Recall** = of all gold evidence pieces needed for a claim, what fraction did retrieval actually fetch? Published FINDVER retrieval (OpenAI text-embedding-3, k=10) achieves only **~68–70% evidence recall** (67.91% testmini / 69.53% test, per MACE). So for roughly **3 in 10 claims, at least one required piece of evidence never reaches the model** — a hard accuracy ceiling no reasoning improvement can break through. Every published approach copied this retrieval setup rather than improving it. Because gold evidence labels exist, retrieval improvements can be measured **in isolation, cheaply, without running the full pipeline** — a clean, self-contained reportable number.

### 3.5 Why "in-head" LLM math fails (and what code execution changes)
An LLM is a next-token predictor: when it writes `210,600 − 145,300 =`, no arithmetic circuit runs — it generates the digits that are *statistically likely* to follow, based on patterns in training data. For large/uncommon numbers this is unreliable, and errors carry no signal (the model is equally confident either way). It can also mis-transcribe numbers mid-generation. **Code execution** changes the division of labor: the LLM *writes* a short program (a pattern task it is excellent at), a real Python interpreter *executes* it deterministically on the CPU, and the guaranteed-correct output is fed back into the model's context. Analogy: an accountant using a calculator — not because they can't subtract, but because the calculator's error rate is zero. Established technique names: **Program-of-Thought (PoT)** and **PAL (Program-Aided Language Models)**, 2022–2023.

Note: in a raw-API pipeline there is no built-in sandbox — *we* must extract the code the model writes, execute it (restricted `exec` or subprocess), and feed results back. That loop **is** the code-execution skill (~30 lines of Python).

### 3.6 Table querying (tables as data, not prose)
All published FINDVER approaches hand tables to the model as text (pipe-delimited or HTML), forcing it to "visually" locate cells — a major source of extraction errors across 79 tables/document. Instead: parse each table into a **pandas DataFrame** (a spreadsheet inside Python with named rows/columns). The LLM then writes a lookup, e.g.:

```python
val_2024 = df.loc["120+ days past due", "Mar 31, 2024"]   # → 210600
val_2023 = df.loc["120+ days past due", "Mar 31, 2023"]   # → 145300
print(val_2024 - val_2023)                                 # → 65300 (CPU-computed)
```

`.loc[row_label, column_label]` fetches exactly one cell by its labels (like `=B4` in Excel but addressed by name). The lookup either returns the exact value or throws an error — it cannot "sort of" grab a neighboring cell the way reading can. Extraction *and* computation both become deterministic; the LLM's remaining job is the language task it is good at: mapping claim phrases ("over 120 days past due") to actual table labels.

Practical realities: (a) SEC tables are messy — merged headers, footnotes, "in thousands" scaling — so parsing is genuine engineering work; imperfect parsing with fallback to raw text is fine for v1. (b) Label mismatch is the residual difficulty ("over 120 days" vs "120+ days past due"): print `df.index` / `df.columns` into the model's context so it writes lookups against *real* labels, and feed lookup errors back for a retry — a natural mini feedback loop.

### 3.7 Claim-decomposed retrieval
Standard RAG embeds the *whole claim* as one query — a blurry average when the claim needs multiple facts (e.g., a 2023 figure and a 2024 figure that live in different places). **Decomposition:** an LLM first splits the claim into atomic facts + the operation connecting them; retrieval then runs **separately per fact** and results are merged. Each query becomes sharp instead of blurry.

### 3.8 Hybrid retrieval (BM25 + embeddings)
Financial evidence hinges on exact strings — "120 days", specific dates, exact figures — which dense embeddings blur. **BM25** is classical keyword search that rewards exact token matches. Running both and merging (e.g., reciprocal rank fusion) typically raises recall on number-heavy domains. No training required; a library call.

### 3.9 Explanation faithfulness (vs. label correctness)
Two different things a verifier can check:
- **Label correctness / internal coherence** (what MACE's Verifier does): does the verdict follow from the stated reasoning?
- **Faithfulness** (the open gap): is **every individual step grounded in the document**? Concretely: for each cited figure, check it actually appears in the cited table/paragraph at the right coordinates; re-run each arithmetic step independently; confirm the final comparison. LLMs can produce the *right label with wrong reasoning* (hallucinated figures, lucky verdicts) — in finance, a plausible explanation with a fabricated number is arguably worse than a wrong answer. FINDVER's authors evaluated explanations only with human raters and **explicitly call for automated explanation-error detection** in their limitations section. Nobody has answered that call. Caveat: the verifier is itself an LLM and can err — hence a stretch goal, but even catching obvious fabricated numbers adds value, and it doubles as an **evaluation metric** ("X% of explanation steps are verifiable against the document").

### 3.10 Frameworks (AutoGen etc.) vs. plain scripts
- **Framework (AutoGen / LangGraph / CrewAI):** library providing pre-built multi-agent plumbing — define agents with roles, register tools, the library runs the conversation loop, message passing, retries, termination. MACE used AutoGen.
- **Plain script:** you write the loop yourself; every LLM call, branch, and retry is a visible line of your code.
- **Decision: start plain.** Our pipeline is 4–5 LLM calls with simple branching (~200 lines). Frameworks add a learning curve, hide control flow (painful to debug), and their APIs churn. Plain code teaches how agents actually work and is trivially migratable later. Mention at the meeting that AutoGen was considered (it's what MACE used) but plain implementation was chosen for debuggability — defensible and usually respected.
- **Steal one framework habit regardless: log everything** — every prompt, response, retrieved chunk, executed code snippet, per example, to disk. These traces are the raw material for error analysis.

### 3.11 Data contamination
2026 models may have trained on the Jan–Apr 2024 SEC filings *and possibly the public testmini set with labels*. Diagnostic: ask the model to verify claims **with the evidence withheld** — above-chance accuracy without evidence is a contamination smoking gun. Relevant both as a caveat on high baselines and as a potential standalone analysis (§10.3).

---

## 4. Why LLMs Fail on FINDVER — the Diagnosis That Organizes Everything

"Verify this claim" secretly bundles four competencies that a single forward pass must interleave in natural language:

| # | Competency | FINDVER error category it maps to | Our fix |
|---|---|---|---|
| 1 | **Locate** relevant evidence in ~41K words / ~79 tables | Extraction error (also: retrieval recall ceiling) | Claim-decomposed hybrid retrieval; table-aware indexing |
| 2 | **Extract** precise values from hybrid text+tables | Extraction error | Tables parsed to DataFrames; deterministic `.loc` lookups |
| 3 | **Compute** over extracted values | Computation error (+ part of numerical reasoning error) | Code execution (PoT-style) |
| 4 | **Apply domain knowledge** (accounting terms, regulations) | Domain knowledge deficiency | Retrievable finance glossary/rulebook skill |

**Core thesis of the project:** externalize each competency to a component that is actually good at it, leaving the LLM to do orchestration and genuine judgment (which rows matter, what operation the claim requires) rather than table-scanning and arithmetic in its head.

Supporting observation from the original paper: the strongest models did **better with the whole document than with RAG** — suggesting that for frontier models the bottleneck is reasoning/computation over evidence, not finding it. For weaker/cheaper models the reverse held. Both retrieval and reasoning interventions therefore matter, and they **multiply rather than add**: better retrieval mostly rescues examples the reasoner would have solved *if it had seen the evidence* — another reason to measure the two stages separately.

---

## 5. Related Work Since FINDVER (what exists, and its weaknesses)

### 5.1 MACE (Saha, Lakshmanan & Ng, UBC — arXiv 2604.17225, 2026) — the main competitor
- **What it is:** Multi-Agentic framework for Claim vErification. Three agents — **Planner** (devises step-by-step strategy; handles negations, ambiguous descriptors, compound claims), **Executor** (implements plan, produces provisional verdict), **Verifier** (audits coherence, approves or requests correction) — plus a User agent, built on **AutoGen** with constrained speaker transitions. Feedback loops: Executor can request plan revisions; Verifier can request corrections (mitigates error propagation of one-way pipelines). **Zero-shot CoT prompts only — no training.** Evaluated directly on FINDVER testmini and test (plus SciTab, SemTabFacts). Claims SOTA/parity, with smaller open models (27–92B) reaching 80–100% of a 235B model's performance.
- **Weakness 1 — no code execution.** The Executor "performs computations" *inside its natural-language explanation* — summing seven six-digit figures in prose in their own published example, which even contains an apparent transcription slip (1,099,107 vs 1,999,107 two lines apart). The computation-error category is left entirely unaddressed by the current best approach.
- **Weakness 2 — retrieval untouched.** They state retrieval "is not our focus" and copy FINDVER's setup (text-embedding-3, k=10), reporting **67.91% / 69.53% evidence recall** — the ceiling sits unattacked.
- **Weakness 3 — tables still prose.** Tables converted to HTML text; no structured querying.
- **Weakness 4 — nothing for FDV-KNOW.** No knowledge component.
- **What it proves for us:** a zero-shot, prompt-only, no-training approach is publishable on this benchmark — exactly our resource profile.

### 5.2 TART (Lu et al., NAACL 2025 Findings)
Tool-Augmented Reasoning for Tables: a **table formatter** (accurate representation), a **tool maker** (generates executable code for table computations), an **explanation generator**. Philosophically our closest ancestor for the tables-as-data idea. **Limitations for our purposes:** all modules are **fine-tuned** (Llama/CodeLlama/Deepseek-Coder backbones on a custom ToolTab dataset) — out of reach without training compute; and it was evaluated on **single-table, closed-domain** benchmarks (SciTab, TabFact-style), never on long hybrid documents like FINDVER. We borrow the insight, not the method: implement tables-as-data zero-shot.

### 5.3 FISCAL (Sharma et al., 2025)
Synthetic-data framework that **trains a lightweight verifier** for numerical financial claims. Requires training → not our lane; also frames verification as classification, not explanation.

### 5.4 FinVerBench (2026)
Notes that FINDVER and FISCAL frame verification as classification rather than numerical consistency checking across statements. Useful for positioning; different task.

### 5.5 Adjacent table-reasoning methods (baseline citations to know)
- **PoT / PAL (2022–23):** foundational program-execution-for-math papers — the canonical citations for our code-execution skill.
- **ProTrix:** plan-then-reason; routes steps to program-based or textual execution.
- **OpenTab:** BM25 retrieval + SQL generation over tables (same tables-as-data philosophy, SQL flavor).
- **GraphOTTER:** graph representations for tables with merged/nested cells.
- **TableRAG, TableGPT2:** retrieval/pretraining approaches for large-table contexts (training-heavy).

### 5.6 The gap statement (one sentence for the meeting)
> No published FINDVER approach executes code for arithmetic, parses tables into queryable structures, attacks the ~68% retrieval-recall ceiling, targets FDV-KNOW with a knowledge component, or evaluates explanation faithfulness — despite the benchmark's own error analysis and limitations section pointing at exactly these gaps.

**Honesty requirements when using this claim:**
1. Never say "first to use a Python script for arithmetic" — PoT/PAL made the technique standard years ago. Correct framing: *"an established technique (PoT/PAL) that no published approach has applied to FINDVER, whose own error analysis shows it is needed."* Most applied NLP papers are "known technique, new setting, careful analysis" — a respectable contribution class.
2. The literature search here is not exhaustive. **Week-1 due diligence:** check the FINDVER online leaderboard for recent entries, and run a Google Scholar "cited by FINDVER" sweep (an afternoon's work) before repeating any "no one has done X" claim.
3. Sit with "why hasn't anyone done the obvious thing?" Likely answer: niche benchmark, only ~18 months old, field moved fast. But possible answer: someone tried and gains were small — e.g., if most FDV-MATH errors are actually *extraction* failures (wrong numbers pulled) rather than *computation* failures (right numbers, bad math), code execution alone fixes less than hoped and table querying carries the weight. **Our ablation reveals which — and either outcome is a finding.**

---

## 6. Proposed Architecture — Agent + Skills

MACE-style orchestration (Planner → Executor → Verifier with feedback loops), where the Executor does **not** work in its head but invokes skills:

```
                    ┌──────────────────────────────────────────┐
 claim ──► [Skill 1: Claim Decomposer]                          │
                │  atomic facts + required operation            │
                ▼                                               │
           [Skill 2: Retriever]  hybrid BM25+dense, per fact    │
                │  candidate paragraphs + tables                │ feedback
                ▼                                               │ loops
           [Skill 3: Table Normalizer]  tables → DataFrames     │ (retry on
                │                                               │  lookup
                ▼                                               │  error /
           [Agent core: Planner → Executor]                     │  missing
                │  writes Python: .loc lookups + arithmetic     │  evidence /
                ▼                                               │  unfaithful
           [Skill 4: Code Sandbox]  executes, returns results ──┤  step)
                │                                               │
           [Skill 5: Glossary Lookup]  finance terms on demand ─┤
                │                                               │
                ▼                                               │
           [Skill 6: Faithfulness Verifier]                     │
                │  per-step grounding check ────────────────────┘
                ▼
        verdict + evidence-cited explanation
```

### Skill specifications
1. **Claim Decomposer** — one LLM call: claim → numbered atomic facts (entity, metric, time period) + connecting operation. Feeds both retrieval and the explanation template (mirrors FINDVER's own annotation format: extract → reason step-by-step → label).
2. **Retriever** — per-fact queries; BM25 (e.g., `rank_bm25`) + dense embeddings, merged via reciprocal rank fusion; table-aware chunking (keep tables whole, index them with header/unit/period metadata). Evaluated standalone against gold evidence labels.
3. **Table Normalizer** — SEC HTML/serialized tables → pandas DataFrames; preserve units and scaling notes ("in thousands"); fallback to raw text when parsing fails.
4. **Code Sandbox** — extract fenced Python from model output; execute in restricted environment (whitelisted builtins, no network/filesystem, timeout); return stdout/errors to the model; retry loop on exceptions (feed the traceback back).
5. **Glossary Lookup** — small retrievable KB of finance definitions/accounting rules (bootstrapped from investopedia-style definitions + terms harvested from FDV-KNOW dev errors); consulted when the Planner flags an unfamiliar term. Cheapest possible attack on FDV-KNOW; more inspectable than fine-tuning.
6. **Faithfulness Verifier** — post-hoc pass over the explanation: for each step, (a) check cited figures exist at cited coordinates (deterministic where DataFrames exist), (b) re-execute arithmetic, (c) check the final comparison. Outputs per-step grounded/ungrounded; can trigger one retry. Doubles as the faithfulness *metric*.

### Explicit non-goals
No fine-tuning or pretraining of any kind (no compute, and MACE proves it unnecessary). No framework dependency (plain Python + API SDKs). No attempt to beat long-context frontier models at any cost — cost-efficiency is part of the story (professor's model list: OpenAI, Gemini, DeepSeek, Qwen).

---

## 7. Build Order — One Module at a Time (the ablation IS the paper)

Add modules incrementally and measure each delta. Rationale: (a) if everything is built at once and accuracy moves, you cannot say why; (b) a table like "baseline 71% → +code exec 76% → +decomposed retrieval 79% → +glossary 80%" is a publishable result structure — one undifferentiated system is not; (c) each module maps to a named FINDVER error category, so ablations align with the original taxonomy — a very clean story.

| Tier | Module(s) | Error category attacked | Expected payoff / risk |
|---|---|---|---|
| 0 | **Baseline**: plain CoT, 1–2 modern models, RAG setting, ~100 testmini examples | — (reference point) | Mandatory; also answers "has 2026 closed the gap?" |
| 1 | **Code execution + tables-as-DataFrames** (one combined skill in practice) | Computation + extraction | Highest certainty of gain; attacks the two biggest categories; unaddressed by MACE |
| 2 | **Claim-decomposed + hybrid retrieval** | Recall ceiling (extraction) | Clean standalone metric (recall vs. gold labels); nobody has attacked it |
| 3 | **Glossary skill** | Domain knowledge | Smallest expected gain, most novel angle (FDV-KNOW untouched) |
| 4 | **Faithfulness verifier** | Explanation quality (new metric) | Stretch; answers the authors' own call; becomes centerpiece under Backup Plan A |

Working principles: iterate on a ~100-example slice of testmini (keeps cost near zero, fast feedback); label every failure with the four-category taxonomy each round so you know which module to fix next; keep full traces (§3.10).

---

## 8. Evaluation Plan

**Primary metrics**
- Entailment accuracy: overall + per subset (IE / MATH / KNOW), testmini during development; final run on the 1,500-example test set via the online leaderboard.
- Evidence recall: retrieved chunks vs. gold evidence labels — reported per retrieval variant (whole-claim dense / +BM25 / +decomposition).
- Faithfulness: % of explanation steps verifiable against the document (our new metric, if Tier 4 lands).
- Cost: $ and tokens per example, per model — supports the efficiency story.

**Comparisons**
- FINDVER originals (Claude-3.5-Sonnet 77.2, GPT-4o 75.7, humans 93.3/86.7).
- MACE's published FINDVER numbers.
- Our baseline (modern models, no skills) vs. each ablation tier.
- Cheap open models (DeepSeek/Qwen) + skills vs. expensive frontier model without skills.

**Error analysis protocol:** every iteration, sample ≥25 failures, hand-label with the four categories, track the distribution over time. This is the evidence for "module X fixed category Y."

---

## 9. Backup Plans — What If the 2026 Baseline Is Already Very High?

First, why full saturation is unlikely: (1) the ~68–70% recall ceiling caps RAG accuracy regardless of model intelligence; (2) precise cell-level lookup in 41K-word contexts still degrades ("lost in the middle"); (3) FDV-KNOW needs niche accounting knowledge with no completeness guarantee. Realistic expectation: modern models land above 77% but visibly below 93%, with the gap concentrated in identifiable places — the ideal scenario.

If the baseline nevertheless comes back at ~90%+ (in order of preference):

**A. Pivot the metric: accuracy → faithfulness.** Labels can saturate while explanations remain unreliable (right label, hallucinated reasoning). Nobody has measured explanation faithfulness on FINDVER; the authors explicitly requested it. "Labels are nearly solved — are the explanations trustworthy?" is arguably the *more* interesting 2026 paper, especially in finance. The verifier skill graduates from stretch goal to centerpiece.

**B. Pivot the question: accuracy → cost-efficiency.** Do DeepSeek/Qwen at ~1/50th the cost match frontier models *when equipped with our skills*? Real financial firms care about cost-per-verification; fits the professor's stated model list perfectly. The architecture becomes the thing that closes the *cost* gap.

**C. Contamination analysis.** 2026 models may have trained on the 2024 filings and the public testmini labels. Evidence-withheld probing (above-chance accuracy without evidence = smoking gun) is a respected paper genre and strengthens any other result even as a short section.

**D. Characterize residual errors.** Even 90% leaves ~150 failures on the test set. If they cluster (multi-table aggregation, fiscal-vs-calendar-year confusion, unit scaling), documenting the cluster and building one targeted skill for it is a tight contribution — small remaining gaps are often the hard, interesting core.

**E. (Last resort) Benchmark extension.** Adversarial/compositional variants of FINDVER claims that break current models. Most work, needs annotation care; fallback only.

**Key structural point:** all five plans reuse the same infrastructure (pipeline, retrieval measurement, code-execution skill, logging, taxonomy analysis). The baseline experiment is not a gamble — it is a fork where both directions are paved. Frame it exactly this way in the meeting: *"Weeks 1–2 establish the modern baseline; if the gap persists we attack it with the skills architecture; if it is largely closed we pivot to faithfulness and cost-efficiency — the infrastructure is shared either way."*

---

## 10. Practical & Engineering Notes

1. **API access:** a Claude Pro plan is NOT API access; benchmarks need pay-per-token API keys. Professor's model list (OpenAI, Gemini, DeepSeek, Qwen) is deliberately budget-friendly — DeepSeek/Qwen are very cheap. Confirm budget/keys at the meeting; development iterations on a 100-example RAG-setting slice should cost tens of dollars, not thousands. Long-context runs on full 41K-word docs are the expensive mode — use sparingly.
2. **Dataset acquisition:** paper's repo at github.com/yilunzhao/FinDVer; testmini (600, with labels) public; test labels withheld — final scores via the online evaluation platform/leaderboard. Check the leaderboard in week 1 for recent 2025–26 entries before running the suspenseful baseline yourself.
3. **Table parsing:** expect merged headers, footnote markers, "(in thousands)" scaling, blank spacer rows. Budget real time; ship an imperfect parser with raw-text fallback rather than blocking on perfection.
4. **Sandbox safety:** restricted exec (whitelist builtins, no imports beyond pandas/math, timeout ~10s); never execute model code with filesystem/network access.
5. **Determinism:** temperature 0 for all pipeline calls; fix retrieval seeds; version prompts in git.
6. **Reproducibility:** one config file per experiment; results as JSON per example; a single script regenerates every table in the report.
7. **Verdict extraction:** enforce a fixed final-line format ("Therefore, the claim is {entailed|refuted}.") like the original paper, so no GPT-4o post-processing step is needed (MACE's structured outputs made this unnecessary too).

---

## 11. Timeline — 8 Weeks (two-month internship)

**Week 1 — Onboarding & due diligence**
Read FINDVER thoroughly (annotation pipeline, taxonomy, both prompt figures). Download dataset; load testmini; reproduce dataset statistics as a sanity check. Check the online leaderboard; Google Scholar sweep of papers citing FINDVER (verify all "nobody has done X" claims). Skim MACE, TART, PoT/PAL. Deliverable: 1–2-page dataset-analysis note (practical value + core difficulties) — this is Professor Task #1.

**Week 2 — Baseline (Tier 0)**
Build the plain pipeline: RAG retrieval (replicate text-embedding-3-style dense top-10 or nearest available), CoT prompt from the paper's Figure 3, verdict parsing, logging harness. Run 1–2 modern cheap models on ~100 testmini examples (stratified across subsets). Hand-label ~25 failures with the taxonomy. Deliverables: baseline accuracy + error distribution; **the prep memo + meeting with professor** (proposal deck: gap statement, architecture, tiers, backup plans, questions — see §12).

**Weeks 3–4 — Tier 1: code execution + DataFrames**
Build the table normalizer and sandbox; prompt the model to emit Python for lookups/arithmetic; implement the error-feedback retry loop. Measure the delta, especially on FDV-MATH; re-label failures. Decision point: if extraction (not computation) dominates remaining FDV-MATH errors, prioritize retrieval/table work over further compute polish. Deliverable: first ablation row + updated error distribution.

**Weeks 5–6 — Tier 2: retrieval**
Implement claim decomposition; add BM25 + rank fusion; table-aware chunking with metadata. Measure evidence recall standalone against gold labels (target: meaningfully above 68–70%), then end-to-end accuracy. Deliverable: recall table (three retrieval variants) + second ablation row. Mid-project sync with professor; choose final-story emphasis (gap-closing vs. backup plan A/B) based on numbers so far.

**Week 7 — Tier 3 + Tier 4 (scope by remaining time)**
Glossary skill: harvest terms from FDV-KNOW dev failures, build small KB, wire lookup; measure FDV-KNOW delta. Faithfulness verifier v1: per-step grounding checks on top of DataFrame citations; report faithfulness % for baseline vs. full system (this number is valuable even if the inference-time retry is cut for time).

**Week 8 — Final evaluation & writing**
Freeze the system; run the full testmini (600) with the best configuration; submit to the leaderboard for official test-set numbers if budget allows. Final error analysis (taxonomy distribution: before vs. after). Write the report/blog/paper draft: intro → related work (§5) → method (§6) → ablations (§7/§8 tables) → analysis → limitations. Deliverable: complete draft + reproducible repo.

**Slack & risk buffers:** table parsing overruns → cut Tier 3 first, then the verifier's retry loop (keep its metric). Baseline comes back ≥90% in week 2 → invoke Backup Plans A/B immediately; weeks 3–6 work is unchanged (same infrastructure), only the framing and week-7 emphasis shift.

---

## 12. Meeting Prep — Bring This

A 2–3 page memo or ~6 slides:
1. Dataset analysis (value + difficulties, one paragraph each) — assigned Task #1.
2. Related work since FINDVER: MACE / TART / FISCAL, one line each on what they did and left open.
3. The gap statement (§5.6) — carefully worded per the honesty requirements.
4. Architecture diagram (§6) + tiered build plan (§7), cheapest first.
5. Backup plans (§9) — presented as a built-in contingency, which reads as maturity, not hedging.
6. Questions for the professor:
   - What API budget/keys will I have access to?
   - Plain-script implementation vs. a framework — any preference? (State the plain-script rationale.)
   - Target outcome — workshop paper vs. blog/report — since it shapes evaluation rigor?
   - Should the final leaderboard submission be in scope for the two months?
   - Any preferred models beyond the list in the email?

Present the full agent-with-skills architecture as the destination and the incremental ladder as the plan — ambitious vision, disciplined execution, which is exactly what "take the lead to propose ideas" is asking for.

---

## 13. Key Numbers Cheat Sheet

| Fact | Number |
|---|---|
| Benchmark size | 2,400 (testmini 600 / test 1,500) |
| Doc length | ~41K words avg (max 71K); ~79 tables/doc |
| Best 2024 model (Claude-3.5-Sonnet, long-context, testmini) | 77.2% |
| Human expert / non-expert | 93.3% / 86.7% |
| CoT gain over direct output | ~5–7 pts |
| Published evidence recall (text-embedding-3, k=10) | 67.91% (testmini) / 69.53% (test) |
| Claims requiring table evidence | 66–71% |
| MACE model sizes | 27–92B reaching 80–100% of 235B performance |

## 14. Reference List (to expand in week 1)

- Zhao et al., 2024. *FINDVER: Explainable Claim Verification over Long and Hybrid-Content Financial Documents.* EMNLP 2024. github.com/yilunzhao/FinDVer
- Saha, Lakshmanan, Ng, 2026. *A Multi-Agent Approach for Claim Verification from Tabular Data Documents (MACE).* arXiv:2604.17225.
- Lu et al., 2025. *TART: An Open-Source Tool-Augmented Framework for Explainable Table-based Reasoning.* Findings of NAACL 2025. github.com/XinyuanLu00/TART
- Sharma et al., 2025. *FISCAL* (synthetic-data financial fact-checking verifier).
- Chen et al., 2022. *Program of Thoughts (PoT)*; Gao et al., 2022. *PAL: Program-Aided Language Models.* (canonical code-execution citations)
- Wu & Feng, 2024. *ProTrix*; Kong et al., 2024. *OpenTab*; Li et al., 2024. *GraphOTTER.*
- Wei et al., 2022. *Chain-of-Thought Prompting.*
