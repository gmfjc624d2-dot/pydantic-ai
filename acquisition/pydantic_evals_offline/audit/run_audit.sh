#!/usr/bin/env bash
# Privacy and network audit of pydantic-evals, scenarios A-E (see ../REPORT.md).
#
# Usage: audit/run_audit.sh VENV_A VENV_B RESULTS_DIR
#   VENV_A: pydantic-evals without logfire; VENV_B: pydantic-evals[logfire].
#
# Every run happens inside `unshare -n` (a fresh network namespace: no interfaces except a
# loopback that is DOWN unless a local sink is needed), under `strace -f`, with `env -i`, a
# temporary HOME/TMPDIR/cwd, and PYTHONDONTWRITEBYTECODE=1. No run can reach a real network,
# so nothing is ever sent to a hosted telemetry service; attempts show up in strace instead.
set -euo pipefail

VENV_A=$(realpath "$1")
VENV_B=$(realpath "$2")
RESULTS=$(realpath -m "$3")
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
mkdir -p "$RESULTS"

TRACE_SET='%network,execve,execveat,clone,clone3,fork,vfork,openat,open,creat,mkdir,mkdirat,rename,renameat,renameat2,unlink,unlinkat'
OTEL_ENV='OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 OTEL_TRACES_EXPORTER=otlp OTEL_SERVICE_NAME=privacy-audit OTEL_RESOURCE_ATTRIBUTES=deployment.environment=audit'
# A syntactically plausible but fake token; the namespace has no route to any real endpoint.
TOKEN_ENV='LOGFIRE_TOKEN=pylf_v1_us_0000000000000000000000000000000000000000fake LOGFIRE_SEND_TO_LOGFIRE=true'

run_case() {
    local id=$1 venv=$2 flags=$3 extra_env=$4 sink=$5
    local R="$RESULTS/$id"
    rm -rf "$R"
    mkdir -p "$R"
    local T
    T=$(mktemp -d "/tmp/pe-audit-$id.XXXXXX")
    mkdir -p "$T/home" "$T/tmp" "$T/cwd"
    printf '%s\n' "venv=$venv" "probe_flags=$flags" "extra_env=$extra_env" "local_sink=$sink" "sandbox=$T" > "$R/run.txt"
    unshare -n bash -c "
        set -e
        if [ '$sink' = yes ]; then
            /usr/bin/python3 '$HERE/netns_lo_up.py'
            /usr/bin/python3 '$HERE/otlp_sink.py' '$R/sink' 4318 &
            sleep 0.5
        fi
        cd '$T/cwd'
        env -i HOME='$T/home' TMPDIR='$T/tmp' PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 $extra_env \
            strace -f -qq -s 256 -e trace='$TRACE_SET' -o '$R/strace.txt' \
            '$venv/bin/python' '$HERE/probe_run.py' '$R/out' $flags > '$R/stdout.txt' 2> '$R/stderr.txt' || echo \"exit=\$?\" >> '$R/run.txt'
        sleep 0.5
        if [ '$sink' = yes ]; then kill %1 2>/dev/null || true; fi
    "
    (cd "$T" && find . -type f | sort) > "$R/files_left_in_sandbox.txt"
    grep -rlE 'CANARY-(INPUT|SECRETKEY|META|EXPECTED|OUTPUT|ERROR)' "$T" > "$R/canary_files_in_sandbox.txt" 2>/dev/null || true
    rm -rf "$T"
    echo "done: $id"
}

# A. pydantic-evals without Logfire.
run_case A "$VENV_A" '' '' no
# B. Logfire installed but not configured.
run_case B "$VENV_B" '' '' no
# C. Logfire configured with send_to_logfire=False.
run_case C "$VENV_B" '--configure-logfire' '' no
# D. Inherited OpenTelemetry / Logfire variables, applied to A, B and C (local sink listening).
run_case D-A-otel "$VENV_A" '' "$OTEL_ENV" yes
run_case D-B-otel "$VENV_B" '' "$OTEL_ENV" yes
run_case D-C-otel "$VENV_B" '--configure-logfire' "$OTEL_ENV" yes
run_case D-B-token "$VENV_B" '' "$TOKEN_ENV" no
run_case D-C-token "$VENV_B" '--configure-logfire' "$TOKEN_ENV" no
# E. Simulated local exporter: in-memory span processor shows exactly which content enters spans.
run_case E-memory "$VENV_B" '--configure-logfire --memory-exporter' '' no

# Full experiment and baseline with NO network at all (loopback down), to show they complete offline.
full_offline() {
    local id=$1
    shift
    local R="$RESULTS/$id"
    rm -rf "$R"
    mkdir -p "$R"
    local T
    T=$(mktemp -d "/tmp/pe-audit-$id.XXXXXX")
    mkdir -p "$T/home" "$T/tmp"
    echo "sandbox=$T" > "$R/run.txt"
    unshare -n env -i HOME="$T/home" TMPDIR="$T/tmp" PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
        strace -f -qq -s 256 -e trace="$TRACE_SET" -o "$R/strace.txt" "$@" > "$R/stdout.txt" 2> "$R/stderr.txt" \
        && echo "exit=0" >> "$R/run.txt" || echo "exit=$?" >> "$R/run.txt"
    rm -rf "$T"
    echo "done: $id"
}
cd "$ROOT"
full_offline offline-evals-experiment "$VENV_A/bin/python" evals/evals_experiment.py "$RESULTS/offline-evals-experiment/out" --generated 20
full_offline offline-pytest-baseline "$VENV_A/bin/python" -m pytest -q -p no:randomly

# Decode whatever reached the local sink, then summarize.
for sink in "$RESULTS"/*/sink; do
    if [ -d "$sink" ]; then "$VENV_B/bin/python" "$HERE/decode_otlp.py" "$sink"; fi
done
/usr/bin/python3 "$HERE/analyze.py" "$RESULTS" > /dev/null
