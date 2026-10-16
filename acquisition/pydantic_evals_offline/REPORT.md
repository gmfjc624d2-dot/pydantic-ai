# Pydantic Evals for offline evaluation of local AI workers — findings and verdict

**Verdict: ADAPT SELECTIVELY.** Use Pydantic Evals only as an optional, isolated *scoring and
comparison layer over recorded worker observations*, in an environment without Logfire. Keep
pytest + Hypothesis as the correctness gate, and keep the worker's own durable ledger as the
evidence of record. If graded evaluation of non-deterministic (e.g. local-model) outputs does not
become a demonstrated need, downgrade to **LEARN ONLY**: nothing built here depends on Pydantic Evals.

All results: Linux x86_64 cloud container, CPython 3.13.16, 4 vCPU. **No result here is a macOS
qualification**; see [MACOS_HANDOFF.md](MACOS_HANDOFF.md). Evidence files are under
[`results/linux-x86_64-cloud/`](results/linux-x86_64-cloud/); commands are in [README.md](README.md).

## 1. Identity, license, dependencies

| Item | Finding |
|---|---|
| Repository | Fork `gmfjc624d2-dot/pydantic-ai` of `pydantic/pydantic-ai`; work branch `claude/sweet-carson-tjohp1` |
| Commit studied | `a3251fbe489f4f47e5f281030868c67475279fbd` (2026-10-16, `git describe`: `v2.57.0-17-ga3251fb`). Verified to be in upstream `main` history; upstream `main` was 5 commits ahead, none touching `pydantic_evals/`. |
| Built version | `pydantic-evals 2.57.1.dev17+a3251fb` (wheel SHA-256s in `results/.../dependencies/wheel-sha256.txt`). Latest release: `2.57.0` (PyPI, 2026-10-16). |
| License | MIT, "Copyright (c) Pydantic Services Inc. 2024 to present" (`pydantic_evals/LICENSE`) |
| Python | `requires-python >=3.11`; classifiers 3.11–3.15 |
| Direct deps | `rich`, `logfire-api`, `pydantic>=2.12`, `pydantic-ai-slim==<same version>`, `anyio`, `pyyaml`; extra `logfire` |
| Runtime closure | **22 distributions** without Logfire: `pydantic-ai-slim`, `pydantic-graph`, `pydantic`, `pydantic-core`, `annotated-types`, `typing-extensions`, `typing-inspection`, `anyio`, `idna`, `logfire-api`, `opentelemetry-api`, `genai-prices`, `griffelib`, `httpx2`, `httpcore2`, `h11`, `truststore`, `pyyaml`, `rich`, `markdown-it-py`, `mdurl`, `pygments`. The `logfire` extra adds 17 more (`logfire`, `opentelemetry-sdk`, OTLP/HTTP exporter + proto, `protobuf`, `requests`, `urllib3`, `certifi`, `charset-normalizer`, `wrapt`, ...). |
| Import cost | `import pydantic_evals`: ~0.56–0.71 s, 625 modules, **imports `pydantic_ai.agent`** (the agent framework), `httpx2`, `ssl`, `genai_prices`, `griffe`. With Logfire: 1015 modules, peak RSS 79 MiB (63 MiB without). |
| Retries | `retry_task` / `retry_evaluators` need `tenacity`, which no `pydantic-evals` extra declares (and, before the fix on this branch, also the legacy `httpx`; §7). |

**Package-level independence: no.** `pydantic_evals` cannot be imported without `pydantic-ai-slim`
(`ModuleNotFoundError: No module named 'pydantic_ai'`), imports its *private* modules
(`pydantic_ai._spec`, `pydantic_ai._utils`), and pins it to the exact same version. Adopting
Pydantic Evals therefore installs and imports the Pydantic AI agent framework in the evaluation
process, even though offline evaluation of plain functions uses none of it. It is independent of
Logfire and of the OpenTelemetry SDK (both optional; `logfire-api` is a no-op shim without `logfire`).

