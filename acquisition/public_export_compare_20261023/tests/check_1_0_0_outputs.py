"""Check that the current module reproduces every committed 1.0.0 CLI stdout, apart from the version string.

Run (from acquisition/public_export_compare_20261023):  python3 tests/check_1_0_0_outputs.py

It reruns the 3 positive pairs and 35 single-edit cases of tests/run_cases.py through the CLI, replaces the one
`"version": "<current>"` with `"version": "1.0.0"`, and compares the SHA-256 with the `stdout_sha256` that
results/linux-x86_64/python<major.minor>/cases.jsonl recorded for 1.0.0 (Linux, CPython 3.9.25 or 3.13.16).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

UNIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UNIT))
sys.path.insert(0, str(UNIT / 'tests'))
import export_compare  # noqa: E402
import run_cases  # noqa: E402

cases = run_cases.cases


def main() -> int:
    series = '.'.join(platform.python_version_tuple()[:2])
    recorded_path = UNIT / 'results' / 'linux-x86_64' / f'python{series}' / 'cases.jsonl'
    rows = [json.loads(line) for line in recorded_path.read_text(encoding='utf-8').splitlines()[1:]]
    recorded = {row['case']: row['stdout_sha256'] for row in rows}
    current = f'"version": "{export_compare.TOOL_VERSION}"'.encode()
    runs = {
        f'positive:{name}': ['--plain', str(run_cases.FIXTURES / p), '--markdown', str(run_cases.FIXTURES / m), *extra]
        for name, (p, m, extra) in run_cases.POSITIVE.items()
    }
    same, different = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases.CASES:
            plain, markdown, options = cases.apply_case(case)
            plain_path, markdown_path = Path(tmp) / f'{case["id"]}.txt', Path(tmp) / f'{case["id"]}.md'
            args = ['--plain', str(plain_path), '--markdown', str(markdown_path)]
            for key, value in options.items():
                args += ['--rules', ','.join(value)] if key == 'rules' else [run_cases.FLAGS[key], str(value)]
            plain_path.write_bytes(plain)
            markdown_path.write_bytes(markdown)
            runs[case['id']] = args
        for name, args in runs.items():
            _, stdout, _ = run_cases.run_cli(args)
            if 'error' not in json.loads(stdout):  # rejections carry no tool version
                assert stdout.count(current) == 1, name
                stdout = stdout.replace(current, b'"version": "1.0.0"')
            if hashlib.sha256(stdout).hexdigest() == recorded[name]:
                same += 1
            else:
                different.append(name)
    where = recorded_path.relative_to(UNIT)
    print(f'Python {platform.python_version()}: module {export_compare.TOOL_VERSION} against 1.0.0 {where}')
    print(f'{len(runs)} runs, {len(recorded)} recorded; identical apart from the version: {same}; differ: {different}')
    return 0 if same == len(recorded) == len(runs) else 1


if __name__ == '__main__':
    sys.exit(main())
