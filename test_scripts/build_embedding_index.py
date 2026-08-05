"""Embed every context element of the reports behind a stratified claim sample.

Runs the local nomic-embed-text model through Ollama. No cloud, no quota, no key.
This is the one-time cost described in section 11 item 11 of the architecture
plan: pay it once, cache the vectors, and every retrieval experiment afterwards
is arithmetic over a file.

    measured 4 Aug 2026    0.432 s per element, 768 dimensions
    102-claim slice        89 reports, 20,718 elements, about 2.5 h
    full testmini          255 reports, 60,871 elements, about 7.3 h

Storage is raw float32, one file per report, rows in report["context"] order.
Row i is element id i, which is safe because id equals list position for all
137,045 elements (checked 2 Aug 2026). At 768 dims that is 3,072 bytes per
element, about 178 MB for the full index. Written with array.array rather than
numpy because numpy is not installed on this machine and this script does no
arithmetic; whoever reads these back can use either.

Resume is by report. A report whose file already exists at the correct byte
length is skipped, so an interrupted run costs at most one report. The file is
written to a temporary name and renamed only once complete, because a crash
mid-write would otherwise leave a short file that looks finished.

Run it as:

    caffeinate -ims python3 test_scripts/build_embedding_index.py 17 \
        2>&1 | tee logs/embedding_index.txt

caffeinate holds the no-sleep assertion only while this process runs and
releases it on exit, so the machine returns to normal sleep afterwards. It
cannot override a closed lid: leave the lid open and stay on AC power.
"""

import array
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.loader import load_claims
from src.sampler import stratified_sample
from src.run_loop import read_report

MODEL = "nomic-embed-text"
DIM = 768                  # measured 4 Aug 2026, asserted below rather than trusted
OUT_DIR = REPO_ROOT / "embeddings"
ENDPOINT = "http://localhost:11434/api/embed"
BATCH = 32                 # elements per HTTP call; one call per element would be
                           # dominated by request overhead
TIMEOUT = 600


def embed_batch(texts):
    """One Ollama call for a list of texts. Retries once, then gives up."""
    payload = json.dumps({"model": MODEL, "input": texts}).encode()
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})

    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read())["embeddings"]
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 2:
                raise
            print(f"      retrying after {type(exc).__name__}: {exc}", flush=True)
            time.sleep(5)


def index_path(report_name):
    """One file per report, named by basename so the path separator never appears."""
    return OUT_DIR / (Path(report_name).stem + ".f32")


def already_done(path, n_elements):
    """Resume check. Tests byte length, not mere existence.

    A crash mid-write leaves a short file. Renaming only on completion should
    prevent that, but the length check costs nothing and makes the guarantee
    hold even if the script is killed between write and rename.
    """
    return path.exists() and path.stat().st_size == n_elements * DIM * 4


def embed_report(report_name):
    """Embed every element of one report and write it. Returns element count."""
    report = read_report(report_name)
    texts = [element["context"] for element in report["context"]]
    path = index_path(report_name)

    if already_done(path, len(texts)):
        return len(texts), True

    vectors = array.array("f")
    for start in range(0, len(texts), BATCH):
        batch = texts[start:start + BATCH]
        # Ollama rejects an empty string; a blank element would otherwise kill
        # the whole run 90 minutes in.
        batch = [t if t.strip() else " " for t in batch]
        for vector in embed_batch(batch):
            if len(vector) != DIM:
                raise ValueError(
                    f"{report_name}: expected {DIM} dims, got {len(vector)}. "
                    f"The model changed; delete embeddings/ and rebuild.")
            vectors.extend(vector)

    temp = path.with_suffix(".partial")
    with open(temp, "wb") as f:
        vectors.tofile(f)
    os.replace(temp, path)          # atomic: the final name only ever appears complete
    return len(texts), False


def main():
    per_cell = int(sys.argv[1]) if len(sys.argv) > 1 else 17

    claims = load_claims()
    sample = stratified_sample(claims, per_cell)
    reports = sorted({claim.report for claim in sample})

    OUT_DIR.mkdir(exist_ok=True)
    total = sum(len(read_report(r)["context"]) for r in reports)

    print(f"{len(sample)} claims, {len(reports)} reports, {total} elements")
    print(f"estimate at 0.432 s/element: {total * 0.432 / 3600:.1f} h")
    print(f"writing to {OUT_DIR}", flush=True)

    started = time.time()
    done_elements = 0
    failures = []

    for i, report_name in enumerate(reports, start=1):
        try:
            n, skipped = embed_report(report_name)
        except Exception as exc:
            # One malformed report must not end a 2.5 h run.
            failures.append((report_name, repr(exc)))
            print(f"  [{i}/{len(reports)}] FAILED {report_name}: {exc}", flush=True)
            continue

        done_elements += n
        elapsed = time.time() - started
        rate = elapsed / done_elements if done_elements else 0
        remaining = (total - done_elements) * rate
        print(f"  [{i}/{len(reports)}] {n:5d} elements  "
              f"{'skipped' if skipped else 'embedded'}  "
              f"elapsed {elapsed / 60:6.1f} min  eta {remaining / 60:6.1f} min",
              flush=True)

    manifest = {
        "model": MODEL,
        "dim": DIM,
        "per_cell": per_cell,
        "n_claims": len(sample),
        "reports": len(reports),
        "elements": total,
        "seconds": round(time.time() - started, 1),
        "failures": failures,
    }
    with open(OUT_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\ndone in {(time.time() - started) / 60:.1f} min, "
          f"{len(failures)} failed reports")
    if failures:
        print("re-running the script skips completed reports and retries these")


if __name__ == "__main__":
    main()