**Institutional independence: no.** One vendor (Pydantic Services Inc.), one monorepo and lockstep
release train with Pydantic AI, and first-class integration with the commercial Logfire service
(span names and `logfire.experiment.*` attributes target Logfire's experiments view). Mitigations:
MIT license, and the parts we would use (`Evaluator.evaluate(ctx)`, YAML/JSON datasets, JSON
reports) are small, plain and replaceable; §6 shows the reports convert to a neutral format.

## 2. Security advisories (checked 2026-10-16)

- PyPI advisory database via `pip-audit -s pypi`: **no known vulnerabilities** in the 43 third-party
  packages of environment B (`results/.../dependencies/pip-audit--pypi-advisory-db--B.txt`).
- PyPI `vulnerabilities` field: none for `pydantic-evals`, `pydantic-ai-slim`, `pydantic-graph`,
  `pydantic-ai` 2.57.0, `logfire`/`logfire-api` 5.2.0, `genai-prices` 0.1.13.
- OSV (`api.osv.dev`) was **not checked**: the container's proxy refused the connection (403).
- GitHub Security Advisories for `pydantic/pydantic-ai`: 16 published (Feb–Oct 2026). **None names
  `pydantic-evals`.** They concern `pydantic-ai-slim` surfaces (web chat UI, `web_fetch`/SSRF, UI
  adapters, OpenTelemetry content redaction, model concurrency) that are *installed* as a transitive
  dependency but not exercised by offline evaluation of plain functions. Historical: the `Python`
  evaluator was removed from `pydantic-evals` for security reasons (pydantic/pydantic-ai#2808).

Relevant open upstream issues: pydantic/pydantic-ai#2911 (optionally raise when cases raise),
pydantic/pydantic-ai#4758 (keep traces on `ReportCase`), pydantic/pydantic-ai#6842 (finalized execution
counts), pydantic/pydantic-ai#7710 (portable test-case interchange; no maintainer decision),
pydantic/pydantic-ai#2209 (report display without Logfire), pydantic/pydantic-ai#7496 (diff
rendering bug).

## 3. Privacy and network audit

Method (`audit/run_audit.sh`): every run inside `unshare -n` (a fresh network namespace; loopback
only, and down unless a local sink was needed), under `strace -f` (sockets, connects, exec, clone,
file mutations), with `env -i`, a temporary HOME/TMPDIR/cwd and `PYTHONDONTWRITEBYTECODE=1`. An
in-process probe adds a `sys.addaudithook` log, a record of every `os.environ` key read, and
**canary strings** planted in case inputs, metadata, expected output, task output and an exception
message. The evaluation runs 5 cases (4 worker scenarios + 1 task that raises). No run could reach
any real network; the only listener ever reachable was the local OTLP sink (`audit/otlp_sink.py`).

| Run | Setup | Network (inet `connect`) | Processes spawned | Files written outside harness/worker | Env keys read (OTEL / LOGFIRE / other) | Test content exported |
|---|---|---|---|---|---|---|
| **A** | `pydantic-evals`, no Logfire | **none** (no inet socket created) | none | none | 1 / 0 / 11 | no |
| **B** | Logfire installed, not configured | none | none | none | 9 / 32 / 13 | no |
| **C** | `logfire.configure(send_to_logfire=False, console=False)` | none | **`git rev-parse HEAD`** | none | 29 / 32 / 14 | no |
| D-A | A + inherited `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_TRACES_EXPORTER=otlp`, ... | none | none | none | 1 / 0 / 11 | no (0 requests at sink) |
| D-B | B + same `OTEL_*` | none | none | none | 9 / 32 / 13 | no (0 requests) |
| **D-C** | C + same `OTEL_*` | **127.0.0.1:4318** | `git rev-parse HEAD` | none | 69 / 32 / 14 | **yes: 1 POST `/v1/traces`, 20 kB, every canary (inputs ×5, metadata ×5, expected ×5, outputs ×4, exception text ×6)** |
| D-B-token | B + fake `LOGFIRE_TOKEN`, `LOGFIRE_SEND_TO_LOGFIRE=true` | none | none | none | 9 / 32 / 12 | no |
| D-C-token | C + same token variables | none (explicit `send_to_logfire=False` wins) | `git rev-parse HEAD` | none | 29 / 32 / 13 | no |
| **E** | C + in-memory span exporter | none | `git rev-parse HEAD` | none | 29 / 32 / 14 | in-process only: of 15 spans, the 5 `case:` spans carry inputs, metadata, expected output and output as attributes; exception events carry the error text |

