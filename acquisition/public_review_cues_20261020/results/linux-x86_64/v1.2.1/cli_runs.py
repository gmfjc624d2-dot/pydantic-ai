"""Run the real CLI as a subprocess and record exit status, stdout/stderr byte counts, wall time and peak RSS.

Usage (from acquisition/public_review_cues_20261020/):
    python3 results/linux-x86_64/v1.2.1/cli_runs.py OUT.jsonl

Each run goes through a fresh wrapper process whose only child is the CLI, so the wrapper's
RUSAGE_CHILDREN ru_maxrss is that CLI process's peak RSS (KiB on Linux, bytes on macOS). One run per case.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]  # acquisition/public_review_cues_20261020
sys.path.insert(0, str(HERE))
import benchmark  # noqa: E402

WRAPPER = """
import json, resource, subprocess, sys, time
payload = sys.stdin.buffer.read()
started = time.perf_counter()
proc = subprocess.run([sys.executable, sys.argv[1], *sys.argv[2:]], input=payload, capture_output=True, check=False)
seconds = time.perf_counter() - started
code = None
for stream in (proc.stdout, proc.stderr):
    try:
        code = json.loads(stream).get('error', {}).get('code', code)
    except ValueError:
        pass
print(json.dumps({'exit': proc.returncode, 'stdout_bytes': len(proc.stdout), 'stderr_bytes': len(proc.stderr),
                  'error_code': code, 'seconds': seconds,
                  'child_ru_maxrss': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}))
"""


def request(text: str, language: str) -> bytes:
    return json.dumps({'text': text, 'language': language}).encode('ascii')


def main() -> None:
    dense = request(benchmark.make_text('dense_disjoint', 100_000), 'es+en')
    small = request('\U0001f4ccSegún el guía, provided\r\nthat only if no, señor', 'es+en')
    sys.path.insert(0, str(HERE / 'review_cues'))
    import review_cues

    small_size = len(review_cues.render_cues(json.loads(small)['text'], 'es+en'))
    cases = [
        ('dense 100,000 code points, no budget', dense, []),
        ('dense, budget 1 MiB', dense, ['--max-output-bytes', '1048576']),
        ('dense, budget 100 MiB', dense, ['--max-output-bytes', '104857600']),
        ('small Unicode, no budget', small, []),
        ('small Unicode, budget N - 1', small, ['--max-output-bytes', str(small_size - 1)]),
        ('small Unicode, budget N', small, ['--max-output-bytes', str(small_size)]),
        ('budget 511', small, ['--max-output-bytes', '511']),
        ('budget of 5,000 digits', small, ['--max-output-bytes', '9' * 5000]),
    ]
    script = str(HERE / 'review_cues' / 'review_cues.py')
    with open(sys.argv[1], 'w', encoding='utf-8') as log:
        log.write(
            json.dumps({'python': platform.python_version(), 'platform': platform.platform(), 'small_n': small_size})
            + '\n'
        )
        for name, payload, argv in cases:
            proc = subprocess.run(
                [sys.executable, '-I', '-c', WRAPPER, script, *argv],
                input=payload,
                capture_output=True,
                timeout=300,
                check=True,
            )
            row = {'case': name, 'request_bytes': len(payload), **json.loads(proc.stdout)}
            log.write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
