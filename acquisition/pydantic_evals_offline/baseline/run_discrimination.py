"""Run the pytest/Hypothesis baseline once per implementation and record which tests reject it.

Usage (from the directory containing pytest.ini): python baseline/run_discrimination.py OUT_DIR

Writes one JUnit XML per implementation (pytest's own neutral report format) and
`discrimination.json` with the failing test ids, plus the shrunk Hypothesis counterexample lines.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worker'))

from scenarios import SCENARIOS
from synthetic_worker import IMPLEMENTATIONS


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {}
    for impl in IMPLEMENTATIONS:
        junit = out / f'junit--{impl}.xml'
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', '-q', f'--junitxml={junit}'],
            env={**os.environ, 'WORKER_IMPL': impl},
            capture_output=True,
            text=True,
            timeout=1800,
        )
        root = ET.parse(junit).getroot()
        failing: list[str] = []
        counterexamples: list[str] = []
        for case in root.iter('testcase'):
            failure = case.find('failure')
            if failure is None:
                continue
            failing.append(case.get('name', '?'))
            text = failure.text or ''
            lines = [line.strip().removeprefix('E').strip() for line in text.splitlines()]
            counterexamples += [line for line in lines if line.startswith(('state.', 'values=', 'key='))]
        suite = root.find('testsuite') if root.tag == 'testsuites' else root
        assert suite is not None
        scenario_failures = sorted(
            {name.split('[', 1)[1].rsplit('-', 1)[0] for name in failing if name.startswith('test_scenario[')}
        )
        summary[impl] = {
            'exit_code': proc.returncode,
            'tests': int(suite.get('tests', 0)),
            'failures': int(suite.get('failures', 0)),
            'seconds': float(suite.get('time', 0)),
            'rejected': proc.returncode != 0,
            'failing_tests': failing,
            'failing_scenarios': scenario_failures,
            'designed_to_be_caught_by_scenarios': sorted(s.id for s in SCENARIOS if impl in s.catches),
            'hypothesis_counterexample_lines': counterexamples[:12],
        }
        print(impl, 'rejected' if proc.returncode else 'accepted', failing)
    (out / 'discrimination.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