"Files written outside harness/worker: none" excludes one probe file that Python's `tempfile`
creates and deletes in TMPDIR on behalf of the worker harness's `mkdtemp` (attributed to
`worker/scenarios.py` by the audit hook); it appears in every run, including A.

Full table and per-run data: `results/.../audit/summary.md`, `summary.json`, per-run `probe.json`,
`strace-network-and-exec.txt`, `sink-decoded.json`.

Findings:

1. **Without Logfire (A), the evaluation is local-only**: zero inet sockets, no subprocesses, no
   files outside the harness, no files left in HOME/TMPDIR/cwd, nothing on stdout with
   `progress=False`. The complete experiment and the complete pytest baseline also ran to completion
   in a namespace with **no network at all** (`offline-*` runs, exit 0, zero sockets).
2. **`send_to_logfire=False` is not "no export".** With Logfire configured that way, an *inherited*
   `OTEL_EXPORTER_OTLP_ENDPOINT` makes Logfire export every span to that endpoint. Pydantic Evals puts
   case `inputs`, `metadata`, `expected_output`, `output`, scores/assertions and exception text into
   span attributes, so all test content leaves the process. The exported resource also identifies the
   machine: `host.name`, `host.id` (machine ID), `os.version`, `process.pid`, runtime description
   (`results/.../audit/D-C-otel/sink-decoded.json`).
3. Merely *installing* Logfire (B) did not export anything, even with `OTEL_*` or `LOGFIRE_TOKEN`
   inherited; it does read 41 configuration variables.
4. `logfire.configure()` spawns `git rev-parse HEAD` (service version detection) and reads the
   hostname. In a git checkout that commit hash becomes a resource attribute.
5. Logfire's default scrubber redacted a canary stored under the key `secret` but passed the same
   kind of value under `customer_note`: **pattern-based redaction, not a privacy guarantee.**
6. Harness note: the saved report itself (`report.json`) contains all test content by design;
   where it is stored is the harness's responsibility.

Limitations: environment reads by C code through `getenv()` are invisible to both the Python probe
and `strace`. The namespace blocks egress, so a *blocked* attempt would appear in `strace` as a
failed `connect`/DNS lookup; none occurred outside D-C's local sink. The audit hook attributes events
to the first non-stdlib frame, which is a heuristic.

**Rule for adoption:** run evaluations in an environment without the `logfire` package (A), or, if
Logfire is present, do not call `logfire.configure()` in the evaluation process and strip `OTEL_*`
and `LOGFIRE_*` from its environment.

## 4. The experiment: same scenarios, two harnesses

The synthetic worker (`worker/synthetic_worker.py`) answers JSON requests with JSON text and records
side effects in a SQLite ledger. Faults are injected per request (raise before effect, commit then
lose the response, truncate output) and per process (`SIGKILL` before the effect, after the effect,
after the job is marked done). Six implementations, one defect each:

| Variant | Defect |
|---|---|
| `v1-correct` | none |
| `v2-dup-on-retry` | a retry with the same idempotency key applies the effect again |
| `v3-wrong-sum` | `sum` treats negatives as positives |
| `v4-nonatomic-resume` | effect and job completion committed separately, no dedupe: a crash between them duplicates the effect on resume |
| `v5-default-on-miss` | missing key returns `0` instead of an error |
| `v6-int32-sum` | `sum` wraps at 32 bits (only visible with large values) |

Both harnesses consume the same 13 scenarios and the same checks (`worker/scenarios.py`).

**Discrimination** (`results/.../baseline/discrimination.json`, `results/.../evals/discrimination.json`):

| Variant | pytest scenario tests | Hypothesis | Pydantic Evals (13 fixed cases) | Pydantic Evals (100 seeded generated `sum` cases) |
|---|---|---|---|---|
| `v1-correct` | accepted (81/81) | accepted | accepted (100% assertions) | 0/100 failing |
| `v2-dup-on-retry` | rejected: 3 scenarios | rejected; shrunk to two steps (a job for `k0`, then a retry) | rejected: 3 cases (91.2%) | — |
| `v3-wrong-sum` | rejected: `sum-mixed-sign` | rejected; shrunk to `values=[-1]` | rejected: `sum-mixed-sign` | 66/100 failing |
| `v4-nonatomic-resume` | rejected: `crash-after-effect-resume` | rejected; shrunk to one step: `job_with_crash_and_restart(crash_at='after_effect', key='k0')` | rejected: `crash-after-effect-resume` | — |
| `v5-default-on-miss` | rejected: `lookup-miss` | rejected; shrunk to `key='0'` | rejected: `lookup-miss` | — |
| `v6-int32-sum` | **accepted** | **rejected; shrunk to `values=[2_147_483_648]`** | **accepted (100%)** | 85/100 failing; first failing input not minimized |

