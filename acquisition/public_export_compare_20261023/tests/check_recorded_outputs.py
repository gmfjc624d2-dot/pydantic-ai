"""Check that the current module reproduces every recorded CLI stdout of an earlier version, apart from its version.

Run (from acquisition/public_export_compare_20261023):
    python3 tests/check_recorded_outputs.py results/linux-x86_64 1.0.0
    python3 tests/check_recorded_outputs.py results/linux-x86_64/v1.0.1 1.0.1

For each run recorded in RECORD_DIR/python<major.minor>/cases.jsonl (Linux, CPython 3.9.25 or 3.13.16), it reruns
the same pair or case through the CLI (tests/run_cases.py), replaces the one `"version": "<current>"` with
`"version": "<VERSION>"`, and compares the SHA-256 with the recorded `stdout_sha256`.
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


def main() -> int:
    record_dir, version = UNIT / sys.argv[1], sys.argv[2]
    series = '.'.join(platform.python_version_tuple()[:2])
    recorded_path = record_dir / f'python{series}' / 'cases.jsonl'
    rows = [json.loads(line) for line in recorded_path.read_text(encoding='utf-8').splitlines()[1:]]
    recorded = {row['case']: row['stdout_sha256'] for row in rows}
    current = f'"version": "{export_compare.TOOL_VERSION}"'.encode()
    same, different = 0, []
    with tempfile.TemporaryDirectory() as tmp:
        runs = {name: args for name, args, _, _ in run_cases.cli_runs(Path(tmp))}
        missing = sorted(set(recorded) - set(runs))
        for name in recorded:
            if name in missing:
                continue
            _, stdout, _ = run_cases.run_cli(runs[name])
            if 'error' not in json.loads(stdout):  # rejections carry no tool version
                assert stdout.count(current) == 1, name
                stdout = stdout.replace(current, f'"version": "{version}"'.encode())
            if hashlib.sha256(stdout).hexdigest() == recorded[name]:
                same += 1
            else:
                different.append(name)
    where = recorded_path.relative_to(UNIT)
    print(f'Python {platform.python_version()}: module {export_compare.TOOL_VERSION} against {version} {where}')
    print(
        f'{len(recorded)} recorded runs; identical apart from the version: {same}; differ: {different}; '
        f'no longer defined: {missing}'
    )
    return 0 if same == len(recorded) else 1


if __name__ == '__main__':
    sys.exit(main())
