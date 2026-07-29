# findver-agent

An edge-cloud agent that verifies financial claims against long SEC filings. It is
evaluated on the FINDVER benchmark. A local Qwen2.5-Coder-3B model runs through Ollama
and does the mechanical work. Cloud APIs handle the judgment-heavy steps. The retrieval
setup is RAG-only.

Undergraduate research project, two months, one developer.

## Setup

The benchmark data is not committed to this repository. It is 1.3 GB and it is already
public. Clone it into the project root:

```bash
git clone https://github.com/yilunzhao/FinDVer.git
cd FinDVer && git checkout e8bb237 && cd ..
```

That commit is the one this project was developed against. After the clone the data sits
at `FinDVer/data/testmini.json` and the filings sit at `FinDVer/financial_reports/`.

Ollama is pinned at v0.12.3. Auto-update must stay off. Version 0.12.4 dropped macOS 13
support.

## Layout

```
docs/                  architecture plan, research plan, benchmark paper
src/                   pipeline code
FinDVer/               benchmark data, not tracked, see Setup above
results/               per-example JSON output, not tracked
configs/               one config file per experiment
```
