# macOS (Apple Silicon) reproduction plan

**Nothing in this directory has run on macOS.** Every result under `results/linux-x86_64-cloud/`
comes from a Linux x86_64 cloud container. This file says how to obtain the macOS results and what is
expected to differ. Store them under `results/macos-arm64/` with the same layout, and do not merge
them into, or compare them as, the Linux numbers without saying so.

## 1. Native arm64 Python

```bash
uname -m                                  # must print: arm64
sysctl -n sysctl.proc_translated          # must print: 0  (1 = the shell runs under Rosetta)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13                    # uv's standalone builds are native arm64
uv run --python 3.13 python -c 'import platform, sys; print(platform.machine(), sys.version)'   # arm64
```

After creating each venv, confirm the interpreter is not x86_64:
`file "$(python -c 'import sys; print(sys.executable)')"` must mention `arm64`.

## 2. Isolated environments

Follow README.md steps 1–2 unchanged (they only use `uv`), with a throwaway cache and HOME so nothing
from the developer's account leaks in:

```bash
export WORK=$(mktemp -d) UV_CACHE_DIR=$WORK/uv-cache
# build wheels, create venv-A (no Logfire) and venv-B (Logfire) exactly as in README.md
```

Record `uv pip freeze` of both venvs and the wheel SHA-256s; compare with
`results/linux-x86_64-cloud/dependencies/` (versions should match; `pydantic-core` and other
compiled wheels will differ by platform tag).

## 3. Local-only execution

`audit/run_audit.sh` is **Linux-only** (`unshare -n`, `strace`). There is no macOS equivalent of a
per-process network namespace; use one of these and say which in the results:

1. **Physical isolation**: disable Wi-Fi and unplug Ethernet, then prove it:
   `curl -sS --max-time 5 https://pypi.org >/dev/null && echo NOT ISOLATED`.
2. **`sandbox-exec`** (deprecated by Apple but present): profile `deny-net.sb`:
   ```scheme
   (version 1)
   (allow default)
   (deny network-outbound (remote ip))
   (deny network-inbound (local ip))
   ```
   `sandbox-exec -f deny-net.sb "$WORK/venv-A/bin/python" evals/evals_experiment.py "$WORK/evals-offline"`.
   First prove the profile blocks egress (`sandbox-exec -f deny-net.sb curl -sS https://pypi.org`
   must fail) and still allows the local Unix-socket pair asyncio needs (the experiment must finish).
   If either check fails, record that and fall back to option 1. Do not report a run as network
   isolated unless one of these checks was recorded.

Observation without `strace` (`dtruss`/`opensnoop` need SIP disabled; do not disable it for this):

- The in-process probe works unchanged: `python audit/probe_run.py OUT [--configure-logfire]`
  (audit-hook events, environment reads, canaries, import time, peak RSS — the RSS unit difference
  between macOS and Linux is handled).
- File and network activity of the probe: `sudo fs_usage -w -f filesys,network -t 60 python3` in a
  second terminal while the probe runs.
- Sockets: `lsof -a -i -p <pid>` during the run.
- Scenarios B–E: rerun with `venv-B`, `--configure-logfire`, the `OTEL_*` and token variables from
  `audit/run_audit.sh`, and `python3 audit/otlp_sink.py OUT/sink 4318` listening on `127.0.0.1` only.
  Never point `OTEL_EXPORTER_OTLP_ENDPOINT` or `LOGFIRE_BASE_URL` at anything but the local sink.

Expectation to verify, not assume: the Linux findings (no network or subprocess without Logfire;
full content export with Logfire + inherited `OTEL_EXPORTER_OTLP_ENDPOINT`; `git rev-parse HEAD` on
`logfire.configure()`) are code-level and should reproduce. `host.id` on macOS comes from a different
source than `/etc/machine-id`; record what is exported.

## 4. macOS filesystem behavior

- **SQLite durability**: on macOS `fsync()` does not flush the drive's write cache; SQLite only uses
  `F_FULLFSYNC` with `PRAGMA fullfsync=ON`. Run the crash scenarios twice: default, and with
  `SW_SQLITE_FULLFSYNC=1` (the worker then sets `fullfsync` and `checkpoint_fullfsync`). `SIGKILL`
  tests prove crash consistency of the *process*, on any OS; they do **not** prove power-loss
  durability, which needs a hard power cut of the machine and is out of scope unless done
  deliberately.
- **Case-insensitive APFS (default)**: preserved ledgers are named `<case>--<impl>.sqlite3`.
  Pydantic Evals accepts case names that differ only by letter case; such names would collide here.
  Check: `ls results/macos-arm64/evals/ledgers | tr A-Z a-z | sort | uniq -d` must print nothing.
- **Paths**: `/tmp` is a symlink to `/private/tmp`, and `TMPDIR` is a per-user `/var/folders/...`.
  Compare resolved paths (`realpath`) when classifying where files were written.
- **Spotlight/Time Machine** may index or copy the evidence directories; exclude `$WORK` (`tmutil
  addexclusion`, `mdutil -i off` on a dedicated volume) if test content must not leave the run directory.

## 5. Interruption and restart

1. `WORKER_IMPL=v1-correct python -m pytest -q` and `WORKER_IMPL=v4-nonatomic-resume python -m pytest -q`
   (real `SIGKILL` crash scenarios and the in-process state machine; `v4` must fail).
2. `python evals/probe_framework.py OUT.json --probe kill_mid_evaluation --probe teardown_exception`.
3. macOS-specific: run `evals/evals_experiment.py` with the lid closed / `pmset sleepnow` mid-run,
   and with `caffeinate -i` to rule out App Nap or sleep effects; record whether results and
   durations change. Note that a sleeping machine is not a crash.

## 6. CPU and memory

```bash
/usr/bin/time -l "$WORK/venv-A/bin/python" evals/evals_experiment.py "$WORK/evals"     # maximum resident set size is in BYTES on macOS
"$WORK/venv-A/bin/python" -X importtime -c 'import pydantic_evals' 2>&1 | tail -1     # compare with results/linux-x86_64-cloud/dependencies/import-time--A.txt
```

Record: wall time, user/sys CPU, peak RSS, import time (3 runs each), chip model
(`sysctl -n machdep.cpu.brand_string`), macOS version (`sw_vers`), and whether on battery.

## 7. Optional: local models

Only after sections 1–6 pass. Serve a model on loopback (e.g. an OpenAI-compatible server on
`127.0.0.1`), install `pydantic-ai-slim[openai]` into a *third* venv, and point the client's base URL
at `http://127.0.0.1:<port>/v1`. Verify with `lsof -a -i -p <pid>` that the evaluation process only
connects to `127.0.0.1`. Record the model name, quantization, file SHA-256 and server version in
`experiment_metadata`; use `repeat=N` and report spread, because local inference is not guaranteed
deterministic even at temperature 0. Evaluate recorded model outputs with
`evals/reevaluate_recorded.py`-style replay so that judge or evaluator changes do not require new
generations.
