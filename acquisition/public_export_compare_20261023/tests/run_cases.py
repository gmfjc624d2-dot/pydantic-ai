"""Run the fixture pairs and every adversarial case through the real CLI, and time worst-case input shapes.

Usage (from acquisition/public_export_compare_20261023):  python3 tests/run_cases.py OUT_DIR

Writes, for the running interpreter:
- OUT_DIR/cases.jsonl: per run (positive pairs, single-edit cases, bracketed-html cases, then the 1.0.1
  regression pairs), the exit status, stdout/stderr byte counts, the stdout SHA-256, whether the exit status
  was the expected one, and the error code or key result fields;
- OUT_DIR/cases.md: what a reader sees for each case;
- OUT_DIR/positive_<pair>.json: full results of the positive pairs;
- OUT_DIR/timings.jsonl: worst-case shapes, one subprocess each, 120 s timeout.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'export_compare.py'
FIXTURES = ROOT / 'fixtures'
sys.path.insert(0, str(FIXTURES))
import cases  # noqa: E402

POSITIVE = {
    'full': (
        'full_plain.txt',
        'full_markdown.md',
        ['--question-file', str(FIXTURES / 'full_question.txt'), '--request-id', 'req-20261023-0001'],
    ),
    'minimal': ('minimal_plain.txt', 'minimal_markdown.md', []),
    'id_in_body': ('id_in_body_plain.txt', 'id_in_body_markdown.md', ['--request-id', 'public-example-1']),
    'bracketed_html': (
        'bracketed_html_plain.txt',
        'bracketed_html_markdown.md',
        ['--layout', 'bracketed-html', '--question-file', str(FIXTURES / 'bracketed_html_question.txt')]
        + ['--markdown-body-start', '7', '--request-id', 'public-layout-2'],
    ),
}
TIMING_SHAPES = {
    'all_lines_differ_2000': (
        "''.join(f'{i} plain {\"a\" * 100}\\n' for i in range(1, 1990))",
        "''.join(f'{i} markdown {\"b\" * 100}\\n' for i in range(1, 1990))",
    ),
    'repeated_identical_lines_sparse_changes': (
        "''.join('same line[1].\\n' if i % 97 else f'changed {i}[1].\\n' for i in range(1, 1990))",
        "''.join('same line[^1].\\n' if i % 89 else f'other {i}[^1].\\n' for i in range(1, 1990))",
    ),
    'one_long_line_one_char_differs': (
        "'a' * 220000 + 'X[1]\\n'",
        "'a' * 220000 + 'Y[^1]\\n'",
    ),
    'many_markers': (
        "'[1]' * 60000 + '\\n'",
        "'[^1]' * 50000 + '\\n'",
    ),
    'many_backtick_runs': (
        "''.join('`' * (i % 7 + 1) + 'x[1] ' for i in range(20000)) + '\\n'",
        "''.join('`' * (i % 7 + 1) + 'x[^1] ' for i in range(20000)) + '\\n'",
    ),
}
TIMING_WORKER = """
import json, sys, time
sys.path.insert(0, sys.argv[1])
import export_compare as ec
body_p, body_m = eval(sys.argv[2]), eval(sys.argv[3])
plain = (body_p + '\\nSources\\n1. Guide https://example.org/a\\n').encode()
markdown = (body_m + '\\n[^1]: https://example.org/a\\n').encode()
started = time.perf_counter()
try:
    result = ec.compare_exports(plain, markdown)
    row = {'outcome': 'compared', 'differences': result['results']['body_difference_count'],
           'output_bytes': len(json.dumps(result, ensure_ascii=False, indent=2).encode()) + 1}
except ec.CompareError as e:
    row = {'outcome': e.code}