Both harnesses reject every defect their cases are designed for, and accept the correct
implementation. Only Hypothesis rejected `v6` with a minimal counterexample; Pydantic Evals caught it
only after hand-writing seeded random cases, without shrinking.

**What each approach could actually demonstrate:**

| Property | pytest + Hypothesis | Pydantic Evals |
|---|---|---|
| Correct vs incorrect outcomes | Yes | Yes, with per-evaluator reasons |
| Malformed / truncated output | Yes (an exception in a check fails the test: fail-closed) | Yes if the evaluator handles it. **A raising evaluator is dropped from the pass rate**: 0.5 with a robust evaluator vs **1.0** with a naive one on the same data. It is shown in the table, not counted. |
| Worker exceptions | `pytest.raises` / test failure | `ReportCaseFailure`: message + stacktrace only; no `error_type` field (evaluator failures have one), no partial output, evaluators do not run |
| Evaluator exceptions | Test error | Separate `EvaluatorFailure` with `error_type` — a real advantage for telling evaluator bugs from worker bugs |
| Side effect before interruption | Only via the worker ledger | Only via the worker ledger; the report cannot see effects. Both "raise before effect" and "commit then lose response" are an identical `ReportCaseFailure` when the task lets the exception escape |
| Retries and duplicate execution | Stateful model explores interleavings of faults, retries and restarts | `retry_task` **hides attempts**: 2 attempts produced 1 clean case, a user metric incremented per attempt reads `1`, no attempt field. With `v2`, the retry doubled the ledger effect while the report shows success |
| Result produced but not received | Harness classifies; ledger resolves | Same harness; the report keeps whatever the task returns |
| Restart and reconstruction (worker) | Real `SIGKILL` (examples) + simulated crash (state machine) | Real `SIGKILL` inside the task works, as plain Python |
| Restart (the evaluation itself) | No resume; Hypothesis example database replays failures across runs | **No resume or incremental persistence**: `SIGKILL` mid-run left no files and no partial report. A `CaseLifecycle.teardown` journal (user code) persisted 3 of 8 cases. **One raising `teardown` aborts `evaluate()` and discards every case's result.** |
| Version changes | Compare JUnit XML yourself | **Report diff against a baseline** (`report.render(baseline=...)`): per-case score/label/assertion deltas, e.g. `ledger_effects: 1 → 2 (+1)`. Evaluator versions are recorded per result. Worker version and environment only if the harness puts them in `metadata`. |
| Preservation of evidence | JUnit XML; the test owns its artifacts | JSON round-trip of the report is byte-identical for JSON-friendly outputs. **One non-UTF-8 `bytes` output makes the whole report unserializable**, and `fallback=` does not help; custom objects need `fallback=repr`. |
| Repeatability | `derandomize=True` makes Hypothesis deterministic | Identical results across runs after dropping durations and trace/span IDs; `repeat=3` groups identical |
| Re-evaluating old evidence | — | **Works**: a task that replays recorded outputs reproduced every original assertion and applied a new evaluator to old evidence, catching `v2` with zero worker executions (`evals/reevaluated-from-recording--*.json`) |

Defaults that are hazardous for side-effecting workers: `progress=True` writes to stdout;
`max_concurrency=None` ran all 20 sync cases at once in worker threads; `Dataset.to_file` also writes
a `*_schema.json` next to the dataset.

Code size (non-blank, non-comment lines): worker 210 and shared scenarios/checks 289, used by both;
pytest + Hypothesis harness 123 (including a 50-line state machine); Pydantic Evals experiment 156, of
which about 70 are evaluators, dataset and task, and the rest report writing, diffs and generated
cases. Neither approach needed a new framework. Runtime: all six variants in ~4.5 s with Pydantic
Evals; up to ~25 s per variant for pytest, dominated by 200 Hypothesis state-machine examples
(variants the state machine rejects early finish in ~2 s).

