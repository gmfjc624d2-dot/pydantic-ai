"""Differential evaluation of the public package file_read_backwards against the same text-mode reference.

Run: python3 -I evaluation/file_read_backwards_eval.py PACKAGE_DIR OUT.json
     (PACKAGE_DIR holds the unpacked sdist, i.e. the directory containing file_read_backwards/)

The package is imported from PACKAGE_DIR, not installed. It yields line contents without terminators, so its
output is compared with the reference's lines minus their (normalized) terminator; differences in terminator
information are reported separately. All data is synthetic.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import platform
import random
import sys
import tempfile
import time
from pathlib import Path

PACKAGE_DIR = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reverse_lines as rl  # noqa: E402
from file_read_backwards import FileReadBackwards  # noqa: E402

U2028 = chr(0x2028)


def forward_contents(path):
    with open(path, encoding='utf-8', errors='replace', newline=None) as f:
        lines = list(f)
    return [line[:-1] if line.endswith('\n') else line for line in reversed(lines)]


def candidate(path, chunk_size):
    with FileReadBackwards(str(path), encoding='utf-8', chunk_size=chunk_size) as frb:
        return list(itertools.islice(frb, 100_000))


def corpus():
    alphabet = [b'\r', b'\n', b'a', b'\xe2', b'\x82', b'\xac']
    for n in range(5):
        for combo in itertools.product(alphabet, repeat=n):
            yield b''.join(combo)
    rng = random.Random(20261103)
    tokens = [b'\r', b'\n', b'\r\n', b'a', b'{"k": 1}', b' ', b'\xe2\x82\xac', b'\xf0\x9f\x98\x80', b'\xc3\xa9']
    tokens += [b'\xe2', b'\x82', b'\xac', b'\xf0\x9f', b'\xff', b'\xed\xa0\x80', b'\xef\xbb\xbf', b'\x00']
    tokens += [b'\x0b', b'\x0c', U2028.encode('utf-8'), chr(0x2029).encode('utf-8'), chr(0x85).encode('utf-8')]
    for _ in range(2000):
        yield b''.join(rng.choice(tokens) for _ in range(rng.randrange(0, 60)))


def differential(work):
    path = work / 'case.txt'
    outcome = {'valid_utf8': {}, 'invalid_utf8': {}}
    examples = {}
    for data in corpus():
        path.write_bytes(data)
        expected = forward_contents(path)
        try:
            data.decode('utf-8')
            kind = 'valid_utf8'
        except UnicodeDecodeError:
            kind = 'invalid_utf8'
        for chunk_size in (1, 2, 3, 5, 8192):
            try:
                got = candidate(path, chunk_size)
                result = 'equal' if got == expected else 'different'
            except Exception as e:  # recorded, not hidden
                result = f'raised {type(e).__name__}'
            outcome[kind][result] = outcome[kind].get(result, 0) + 1
            if result != 'equal' and result not in examples:
                examples[result] = {'data': repr(data), 'chunk_size': chunk_size}
    return {'outcomes': outcome, 'first_example_of_each_non_equal_outcome': examples}


def terminator_information(work):
    out = {}
    for data in (b'a', b'a\n', b'a\r\n', b'a\r'):
        path = work / 'term.txt'
        path.write_bytes(data)
        with rl.ReverseLineReader(path) as reader:
            ours = [(line.content.decode(), line.terminator.decode()) for line in reader]
        out[repr(data)] = {'file_read_backwards': candidate(path, 8192), 'reverse_lines_content_and_terminator': ours}
    return out


def long_lines(work):
    out = []
    for mib in (0.25, 0.5, 1, 2, 4):
        size = int(mib * (1 << 20))
        path = work / 'long.txt'
        path.write_bytes(b'head\n' + b'x' * size + b'\n')
        started = time.perf_counter()
        frb = candidate(path, 8192)
        frb_seconds = time.perf_counter() - started
        started = time.perf_counter()
        with rl.ReverseLineReader(path, chunk_size=8192) as reader:
            ours = [line.content.decode() for line in reader]
        ours_seconds = time.perf_counter() - started
        out.append(
            {
                'line_bytes': size,
                'chunk_size': 8192,
                'same_contents': frb == ours,
                'file_read_backwards_seconds': round(frb_seconds, 4),
                'reverse_lines_seconds': round(ours_seconds, 4),
            }
        )
    return out


def truncation_during_iteration(work):
    path = work / 'trunc.txt'
    data = b''.join(b'line %04d\n' % i for i in range(1000))
    out = {}
    for name in ('file_read_backwards', 'reverse_lines'):
        path.write_bytes(data)
        lines, error = [], None
        try:
            if name == 'file_read_backwards':
                with FileReadBackwards(str(path), encoding='utf-8', chunk_size=64) as frb:
                    iterator = iter(frb)
                    lines.append(next(iterator))
                    os.truncate(path, 100)
                    lines.extend(iterator)
            else:
                with rl.ReverseLineReader(path, chunk_size=64) as reader:
                    iterator = iter(reader)
                    lines.append(next(iterator).text())
                    os.truncate(path, 100)
                    lines.extend(line.text() for line in iterator)
        except Exception as e:
            error = f'{type(e).__name__}: {e}'.replace(repr(path), '<path>').replace(str(path), '<path>')
        out[name] = {'lines_returned': len(lines), 'last_lines': [str(x) for x in lines[-3:]], 'error': error}
    out['lines_in_original_file'] = 1000
    return out


def os_read_bytes_for_early_stop(work):
    """Linux only: rchar from /proc/self/io, the bytes the process's read calls returned (each look at
    /proc/self/io itself adds its own size, about 130 bytes, to the next difference)."""
    io_path = Path('/proc/self/io')
    if not io_path.exists():
        return 'not measured: /proc/self/io is not available on this platform'
    path = work / 'many.jsonl'
    path.write_bytes(b''.join(b'{"seq": %d}\n' % i for i in range(200_000)))

    def rchar():
        return int(dict(line.split(': ') for line in io_path.read_text().splitlines())['rchar'])

    out = {'file_bytes': path.stat().st_size}
    before = rchar()
    with FileReadBackwards(str(path), encoding='utf-8') as frb:
        first = list(itertools.islice(frb, 10))
    out['file_read_backwards_10_lines_rchar'] = rchar() - before
    before = rchar()
    with rl.ReverseLineReader(path, chunk_size=8192) as reader:
        ours = [line.content.decode() for line in itertools.islice(reader, 10)]
    out['reverse_lines_10_lines_rchar'] = rchar() - before
    out['reverse_lines_bytes_read_counter'] = reader.bytes_read
    out['same_lines'] = first == ours
    return out


def main():
    out_path = Path(sys.argv[2])
    sources = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((PACKAGE_DIR / 'file_read_backwards').glob('*.py'))
    }
    with tempfile.TemporaryDirectory(prefix='frb_eval_') as tmp:
        work = Path(tmp)
        result = {
            'python': platform.python_version(),
            'platform': platform.platform(),
            'candidate': {'package_dir': PACKAGE_DIR.name, 'module_sha256': sources},
            'differential_contents': differential(work),
            'terminator_information': terminator_information(work),
            'long_lines': long_lines(work),
            'truncation_during_iteration': truncation_during_iteration(work),
            'os_read_bytes_for_early_stop': os_read_bytes_for_early_stop(work),
        }
    out_path.write_text(json.dumps(result, indent=1, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=1, ensure_ascii=True))


if __name__ == '__main__':
    main()