row.update(seconds=time.perf_counter() - started, plain_bytes=len(plain), markdown_bytes=len(markdown))
print(json.dumps(row))
"""


def run_cli(args, cwd=None):
    proc = subprocess.run(
        [sys.executable, '-I', str(SCRIPT), *args], capture_output=True, timeout=120, check=False, cwd=cwd
    )
    return proc.returncode, proc.stdout, proc.stderr


def cli_runs(directory: Path) -> Iterator[Tuple[str, List[str], int, str]]:
    """(name, CLI arguments, expected exit status, what was changed) for every pair and case, inputs in directory."""
    for name, (plain, markdown, extra) in POSITIVE.items():
        yield (
            f'positive:{name}',
            ['--plain', str(FIXTURES / plain), '--markdown', str(FIXTURES / markdown), *extra],
            0,
            '',
        )
    for case in cases.CASES + cases.FRAMED_CASES:
        plain, markdown, options = cases.apply_case(case)
        args = cases.write_cli_inputs(directory, case['id'], plain, markdown, options)
        change = case.get('edit', case.get('edits', case.get('special', case.get('options'))))
        yield case['id'], args, case['expect']['exit'], f'Edit: `{change!r}`'
    for name, pair in cases.REGRESSIONS.items():
        args = cases.write_cli_inputs(directory, name, pair['plain'], pair['markdown'], {})
        yield (
            f'regression:{name}',
            args,
            pair['expect']['exit'],
            f'Plain: `{pair["plain"]!r}`\n\nMarkdown: `{pair["markdown"]!r}`',
        )


def summary(stdout: bytes):
    document = json.loads(stdout)
    if 'error' in document:
        return document, {'error': document['error']['code']}
    r = document['results']
    c = r['citations']
    return document, {
        'raw_documents_equal': r['raw_documents_equal'],
        'raw_bodies_equal': r['raw_bodies_equal'],
        'normalized_bodies_equal': r['normalized_bodies_equal'],
        'body_difference_count': r['body_difference_count'],
        'url_map_equal': c['url_map_equal'],
        'all_entries_url_map_equal': c['all_entries_url_map_equal'],
        'reference_counts_equal': c['reference_counts_equal'],
        'request_id_present_in_plain_body': None
        if r['request_id'] is None
        else r['request_id']['present_in_plain_body'],
        'semantic_judgment': r['semantic_judgment'],
        'producer_authenticity': r['producer_authenticity'],
        'warnings': [w['code'] for w in document['warnings']],
    }


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rows, md = [], [f'# Cases through the CLI (Python {platform.python_version()}, {platform.platform()})', '']
    with tempfile.TemporaryDirectory() as tmp:
        for name, args, expected, change in cli_runs(Path(tmp)):
            status, stdout, stderr = run_cli(args)
            document, fields = summary(stdout)
            if name.startswith('positive:'):
                (out / f'positive_{name.split(":", 1)[1]}.json').write_bytes(stdout)
            rows.append(
                {
                    'case': name,
                    'exit': status,
                    'expected_exit': expected,
                    'stdout_bytes': len(stdout),
                    'stderr_bytes': len(stderr),
                    'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                    **fields,
                }
            )
            md += [f'## {name} (exit {status}, expected {expected})', '']
            md += [change, ''] if change else []
            md += ['```', cases.describe(document), '```', '']
    with (out / 'cases.jsonl').open('w', encoding='utf-8') as f:
        f.write(json.dumps({'python': platform.python_version(), 'platform': platform.platform()}) + '\n')
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    (out / 'cases.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    with (out / 'timings.jsonl').open('w', encoding='utf-8') as f:
        for name, (body_p, body_m) in TIMING_SHAPES.items():
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    [sys.executable, '-I', '-c', TIMING_WORKER, str(ROOT), body_p, body_m],
                    capture_output=True,
                    timeout=120,
                    check=True,
                )
                row = {'shape': name, **json.loads(proc.stdout)}
            except subprocess.TimeoutExpired:
                row = {'shape': name, 'outcome': 'timeout (> 120 s)'}
            row['process_seconds'] = time.perf_counter() - started
            f.write(json.dumps(row) + '\n')
            print(json.dumps(row))
    mismatched = [r['case'] for r in rows if r['exit'] != r['expected_exit'] or r['stderr_bytes']]
    print(f'{len(rows)} CLI runs; unexpected exit status or stderr output: {mismatched}')


if __name__ == '__main__':
    main()