## 5. The worker's records vs the evaluation report

The report knows what the *task returned* and what *evaluators said*. It does not know whether a
side effect happened, how many attempts ran, when the run started, which worker version or
environment produced it (unless the harness supplies them), or anything about a case whose task
raised beyond the message and stacktrace. In every scenario where a response was lost or the process
was killed, only the worker's SQLite ledger could establish whether the effect happened, and the
harness records such steps as `effect_known_from_response: false`, never as "no effect".

## 6. Reports and portability: neutral evidence records

`neutral/to_neutral.py` converts a saved report plus the preserved SQLite ledgers into
`evidence-record/v0` JSON Lines (schema: `neutral/evidence-record.v0.schema.json`, validated on every
record). It defines no new scoring vocabulary: evaluator outcomes use the OpenTelemetry GenAI
evaluation names that Pydantic Evals already emits for online evaluation (`gen_ai.evaluation.name`,
`.score.value`, `.score.label`, `.explanation`, `error.type`, evaluator source and version), with the
same bool → `1.0`/`pass` mapping. Inputs and outputs are referenced by SHA-256 (inlining is opt-in).

| Field | Source |
|---|---|
| case identity, input, output, evaluations, evaluator errors, task error message/stacktrace, durations | Pydantic Evals report |
| trace/span IDs | Report, only when a tracer provider was configured (null in environment A) |
| worker version, environment, dataset digest | Harness, via `experiment_metadata` (not observed by Pydantic Evals) |
| side effects, effects per idempotency key | Worker ledger, re-read and hashed by the converter; cross-checked against the snapshot in the report (`ledger_matches_report_snapshot` for all 27 preserved ledgers) |
| uncertain steps (no response, malformed, killed) | Harness caller view joined with the ledger |
| retry identity | Idempotency keys from the case inputs |
| attempt index/count, run start time | **Not observed** → `null`, with provenance saying so |
| repetition index, error type of a task failure | Derived from strings (`"[i/n]"` suffix, `"Type: message"` prefix), flagged as derived |

Evidence handling: opening a WAL-mode SQLite ledger with `mode=ro` still created `-wal`/`-shm` files
next to the evidence; the converter opens ledgers with `mode=ro&immutable=1`, which reads without
touching the directory. The 27 preserved ledgers still match `evals/ledgers/SHA256SUMS`.

When no ledger was preserved (the read-only scenarios here, and the audit report), `effects` is
`{"status": "not_observed"}`, never "none". Outputs: `results/.../neutral/*.jsonl`. pytest's own
neutral output (JUnit XML) is kept alongside (`results/.../baseline/junit--*.xml`).

## 7. Upstream defect found and fixed (commit `0dbcd43` on this branch; no pull request)

**Defect.** `Dataset.evaluate(retry_task=..., retry_evaluators=...)` imported `retry` from
`pydantic_ai.retries`, which also imports the legacy `httpx` package for deprecated transports. With
`tenacity` installed, as the retry docs imply, but not `httpx`, *no task runs*: every case becomes a
`ReportCaseFailure` saying "Please install `httpx`". `evaluate()` does not raise. Reproduced on the
**released `pydantic-evals==2.57.0` from PyPI** and on the studied commit
(`results/.../upstream-fix/retry_without_httpx.txt`). No upstream issue or PR found.

**Fix.** `pydantic_evals/_utils.py:with_retry` imports `retry` from `tenacity` directly (install hint
names `tenacity`); `dataset.py` and `evaluators/_run_evaluator.py` use it.

**Tests** (`tests/evals/test_dataset.py`): `test_evaluate_retries_need_only_tenacity` hides `httpx`
and reloads `pydantic_ai.retries`; it failed on the original code with exactly the reported
`ImportError` and passes after the fix. `test_evaluate_retry_without_tenacity` covers the new error
path. Verified: all 625 `tests/evals` tests pass; Pyright strict reports 0 errors on the changed
files; ruff and the repository's pre-commit hooks pass; a wheel built from the fix ran the retry
end to end in a real environment with `tenacity` and without `httpx` (2 attempts, case passes).

**Remaining limitations (not changed):** with `tenacity` missing, `retry_task` still turns into
per-case failures instead of failing fast, and `retry_evaluators` surfaces as an opaque
`ExceptionGroup` *task* failure after the task already ran; `pydantic-evals` declares no extra for
`tenacity`; the retry docs page does not state the install requirement.

