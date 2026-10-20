# Public NLI conditions experiment (`public-nli-conditions-20261020-01`)

A bounded, public, offline experiment: can a small multilingual NLI classifier
(`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`) give a useful **advisory** signal for document review on
conditions, exceptions, negation, uncertain modality, attribution and multi-sentence reference, in
Spanish and English, compared with a documented lexical baseline? A model score is never an
authorization, a verdict or ground truth.

All fixtures are original synthetic toy texts (museum, books, weather, geometry puzzle); no private,
institutional or personal data. Nothing here ran on macOS. Earlier work on this branch
(`acquisition/pydantic_evals_offline/`) is untouched.

## Status

| | What |
|---|---|
| **Implemented and executed** (Linux x86_64 cloud) | frozen fixtures (48 items, 128 trials) and ambiguity review; deterministic lexical baseline fitted on dev only and run on both sets; replay scorer with errata subsets and group-level reporting; torch-free harness self-test; one logged model-fetch attempt; dependency resolution |
| **Implemented, not executed** | `model/run_model.py` (offline CPU float32 inference with raw logits, token counts, durations, peak memory, overlength refusal) and `model/verify_local_model.py` against real assets |
| **Blocked** | model metadata, card and weights: `huggingface.co` denied by the session's egress policy (no mirror or relay used); ACL 2026 paper `2026.acl-long.1472` unidentifiable (`aclanthology.org`, `doi.org`, arXiv, Semantic Scholar denied); CPU-only PyTorch index denied |
| **Proposed** | the model run on requester-held assets (`RESULTS.md`, "Smallest next test"); macOS Apple Silicon qualification (`MACOS_PLAN.md`) |

## Documents

- [`METHOD.md`](METHOD.md) — question, what is not equated, fixtures, protocol, systems, scoring.
- [`fixtures/REVIEW.md`](fixtures/REVIEW.md), [`fixtures/errata.md`](fixtures/errata.md) — labeling
  convention, pre-freeze review, post-freeze flags (labels never changed).
- [`SOURCES_AND_LICENSES.md`](SOURCES_AND_LICENSES.md) — model identity (requester-provided vs
  verified), SummaC limitations from its source, the blocked paper, dependencies, license notes.
- [`RESULTS.md`](RESULTS.md) — Linux baseline results, failure analysis, blocked model, next test.
- [`MACOS_PLAN.md`](MACOS_PLAN.md) — Apple Silicon qualification plan.

## Layout

| Path | Contents |
|---|---|
| `fixtures/` | frozen `dev.jsonl`, `heldout.jsonl`, `excluded.jsonl`, `freeze_manifest.json`, builder, review, errata |
| `nli_common.py` | hash-verified fixture loading and trial construction |
| `baseline_lexical.py` | lexical baseline (`fit` on dev, `predict`) |
| `score.py` | replay scorer (stdlib only; never runs a model) |
| `model/` | `fetch_model.py`, `verify_local_model.py`, `run_model.py`, `selftest_harness.py`, `expected/` metadata, dependency locks |
| `results/linux-x86_64-cloud/` | baseline config and immutable predictions, score report, model attempt log, network evidence |

## Reproduce

From the repository root (`git clone https://github.com/gmfjc624d2-dot/pydantic-ai && git checkout claude/sweet-carson-tjohp1`):

```bash
cd acquisition/public_nli_conditions_20261020
WORK=$(mktemp -d)

# Fixtures: rebuilding must reproduce the frozen bytes exactly.
python3 fixtures/build_fixtures.py > /dev/null && git diff --exit-code -- fixtures/

# Lexical baseline: refit on dev (tau must be 0.6) and re-predict; outputs are byte-identical.
python3 baseline_lexical.py fit "$WORK/cfg.json"
python3 baseline_lexical.py predict "$WORK/cfg.json" "$WORK/run"
cmp "$WORK/run/predictions--heldout.jsonl" results/linux-x86_64-cloud/lexical-baseline/predictions--heldout.jsonl

# Re-score retained predictions (no inference); report is byte-identical to the committed one.
python3 score.py "$WORK/scores" results/linux-x86_64-cloud/lexical-baseline
cmp "$WORK/scores/score_report.json" results/linux-x86_64-cloud/scores/score_report.json

# Harness safety checks without torch or weights.
python3 model/selftest_harness.py
```

Model run, on a machine with the model files (proposed; not executed here):

```bash
uv venv "$WORK/venv-model" --python 3.13
VIRTUAL_ENV="$WORK/venv-model" uv pip sync model/requirements-model.x86_64-unknown-linux-gnu.lock
python3 model/verify_local_model.py --model-dir "$MODEL_DIR" \
    --expected model/expected/requester_metadata_8adb042d.json \
    --manifest "$WORK/model_manifest.json" --attempt-log results/<platform>/model-attempts/attempts.jsonl
# (or, where huggingface.co is allowed: "$WORK/venv-model/bin/python" model/fetch_model.py
#   --revision 8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c --dest "$MODEL_DIR" --manifest "$WORK/model_manifest.json"
#   --attempt-log results/<platform>/model-attempts/attempts.jsonl)
sudo unshare -n "$WORK/venv-model/bin/python" model/run_model.py --model-dir "$MODEL_DIR" \
    --manifest "$WORK/model_manifest.json" --run-dir results/<platform>/mdeberta-8adb042d --threads 4
python3 score.py results/<platform>/scores results/linux-x86_64-cloud/lexical-baseline results/<platform>/mdeberta-8adb042d
```

Notes: prediction files are immutable (writers refuse to overwrite; the scorer checks their SHA-256).
The repository's codespell hook flags four Spanish words in the fixtures (`nieve`, `imposible`,
`posible`, `termine`); the frozen text is intentionally unchanged.
