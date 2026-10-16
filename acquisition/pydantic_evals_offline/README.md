# Pydantic Evals: offline evaluation and evidence reliability (acquisition study)

Public, synthetic investigation of whether `pydantic-evals` improves the evaluation of local Python
workers compared with pytest and Hypothesis alone. Findings, verdict and limitations are in
[REPORT.md](REPORT.md); the macOS reproduction plan is in [MACOS_HANDOFF.md](MACOS_HANDOFF.md).

Everything here ran on **Linux x86_64 in a cloud container** (CPython 3.13.16). Nothing here is a
macOS result.

This directory is self-contained and is not part of the repository's own test suite (it has its own
`pytest.ini`). The only upstream code change is in the separate commit
`fix: let pydantic-evals retries work without the legacy httpx package` (see REPORT.md).

## Layout

| Path | What |
|---|---|
| `worker/synthetic_worker.py` | Deterministic worker with a SQLite ledger: lookup, sum, idempotent `record`, job queue with crash points; six implementation variants (one correct, five with one defect each). |
| `worker/scenarios.py` | The 13 shared scenarios, the scenario runner (caller view + ledger snapshot) and the shared checks. Used by both harnesses. |
| `baseline/` | Control baseline: pytest + Hypothesis (parametrized scenarios, properties, a stateful model with crash/restart). `run_discrimination.py` runs it per variant and writes JUnit XML. |
| `evals/evals_experiment.py` | The same scenarios as a Pydantic Evals `Dataset` with deterministic evaluators; per-variant reports, baseline diffs, seeded generated cases. |
| `evals/probe_framework.py` | Probes of Pydantic Evals' own behavior (exceptions, retries, kill mid-run, teardown, serialization, concurrency, repeatability). |
| `evals/reevaluate_recorded.py` | Re-evaluates recorded observations from a saved report without re-running the worker. |
| `evals/repro_retry_without_httpx.py` | Reproduction for the upstream defect fixed on this branch. |
| `neutral/` | `evidence-record/v0` JSON Schema and the converter from a saved report + preserved ledgers. |
| `audit/` | Privacy/network audit: in-process probe (audit hook, env reads, canaries), local OTLP sink, netns + strace orchestration, analyzer. |
| `results/linux-x86_64-cloud/` | Captured outputs of every step below (paths rewritten to `$WORK` / `$REPO`; the repository's whitespace hook stripped trailing spaces inside pytest's JUnit failure text; SQLite ledgers are byte-exact, see `evals/ledgers/SHA256SUMS`). |

## Reproduce

Requires `uv`, and for the audit: Linux, root (or user namespaces), `unshare`, `strace`.

```bash
REPO=$(git rev-parse --show-toplevel)
WORK=$(mktemp -d)                      # venvs and scratch outputs live outside the repo
cd "$REPO"

# 1. Build the three first-party wheels from this exact commit.
for p in pydantic-graph pydantic-ai-slim pydantic-evals; do uv build --wheel --package $p -o "$WORK/wheels"; done
EV=$(ls "$WORK"/wheels/pydantic_evals-*.whl); SL=$(ls "$WORK"/wheels/pydantic_ai_slim-*.whl); GR=$(ls "$WORK"/wheels/pydantic_graph-*.whl)

# 2. Isolated environments (network is needed only for this step).
uv venv "$WORK/venv-A" && VIRTUAL_ENV="$WORK/venv-A" uv pip install "$EV" "$SL" "$GR" pytest hypothesis            # A: no Logfire
uv venv "$WORK/venv-B" && VIRTUAL_ENV="$WORK/venv-B" uv pip install "$EV[logfire]" "$SL" "$GR" pytest hypothesis    # B: Logfire installed

cd acquisition/pydantic_evals_offline

# 3. Control baseline (pytest + Hypothesis), once per implementation variant.
WORKER_IMPL=v1-correct "$WORK/venv-A/bin/python" -m pytest -q
"$WORK/venv-A/bin/python" baseline/run_discrimination.py "$WORK/baseline"

# 4. Pydantic Evals over the same scenarios, framework probes, re-evaluation of recorded evidence.
"$WORK/venv-A/bin/python" evals/evals_experiment.py "$WORK/evals"
"$WORK/venv-A/bin/python" evals/probe_framework.py "$WORK/probes.json"
"$WORK/venv-A/bin/python" evals/reevaluate_recorded.py "$WORK/evals/report--v2-dup-on-retry.json" "$WORK/reeval.json"

# 5. Neutral evidence records (report + preserved SQLite ledgers).
"$WORK/venv-A/bin/python" neutral/to_neutral.py "$WORK/evals/report--v2-dup-on-retry.json" --ledgers "$WORK/evals/ledgers" > "$WORK/records.jsonl"

# 6. Privacy and network audit, scenarios A-E, plus fully offline runs of steps 3 and 4.
sudo audit/run_audit.sh "$WORK/venv-A" "$WORK/venv-B" "$WORK/audit"     # writes $WORK/audit/summary.md
```

Hypothesis runs derandomized with no example database by default (repeatable evidence); set
`HYPOTHESIS_PROFILE=explore` to search randomly.
