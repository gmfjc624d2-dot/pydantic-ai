# macOS Apple Silicon qualification plan (proposed; nothing here has run on macOS)

Linux results do not qualify macOS. Store macOS outputs under `results/macos-arm64/` with the same
layout, never mixed into `results/linux-x86_64-cloud/`.

## 1. Native platform

```bash
uname -m                              # arm64
sysctl -n sysctl.proc_translated      # 0 (1 = Rosetta)
sw_vers; sysctl -n machdep.cpu.brand_string
uv python install 3.13 && uv venv "$WORK/venv-model" --python 3.13
file "$("$WORK/venv-model/bin/python" -c 'import sys; print(sys.executable)')"   # must say arm64
```

macOS 14 or later is required: torch 2.14.1 publishes arm64 wheels only for `macosx_14_0_arm64`.

## 2. Environment and assets

```bash
cd acquisition/public_nli_conditions_20261020
VIRTUAL_ENV="$WORK/venv-model" uv pip sync model/requirements-model.aarch64-apple-darwin-macos14.lock
python3 model/selftest_harness.py                       # stdlib-only harness checks
python3 model/verify_local_model.py --model-dir "$MODEL_DIR" \
    --expected model/expected/requester_metadata_8adb042d.json \
    --manifest results/macos-arm64/model_manifest.json \
    --attempt-log results/macos-arm64/model-attempts/attempts.jsonl
```

`$MODEL_DIR` is the requester's recovered, hash-checked directory. Weights stay outside the repository.

## 3. Local-only execution

There is no `unshare -n` on macOS. Use and record one of: (a) Wi-Fi off and cable unplugged, proven by
a failing `curl -sS --max-time 5 https://pypi.org`; or (b) `sandbox-exec` with a profile denying
`network-outbound (remote ip)`, proven to block `curl` first. The runner also sets `HF_HUB_OFFLINE`,
`TRANSFORMERS_OFFLINE` and `HF_HUB_DISABLE_TELEMETRY` and passes `local_files_only=True`. During the
run, `lsof -a -i -p <pid>` should list no internet sockets.

## 4. Run and compare (CPU, float32)

```bash
"$WORK/venv-model/bin/python" model/run_model.py --model-dir "$MODEL_DIR" \
    --manifest results/macos-arm64/model_manifest.json --run-dir results/macos-arm64/mdeberta-8adb042d --threads 4
python3 score.py results/macos-arm64/scores results/linux-x86_64-cloud/lexical-baseline results/macos-arm64/mdeberta-8adb042d
```

- CPU only. MPS (`device="mps"`), if tried later, is a separate, separately identified trial: different
  kernels and reduced-precision paths can change logits.
- Compare with a Linux run of the same revision (when one exists), per trial: `input_ids_sha256` must be
  identical (tokenization parity); report the maximum absolute logit difference and any label change.
  Do not declare parity from labels alone; do not pick a tolerance after seeing the differences.
- The runner re-runs every trial once and records any logit mismatch (in-process determinism).

## 5. Resources

Record `import_seconds`, `load_seconds`, per-trial `duration_ns` and peak RSS from the run manifest
(the runner converts `ru_maxrss`, which is bytes on macOS and KiB on Linux, to MiB), plus
`/usr/bin/time -l` (maximum resident set size in **bytes** on macOS), power source (battery or AC), and
whether `caffeinate -i` was used. Close other heavy applications; report, do not normalize, variance.

## 6. Not covered

Power-loss durability, long documents (the fixtures are at most 255 characters per trial), languages
other than Spanish and English, and calibration. Model output remains advisory on macOS as on Linux.
