"""Measure reverse_lines on large synthetic files (standard library only).

Run: python3 bench/measure.py OUT.jsonl   (from acquisition/public_reverse_jsonl_20261103)

Each scenario runs in its own subprocess (python -I) and writes its synthetic file into a fresh temporary
directory, removed afterwards. Times are of an untraced run; peak memory is tracemalloc's peak of Python allocations in a second, traced run,
and ru_maxrss the subprocess's peak resident size as getrusage reports it (KiB on Linux, bytes on macOS).
Timings describe the host they ran on and are not guarantees.
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import reverse_lines as rl  # noqa: E402

MIB = 1 << 20
STREAK = 5000


def write_streak_file(path: Path, target_bytes: int) -> int:
    """JSONL records ~100 bytes each; the newest STREAK have status "ok", the one before "fail"."""
    rng = random.Random(20261103)
    lines, size, seq = [], 0, 0
    with open(path, 'wb') as f:
        while size < target_bytes:
            status = 'ok' if rng.random() < 0.9 else 'fail'
            line = json.dumps({'seq': seq, 'status': status, 'pad': 'p' * rng.randrange(40, 80)}) + '\n'
            lines.append(line)
            size += len(line)
            seq += 1
            if len(lines) == 10_000:
                f.write(''.join(lines).encode())
                lines = []
        lines.append(json.dumps({'seq': seq, 'status': 'fail', 'pad': ''}) + '\n')
        seq += 1
        for _ in range(STREAK):
            lines.append(json.dumps({'seq': seq, 'status': 'ok', 'pad': 'p' * rng.randrange(40, 80)}) + '\n')
            seq += 1
        f.write(''.join(lines).encode())
    return seq


def measured(fn):
    """Run fn twice: timed without tracing, then under tracemalloc for its peak (tracing slows it down)."""
    started = time.perf_counter()
    result = fn()
    seconds = time.perf_counter() - started
    tracemalloc.start()
    traced = fn()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert traced == result, 'the traced run gave a different result'
    return result, {'seconds': round(seconds, 4), 'tracemalloc_peak_bytes': peak}


def scenario_early_stop(work: Path) -> dict:
    path = work / 'streak.jsonl'
    records = write_streak_file(path, 32 * MIB)
    size = path.stat().st_size

    def reverse():
        with rl.ReverseLineReader(path) as reader:
            streak = 0
            for record in rl.reverse_json_records(iter(reader), malformed='raise'):
                if record.value['status'] != 'ok':
                    break
                streak += 1
        return streak, reader.bytes_read, reader.read_calls

    def forward():
        streak = 0
        with open(path, encoding='utf-8', errors='replace', newline=None) as f:
            for line in f:
                streak = streak + 1 if json.loads(line)['status'] == 'ok' else 0
        return streak

    def fixed_tail(tail_bytes=64 * 1024):
        with open(path, 'rb') as f:
            f.seek(max(0, size - tail_bytes))
            lines = f.read().decode('utf-8', 'replace').splitlines()[1:]  # drop the first, partial line
        streak = 0
        for line in reversed(lines):
            if json.loads(line)['status'] != 'ok':
                break
            streak += 1
        return streak

    (streak, bytes_read, read_calls), reverse_cost = measured(reverse)
    forward_streak, forward_cost = measured(forward)
    tail_streak, tail_cost = measured(fixed_tail)
    return {
        'file_bytes': size,
        'records': records,
        'true_streak': STREAK,
        'reverse': {
            'streak': streak,
            'bytes_read': bytes_read,
            'read_calls': read_calls,
            'chunk_size': rl.DEFAULT_CHUNK_SIZE,
            **reverse_cost,
        },
        'forward_full_scan': {'streak': forward_streak, 'bytes_read': size, **forward_cost},
        'fixed_64KiB_tail': {'streak': tail_streak, 'bytes_read': min(size, 64 * 1024), **tail_cost},
    }


def scenario_full_equivalence(work: Path) -> dict:
    path = work / 'streak.jsonl'
    write_streak_file(path, 32 * MIB)

    def reverse():
        digest, count = hashlib.sha256(), 0
        with rl.ReverseLineReader(path) as reader:
            for line in reader:
                digest.update(line.text().encode('utf-8', 'surrogatepass'))
                count += 1
        return digest.hexdigest(), count, reader.bytes_read

    def forward():
        with open(path, encoding='utf-8', errors='replace', newline=None) as f:
            lines = list(f)
        digest = hashlib.sha256()
        for line in reversed(lines):
            digest.update(line.encode('utf-8', 'surrogatepass'))
        return digest.hexdigest(), len(lines)

    (reverse_digest, count, bytes_read), reverse_cost = measured(reverse)
    (forward_digest, forward_count), forward_cost = measured(forward)
    return {
        'file_bytes': path.stat().st_size,
        'lines': count,
        'equal': reverse_digest == forward_digest and count == forward_count,
        'reverse': {'sha256': reverse_digest, 'bytes_read': bytes_read, **reverse_cost},
        'forward_list_reversed': {'sha256': forward_digest, **forward_cost},
    }


def scenario_long_line(work: Path) -> dict:
    path = work / 'long.jsonl'
    line_bytes = 16 * MIB
    body = ('x' * 1023 + chr(0x20AC)).encode('utf-8')  # 1,026 bytes, a 3-byte character at the end of each piece
    with open(path, 'wb') as f:
        f.write(b'{"first": true}\n')
        written = 0
        while written + len(body) <= line_bytes:
            f.write(body)
            written += len(body)
        f.write(b'\n{"last": true}\n')

    def unlimited():
        with rl.ReverseLineReader(path) as reader:
            sizes = [len(line.content) for line in reader]
        return sizes, reader.bytes_read

    def limited():
        with rl.ReverseLineReader(path, max_line_bytes=MIB) as reader:
            try:
                for _ in reader:
                    pass
            except rl.LineTooLongError as e:
                return type(e).__name__, reader.bytes_read
        return 'no error', reader.bytes_read

    (sizes, bytes_read), unlimited_cost = measured(unlimited)
    (outcome, limited_read), limited_cost = measured(limited)
    return {
        'file_bytes': path.stat().st_size,
        'long_line_content_bytes': written,
        'unlimited': {'line_sizes': sizes, 'bytes_read': bytes_read, **unlimited_cost},
        'max_line_bytes_1MiB': {'outcome': outcome, 'bytes_read_at_failure': limited_read, **limited_cost},
    }


def scenario_dense_line_ends(work: Path) -> dict:
    out = {}
    for name, unit in (('lf', b'\n'), ('crlf', b'\r\n'), ('cr', b'\r')):
        path = work / f'{name}.txt'
        path.write_bytes(unit * (8 * MIB // len(unit)))

        def count_lines(path=path):
            with rl.ReverseLineReader(path) as reader:
                return sum(1 for _ in reader), reader.bytes_read

        (lines, bytes_read), cost = measured(count_lines)
        out[name] = {'file_bytes': path.stat().st_size, 'lines': lines, 'bytes_read': bytes_read, **cost}
        path.unlink()
    return out


SCENARIOS = {
    'early_stop_streak': scenario_early_stop,
    'full_reverse_equals_forward': scenario_full_equivalence,
    'long_line': scenario_long_line,
    'dense_line_ends': scenario_dense_line_ends,
}


def run_one(name: str) -> None:
    with tempfile.TemporaryDirectory(prefix='reverse_lines_bench_') as tmp:
        result = SCENARIOS[name](Path(tmp))
    result['ru_maxrss'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({'scenario': name, **result}))


def main() -> None:
    if sys.argv[1] == '--scenario':
        run_one(sys.argv[2])
        return
    out = Path(sys.argv[1])
    header = {
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'reverse_lines': rl.VERSION,
    }
    rows = [header]
    for name in SCENARIOS:
        proc = subprocess.run(
            [sys.executable, '-I', __file__, '--scenario', name],
            capture_output=True,
            text=True,
            timeout=1800,
            check=True,
        )
        rows.append(json.loads(proc.stdout))
        print(proc.stdout.strip())
    out.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


if __name__ == '__main__':
    main()
