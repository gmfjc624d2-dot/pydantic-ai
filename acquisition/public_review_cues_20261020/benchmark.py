"""Time find_cues() of the 1.0.0 baseline and of this version on synthetic texts under a timeout.

Usage:  python3 benchmark.py OUT_DIR [--timeout SECONDS] [--repeats N] [--sizes 2000,10000,50000,100000]
                                     [--baseline-commit SHA]

The baseline source is extracted with `git show SHA:./review_cues/...` (needs this repository's history).
Each measurement is a fresh `python -I` process that loads the rules with a warm-up call and then times one
find_cues() call with time.perf_counter(). Sizes (code points) run in ascending order, modest before
larger; after a timeout, the remaining repeats and larger sizes of that implementation and text shape are
recorded as not run. Outputs: measurements.jsonl (every attempted or skipped run), platform.json and
summary.md. A timeout only means "did not finish within the timeout"; nothing is extrapolated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
BASELINE_COMMIT = '1c8c9ca3bc40a842296acab56436ccc1d1283c46'  # last commit with review_cues 1.0.0
RUNTIME_FILES = ('review_cues.py', 'rules_v1.json')

# shape: (language, repeated unit or None for seeded sentences, description)
SHAPES = {
    'cue_free': ('en', 'The blue square sits next to a red circle. ', 'no cue at all'),
    'dense_disjoint': ('es', 'no ', 'a cue every 3 code points, none overlapping'),
    'dense_nested': ('en', 'Only if ', '"Only if" and nested "if" every 8 code points'),
    'mixed_sentences': ('es+en', None, 'seeded random ES/EN sentences, ~30% cue words'),
}
FILLER = ['the', 'room', 'opens', 'la', 'sala', 'abre', 'el', 'guía', 'museum', 'map', 'reloj', 'torre', 'and', 'y']
CUES = ['if', 'unless', 'no', 'not', 'never', 'may', 'must', 'según', 'quizás', 'a menos que', 'provided that']
CUES += ['except for', "isn't", 'Only if', 'nadie', 'debe']


def make_text(shape: str, size: int) -> str:
    """Deterministic synthetic text of exactly `size` code points (a prefix of the same text for larger sizes)."""
    _, unit, _ = SHAPES[shape]
    if unit is None:
        rng, parts, length = random.Random(20261020), [], 0
        while length < size:
            words = [rng.choice(CUES) if rng.random() < 0.3 else rng.choice(FILLER) for _ in range(rng.randint(5, 12))]
            sentence = ' '.join(words)
            parts.append(sentence[0].upper() + sentence[1:] + '. ')
            length += len(parts[-1])
        return ''.join(parts)[:size]
    return (unit * (size // len(unit) + 1))[:size]


def worker(impl_dir: str, shape: str, size: int) -> None:
    sys.path.insert(0, impl_dir)
    import review_cues

    review_cues.find_cues('if', 'en')  # warm-up: loads and compiles the rules
    text = make_text(shape, size)
    started = time.perf_counter()
    result = review_cues.find_cues(text, SHAPES[shape][0])
    seconds = time.perf_counter() - started
    version = result['tool'].pop('version')
    result.pop('configuration_sha256')
    print(
        json.dumps(
            {
                'seconds': seconds,
                'tool_version': version,
                'input_sha256': result['input']['sha256'],
                'match_count': result['match_count'],
                'overlap_pairs': sum(len(m['overlaps']) for m in result['matches']) // 2,
                'output_sha256_without_version_fields': hashlib.sha256(
                    json.dumps(result, ensure_ascii=False, sort_keys=True).encode('utf-8')
                ).hexdigest(),
            }
        )
    )


def git(*args: str) -> str:
    return subprocess.run(['git', '-C', str(HERE), *args], capture_output=True, check=True).stdout.decode().strip()


def platform_details() -> Dict[str, Any]:
    details: Dict[str, Any] = {
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'executable': sys.executable,
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
        'loadavg_before': os.getloadavg(),
    }
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        lines = cpuinfo.read_text(encoding='utf-8').splitlines()
        names = [line.split(':', 1)[1].strip() for line in lines if line.startswith('model name')]
        details['cpu_model'] = names[0] if names else None
    elif sys.platform == 'darwin':
        brand = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, check=False)
        details['cpu_model'] = brand.stdout.decode().strip() or None
    return details


def summarize(rows: List[Dict[str, Any]], timeout: float) -> List[str]:
    lines = [
        '| shape | language | code points | 1.0.0 seconds (min / median / max) '
        + '| this version seconds (min / median / max) | matches | overlapping pairs | outputs identical |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for shape in SHAPES:
        for size in sorted({r['size'] for r in rows}):
            cells, hashes, counts, finished = [], set(), set(), []
            for impl in ('baseline', 'revised'):
                runs = [r for r in rows if (r['impl'], r['shape'], r['size']) == (impl, shape, size)]
                done = [r for r in runs if r['status'] == 'ok']
                hashes |= {r['output_sha256_without_version_fields'] for r in done}
                counts |= {(r['match_count'], r['overlap_pairs']) for r in done}
                seconds = [r['seconds'] for r in done]
                cell = f'{min(seconds):.4f} / {statistics.median(seconds):.4f} / {max(seconds):.4f}' if done else ''
                if any(r['status'] == 'timeout' for r in runs):
                    cell = (cell + '; ' if cell else '') + f'timeout (> {timeout:g} s)'
                elif not done:
                    cell = 'not run (a smaller size timed out)'
                cells.append(cell)
                finished.append(bool(done))
            matches, pairs = next(iter(counts)) if len(counts) == 1 else ('?', '?')
            identical = 'NO' if len(hashes) > 1 else 'yes' if all(finished) else 'not compared'
            lines.append(
                f'| {shape} | {SHAPES[shape][0]} | {size:,} | {cells[0]} | {cells[1]} | {matches} | {pairs} | {identical} |'
            )
    return lines


def output_mismatches(rows: List[Dict[str, Any]]) -> List[Any]:
    keys = sorted({(r['shape'], r['size']) for r in rows})
    ok = [r for r in rows if r['status'] == 'ok']
    return [
        k
        for k in keys
        if len({r['output_sha256_without_version_fields'] for r in ok if (r['shape'], r['size']) == k}) > 1
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--timeout', type=float, default=60.0)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--sizes', default='2000,10000,50000,100000')
    parser.add_argument('--baseline-commit', default=BASELINE_COMMIT)
    args = parser.parse_args()
    sizes = sorted(int(s) for s in args.sizes.split(','))
    out: Path = args.out
    impls = {'baseline': out / 'baseline_src', 'revised': HERE / 'review_cues'}
    impls['baseline'].mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_FILES:
        content = subprocess.run(
            ['git', '-C', str(HERE), 'show', f'{args.baseline_commit}:./review_cues/{name}'],
            capture_output=True,
            check=True,
        ).stdout
        (impls['baseline'] / name).write_bytes(content)
    details = platform_details()
    details.update(
        {
            'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'head_commit': git('rev-parse', 'HEAD'),
            'working_tree_changes_in_this_directory': git('status', '--porcelain', '--', '.').splitlines(),
            'baseline_commit': args.baseline_commit,
            'file_sha256': {
                impl: {name: hashlib.sha256((path / name).read_bytes()).hexdigest() for name in RUNTIME_FILES}
                for impl, path in impls.items()
            },
            'timeout_seconds': args.timeout,
            'repeats': args.repeats,
            'sizes': sizes,
            'shapes': {name: {'language': lang, 'description': desc} for name, (lang, _, desc) in SHAPES.items()},
        }
    )
    rows: List[Dict[str, Any]] = []
    stopped = set()
    with (out / 'measurements.jsonl').open('w', encoding='utf-8') as log:
        for size in sizes:
            for shape in SHAPES:
                for repeat in range(1, args.repeats + 1):
                    for impl, path in impls.items():
                        row: Dict[str, Any] = {'impl': impl, 'shape': shape, 'size': size, 'repeat': repeat}
                        if (impl, shape) in stopped:
                            row['status'] = 'not_run_after_timeout'
                        else:
                            cmd = [
                                sys.executable,
                                '-I',
                                str(Path(__file__).resolve()),
                                '--worker',
                                str(path),
                                shape,
                                str(size),
                            ]
                            try:
                                proc = subprocess.run(cmd, capture_output=True, timeout=args.timeout, check=True)
                                row.update(status='ok', **json.loads(proc.stdout))
                            except subprocess.TimeoutExpired:
                                row.update(status='timeout', timeout_seconds=args.timeout)
                                stopped.add((impl, shape))
                        rows.append(row)
                        log.write(json.dumps(row) + '\n')
                        log.flush()
                        print(json.dumps(row), flush=True)
    details['finished_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    details['loadavg_after'] = os.getloadavg()
    (out / 'platform.json').write_text(json.dumps(details, indent=2) + '\n', encoding='utf-8')
    revised = next((r['tool_version'] for r in rows if r['impl'] == 'revised' and r['status'] == 'ok'), '?')
    summary = [
        f'# Benchmark: review_cues 1.0.0 (baseline) vs {revised} (Python {details["python"]}, {details["platform"]})',
        '',
        f'find_cues() wall time per call, one fresh process per run, {args.repeats} repeats, timeout {args.timeout:g} s. '
        + 'Raw rows: measurements.jsonl; platform: platform.json. "outputs identical": every completed run of both '
        + 'versions produced the same output apart from tool.version and configuration_sha256.',
        '',
        *summarize(rows, args.timeout),
    ]
    (out / 'summary.md').write_text('\n'.join(summary) + '\n', encoding='utf-8')
    print('\n'.join(summary))
    mismatches = output_mismatches(rows)
    if mismatches:
        print(f'OUTPUTS DIFFER for {mismatches}')
    return 1 if mismatches else 0


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        worker(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        sys.exit(main())
