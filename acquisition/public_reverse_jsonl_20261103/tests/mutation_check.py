"""Show that the tests reject plausible broken variants of reverse_lines (standard library only).

Run: python3 tests/mutation_check.py   (from acquisition/public_reverse_jsonl_20261103)

Each mutation makes one textual edit to a copy of reverse_lines.py in a temporary directory (the edit must match
exactly once), then runs the unittest suite against that copy in a subprocess with a time limit. Every mutation
must make the suite fail or time out; the failing tests are listed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = (ROOT / 'reverse_lines.py').read_text(encoding='utf-8')

MUTATIONS = {
    'CRLF split across two chunks read as two line ends': (
        "    if start == 0:\n        return b'\\n', 0",
        "    if True:\n        return b'\\n', 0",
    ),
    'CR position not rescanned after a CRLF': ('                if cr >= hi:\n', '                if cr > hi:\n'),
    'phantom empty line after a final line end': ('if line.content or line.terminator:', 'if True:'),
    'initial empty line dropped': (
        "        yield from finish(0, b'')\n",
        "        yield from (line for line in finish(0, b'') if line.content)\n",
    ),
    'line start offset one byte early': (
        'yield from finish(start + i + 1, line_end[0])',
        'yield from finish(start + i, line_end[0])',
    ),
    'invalid UTF-8 dropped instead of replaced': (
        "content.decode('utf-8', 'replace')",
        "content.decode('utf-8', 'ignore')",
    ),
    'terminator kept raw instead of normalized': (
        "return _decode(self.content) + ('\\n' if self.terminator else '')",
        'return _decode(self.content + self.terminator)',
    ),
    'short read taken as end of data': (
        '            if not piece:\n                raise ExtentChangedError(',
        '            if not piece:\n                break\n                raise ExtentChangedError(',
    ),
    'explicit end ignored': ('        self.extent = end\n', '        self.extent = self.stat.st_size\n'),
    'max_line_bytes ignored': ('if limit is not None and size > limit:', 'if False:'),
    'malformed JSON silently skipped under report': (
        '            yield JsonRecord(line, error=str(e))\n',
        '            continue\n',
    ),
}


def run_suite(module_dir: str) -> tuple:
    env = {**os.environ, 'REVERSE_LINES_UNDER_TEST': module_dir}
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests')],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=ROOT,
        )
    except subprocess.TimeoutExpired:
        return None, ['(timed out after 120 s)']
    failing = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\S+) \(\S*?\.(\w+)', proc.stderr, re.M)))
    return proc.returncode, [f'{cls}.{name}' for name, cls in failing]


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'reverse_lines.py').write_text(SOURCE, encoding='utf-8')
        status, failing = run_suite(tmp)
        print(f'unmutated copy: exit {status}, failing {failing}')
        ok = status == 0
        for label, (old, new) in MUTATIONS.items():
            if SOURCE.count(old) != 1:
                print(f'{label}: edit matched {SOURCE.count(old)} times -> BROKEN MUTATION')
                ok = False
                continue
            (Path(tmp) / 'reverse_lines.py').write_text(SOURCE.replace(old, new), encoding='utf-8')
            status, failing = run_suite(tmp)
            detected = status != 0
            print(f'{label}: {len(failing)} failing test(s) -> {"rejected" if detected else "NOT DETECTED"}')
            for name in failing:
                print(f'    {name}')
            ok = ok and detected
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
