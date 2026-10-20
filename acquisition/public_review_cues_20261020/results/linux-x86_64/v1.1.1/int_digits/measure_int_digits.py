"""Time the CLI path (main() on an in-memory request) for {"text": <N-digit integer>, "language": "en"}.

Usage (from acquisition/public_review_cues_20261020/):
    python3 results/linux-x86_64/v1.1.1/int_digits/measure_int_digits.py BASELINE_1_1_0_DIR OUT.jsonl

BASELINE_1_1_0_DIR holds review_cues.py and rules_v1.json from commit 0419f01 (`git show`). Each run is a
fresh `python -I` process with a 60 s timeout, either with the interpreter's default integer
string-conversion limit or with `-X int_max_str_digits=0`, which disables it and so emulates interpreters
without the limit (such as CPython 3.9.6, which was not run here). Only main() is timed.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[4]  # acquisition/public_review_cues_20261020
SIZES = (5_000, 50_000, 100_000, 200_000, 1_265_511)  # the last fills MAX_REQUEST_BYTES exactly
WORKER = """
import io, json, sys, time
sys.path.insert(0, sys.argv[1])
import review_cues
payload = b'{"text":' + b'7' * int(sys.argv[2]) + b',"language":"en"}'
assert len(payload) <= 1_265_536
out = io.BytesIO()
started = time.perf_counter()
try:
    status = review_cues.main([], stdin=io.BytesIO(payload), stdout=out)
    outcome = json.loads(out.getvalue())['error']['code'] if status else 'ok'
except Exception as e:
    status, outcome = 'uncaught', type(e).__name__
seconds = time.perf_counter() - started
print(json.dumps({'version': review_cues.TOOL_VERSION, 'payload_bytes': len(payload), 'status': status,
                  'outcome': outcome, 'seconds': seconds}))
"""


def main() -> None:
    baseline, out = Path(sys.argv[1]), Path(sys.argv[2])
    impls = {'1.1.0': baseline, 'working tree': HERE / 'review_cues'}
    settings = {'default limit': [], 'limit disabled (-X int_max_str_digits=0)': ['-X', 'int_max_str_digits=0']}
    with out.open('w', encoding='utf-8') as log:
        header = {'python': platform.python_version(), 'platform': platform.platform(), 'executable': sys.executable}
        log.write(json.dumps(header) + '\n')
        for label, xopt in settings.items():
            for impl, path in impls.items():
                for digits in SIZES:
                    row = {'impl': impl, 'setting': label, 'digits': digits}
                    try:
                        cmd = [sys.executable, '-I', *xopt, '-c', WORKER, str(path), str(digits)]
                        proc = subprocess.run(cmd, capture_output=True, timeout=60, check=True)
                        row.update(json.loads(proc.stdout))
                    except subprocess.TimeoutExpired:
                        row.update(status='timeout', timeout_seconds=60)
                    log.write(json.dumps(row) + '\n')
                    log.flush()
                    print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