## 8. Adjudication

| Dimension | pytest + Hypothesis | Pydantic Evals | Edge |
|---|---|---|---|
| Necessary code | 123 lines incl. stateful model | ~70 lines of evaluators/dataset + reporting glue | even |
| Evaluator interface | assertions; fail-closed | typed `Evaluator.evaluate(ctx)`, bool/number/label + reason, versioned | Evals |
| Comparing implementations | manual JUnit comparison | baseline diff rendering, per-case deltas, averages | **Evals** |
| Finding defects | found all 5, minimal counterexamples | found 4 of 5 with fixed cases | **pytest + Hypothesis** |
| Retries, crashes, partial failure | stateful model across faults and restarts | hides retry attempts; teardown error discards everything; no resume | **pytest + Hypothesis** |
| Serialization and recovery | JUnit XML; example database | JSON round-trip (all-or-nothing); no incremental persistence | pytest (slightly) |
| Error reporting | failure vs error | task vs evaluator failures separated; crashing evaluators not counted in pass rate | mixed |
| Traceability | test ids | evaluator source + version per result; trace IDs only with OTel | Evals (slightly) |
| Dependency complexity | pytest + Hypothesis | 22 distributions incl. the Pydantic AI agent framework, private-API coupling, exact pin | **pytest + Hypothesis** |
| Privacy and telemetry | none | none without Logfire; full content export with Logfire + inherited `OTEL_*` | pytest (Evals safe only in configuration A) |
| Plain Python functions | yes | yes (sync tasks run in threads, all at once by default) | even |
| Maintenance and portability | stable, independent | lockstep with Pydantic AI; MIT; reports convert to neutral records | pytest |

**Why ADAPT SELECTIVELY and not USE:** for the properties that matter most to a durable worker —
exactly-once effects, crash/resume, lost responses, retries — pytest + Hypothesis demonstrated
strictly more, and Pydantic Evals' own retry and teardown behavior is unsafe around side effects.
**Why not REJECT:** the evaluator/report model, separated evaluator failures, evaluator versioning and
especially baseline diffs are useful for measuring change between implementations, and the
re-evaluation experiment shows they can be used *without* executing side effects. **Boundaries of
the adaptation:** evaluate recorded observations (not live side effects); environment A; explicit
`progress=False` and `max_concurrency`; no `retry_task`; a non-raising `teardown`; JSON-friendly
outputs; evidence of record = worker ledger + neutral records, not the report.

## 9. Continuation

Further Pydantic Evals engineering has **low marginal value** now. The one narrow defect is fixed;
the remaining gaps (attempt records, incremental persistence, fail-fast on case errors) are
design-level questions already open upstream (pydantic/pydantic-ai#2911, #4758, #6842), not
narrow fixes for this branch.

The demonstrated needs are in **durable, attempt-aware evidence**: record every attempt, survive
termination mid-evaluation, resume without redoing completed work, and keep content local. Two
directions follow from that, in order:

1. **Keep the evidence in the worker**, which needs no new technology: an attempt ledger (attempt
   id, idempotency key, request fingerprint, outcome, timestamps) next to the effect ledger, exported
   as `evidence-record` lines. The harness here already does half of this.
2. **Next technology to investigate: Inspect AI** (UK AI Security Institute; MIT). Its documentation
   targets exactly the gaps found here: incrementally written eval logs, `inspect eval-retry` that
   resumes an interrupted or errored run while reusing completed samples, per-sample
   `retry_on_error`, and a documented crash mode (after `kill -9` the log stays `started` and
   unflushed samples are lost). Not yet verified: whether plain Python workers fit its
   task/solver/scorer model without a model provider (it ships a mock model), its dependency
   closure, and its network and telemetry surface. All of these can be tested by reusing this
   directory's worker, scenarios, kill tests, audit and neutral converter unchanged. Sources:
   [Handling Errors](https://inspect.aisi.org.uk/handling-errors.html),
   [Errors and Limits](https://inspect.aisi.org.uk/errors-and-limits.html),
   [`inspect eval-retry`](https://inspect.aisi.org.uk/reference/inspect_eval-retry.html),
   [Eval Sets](https://inspect.aisi.org.uk/eval-sets.html).
