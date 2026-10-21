"""Time and memory of render_cues() with and without an output budget, on synthetic 100,000-code-point texts.

Usage (from acquisition/public_review_cues_20261020/):
    python3 results/linux-x86_64/v1.2.0/budget/measure_budget.py OUT_DIR

Each cell is a fresh `python -I` process (120 s timeout) that builds the text with benchmark.make_text(),
warms up the rules, then calls render_cues() once. "time" runs (3 per cell) record wall time and the
process's peak RSS (resource.getrusage ru_maxrss: KiB on Linux, bytes on macOS) before and after the call;
one "tracemalloc" run per cell records the peak of Python allocations during the call (slower; its time is
not reported). Observations for this host only; nothing is extrapolated.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[4]  # acquisition/public_review_cues_20261020
SHAPES = {'dense_disjoint': 'es+en', 'dense_nested': 'en', 'mixed_sentences': 'es+en', 'cue_free': 'en'}
BUDGETS = [None, 65_536, 1_048_576, 10_485_760, 104_857_600]
WORKER = """
import json, resource, sys, time
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + '/review_cues')
import benchmark, review_cues
mode, shape, language = sys.argv[2], sys.argv[3], sys.argv[4]
budget = None if sys.argv[5] == 'none' else int(sys.argv[5])
text = benchmark.make_text(shape, 100_000)
review_cues.render_cues('if', 'en')
rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if mode == 'tracemalloc':
    import tracemalloc
    tracemalloc.start()
started = time.perf_counter()
try:
    output = review_cues.render_cues(text, language, max_output_bytes=budget)
    row = {'outcome': 'ok', 'output_bytes': len(output)}
except review_cues.CueInputError as e:
    row = {'outcome': e.code, **e.details}
row['seconds'] = time.perf_counter() - started
if mode == 'tracemalloc':
    row['tracemalloc_peak_bytes'] = tracemalloc.get_traced_memory()[1]
    del row['seconds']
row.update(ru_maxrss_before=rss_before, ru_maxrss_after=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
print(json.dumps(row))
"""


def main() -> None:
    out = Path(sys.argv[1]) / f'python{sys.version_info[0]}.{sys.version_info[1]}'
    out.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(['git', '-C', str(HERE), 'rev-parse', 'HEAD'], capture_output=True, check=True).stdout
    changes = subprocess.run(
        ['git', '-C', str(HERE), 'status', '--porcelain', '--', '.'], capture_output=True, check=True
    )
    details = {
        'python': platform.python_version(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'cpu_count': os.cpu_count(),
        'ru_maxrss_unit': 'bytes' if sys.platform == 'darwin' else 'KiB',
        'head_commit': head.decode().strip(),
        'working_tree_changes_in_this_directory': changes.stdout.decode().splitlines(),
        'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'loadavg_before': os.getloadavg(),
    }
    rows = []
    with (out / 'measurements.jsonl').open('w', encoding='utf-8') as log:
        for shape, language in SHAPES.items():
            for budget in BUDGETS:
                for mode, repeat in [('time', 1), ('time', 2), ('time', 3), ('tracemalloc', 1)]:
                    row = {
                        'shape': shape,
                        'language': language,
                        'max_output_bytes': budget,
                        'mode': mode,
                        'repeat': repeat,
                    }
                    cmd = [sys.executable, '-I', '-c', WORKER, str(HERE), mode, shape, language, str(budget).lower()]
                    try:
                        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=True)
                        row.update(json.loads(proc.stdout))
                    except subprocess.TimeoutExpired:
                        row['outcome'] = 'timeout (> 120 s)'
                    rows.append(row)
                    log.write(json.dumps(row) + '\n')
                    log.flush()
                    print(json.dumps(row), flush=True)
    details.update(finished_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), loadavg_after=os.getloadavg())
    (out / 'platform.json').write_text(json.dumps(details, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
