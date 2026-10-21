"""Compare this tool's output with the stored 1.0.0 outputs for the dev and reserved fixtures.

Usage:  python3 regression_check.py OUT_DIR [--cli-baseline-commit SHA]
        (writes OUT_DIR/regression.json; exit 1 on any unexpected difference)

Regression reproduction only, not an evaluation: the reserved items have been seen since the 1.0.0 run,
so reusing them here is not held-out evidence. Fixtures and stored results are read, never written.

For every item, the full find_cues() result is compared with each stored 1.0.0 result
(results/linux-x86_64/{dev,reserved}/python3.*/raw_results.jsonl) after removing `tool.version`,
`configuration.unicode_database_version` and `configuration_sha256`, the only fields expected to differ
(the last two vary with the running Python's Unicode database). The per-item evaluation classes are also
recomputed with evaluate.classify() and compared with the stored evaluation.json.

With --cli-baseline-commit, review_cues.py and rules_v1.json are extracted from that commit (`git show`) and
both CLIs' main() run in-process on every fixture item and on synthetic success and rejection requests,
without a budget. Their stdout bytes must be identical once the tool version and configuration_sha256 of a
successful result are mapped to the baseline's; requests in EXPECTED_DIFFERENT are reported, not failed.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import platform
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate  # noqa: E402
import review_cues  # noqa: E402
from review_cues import TOOL_VERSION, find_cues  # noqa: E402

STORED = HERE / 'results' / 'linux-x86_64'
MASKED_FIELDS = ['tool.version', 'configuration.unicode_database_version', 'configuration_sha256']
CLI_REQUESTS = {
    'empty text': json.dumps({'text': '', 'language': 'en'}).encode(),
    'no match': json.dumps({'text': 'The blue square sits next to a red circle.', 'language': 'en'}).encode(),
    'unicode and overlaps': json.dumps(
        {'text': '\U0001f4ccSegún el guía, provided\r\nthat only if no, señor', 'language': 'es+en'}
    ).encode(),
    'dense overlaps': json.dumps({'text': 'Only if ' * 2000, 'language': 'en'}).encode(),
    'invalid json': b'{"text": ',
    'duplicate key': b'{"text": "a", "text": "b", "language": "en"}',
    'long language value': json.dumps({'text': 'if', 'language': 'x' * 5000}).encode(),
    'unknown field': b'{"text": "if", "language": "en", "x": 1}',
    'long integer': b'{"text":' + b'7' * 5000 + b',"language":"en"}',
    'deep nesting': b'[' * 1100 + b'0' + b']' * 1100,
    'request too large': b' ' * (review_cues.MAX_REQUEST_BYTES + 1),
}
EXPECTED_DIFFERENT = {'invalid arguments': 'the usage message now names --max-output-bytes'}


def cli_compatibility(commit: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        for name in ('review_cues.py', 'rules_v1.json'):
            content = subprocess.run(
                ['git', '-C', str(HERE), 'show', f'{commit}:./review_cues/{name}'], capture_output=True, check=True
            ).stdout
            (Path(tmp) / name).write_bytes(content)
        spec = importlib.util.spec_from_file_location('review_cues_cli_baseline', Path(tmp) / 'review_cues.py')
        assert spec is not None and spec.loader is not None
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        cases = {
            f'fixture {item["id"]}': ([], json.dumps({'text': item['text'], 'language': item['lang']}).encode())
            for set_name in ('dev', 'reserved')
            for item in evaluate.load(set_name)
        }
        cases.update({name: ([], payload) for name, payload in CLI_REQUESTS.items()})
        cases['invalid arguments'] = (['--verbose'], b'{"text": "if", "language": "en"}')
        identical, differing = [], []
        for name, (argv, payload) in cases.items():
            runs = []
            for module in (baseline, review_cues):
                out = io.BytesIO()
                runs.append((module.main(argv, stdin=io.BytesIO(payload), stdout=out), out.getvalue()))
            (old_status, old), (new_status, new) = runs
            if old_status == new_status == 0:
                old_result, new_result = json.loads(old), json.loads(new)
                for field, old_value, new_value in (
                    ('version', old_result['tool']['version'], new_result['tool']['version']),
                    ('configuration_sha256', old_result['configuration_sha256'], new_result['configuration_sha256']),
                ):
                    new = new.replace(f'"{field}": "{new_value}"'.encode(), f'"{field}": "{old_value}"'.encode(), 1)
            (identical if (old_status, old) == (new_status, new) else differing).append(name)
    unexpected = [name for name in differing if name not in EXPECTED_DIFFERENT]
    return {
        'baseline_commit': commit,
        'baseline_tool_version': baseline.TOOL_VERSION,
        'cases': len(cases),
        'identical': len(identical),
        'differing': differing,
        'expected_differences': {name: why for name, why in EXPECTED_DIFFERENT.items() if name in differing},
        'unexpected_differences': unexpected,
    }


def masked(result: Dict[str, Any]) -> str:
    r = copy.deepcopy(result)
    del r['tool']['version'], r['configuration']['unicode_database_version'], r['configuration_sha256']
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


def main() -> int:
    out = Path(sys.argv[1])
    report: Dict[str, Any] = {
        'kind': 'regression reproduction of stored 1.0.0 outputs (not a held-out evaluation)',
        'tool_version': TOOL_VERSION,
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'unicode_database_version': unicodedata.unidata_version,
        'masked_fields': MASKED_FIELDS,
        'sets': {},
    }
    ok = True
    for set_name in ('dev', 'reserved'):
        items = evaluate.load(set_name)  # refuses fixtures whose hash differs from the recorded one
        results = [find_cues(item['text'], item['lang']) for item in items]
        for ref_dir in sorted((STORED / set_name).glob('python3.*')):
            stored = [
                json.loads(line) for line in (ref_dir / 'raw_results.jsonl').read_text(encoding='utf-8').splitlines()
            ]
            stored_eval = json.loads((ref_dir / 'evaluation.json').read_text(encoding='utf-8'))
            differing = [
                item['id']
                for item, result, ref in zip(items, results, stored)
                if ref['item_id'] != item['id'] or masked(result) != masked(ref['result'])
            ]
            eval_differing = [
                item['id']
                for item, result, ref in zip(items, results, stored_eval['per_item'])
                if evaluate.classify(item, result) != ref
            ]
            same_unicode = (
                stored[0]['result']['configuration']['unicode_database_version'] == unicodedata.unidata_version
            )
            report['sets'][f'{set_name}/{ref_dir.name}'] = {
                'items': len(items),
                'stored_items': len(stored),
                'items_with_identical_masked_output': len(items) - len(differing),
                'items_differing': differing,
                'items_with_identical_evaluation_classes': len(items) - len(eval_differing),
                'evaluation_items_differing': eval_differing,
                'stored_unicode_database_version': stored[0]['result']['configuration']['unicode_database_version'],
                'stored_tool_version': stored[0]['result']['tool']['version'],
                'unmasked_configuration_identical': same_unicode
                and all(r['configuration'] == s['result']['configuration'] for r, s in zip(results, stored)),
            }
            ok = ok and len(stored) == len(items) and not differing and not eval_differing
        report['sets'][set_name] = {
            'results_sha256': hashlib.sha256(
                '\n'.join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in results).encode('utf-8')
            ).hexdigest()
        }
    report['all_identical'] = ok
    if sys.argv[2:3] == ['--cli-baseline-commit']:
        report['cli_compatibility'] = cli_compatibility(sys.argv[3])
        ok = ok and not report['cli_compatibility']['unexpected_differences']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'regression.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
