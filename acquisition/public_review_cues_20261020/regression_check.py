"""Compare this tool's output with the stored 1.0.0 outputs for the dev and reserved fixtures.

Usage:  python3 regression_check.py OUT_DIR     (writes OUT_DIR/regression.json; exit 1 on any difference)

Regression reproduction only, not an evaluation: the reserved items have been seen since the 1.0.0 run,
so reusing them here is not held-out evidence. Fixtures and stored results are read, never written.

For every item, the full find_cues() result is compared with each stored 1.0.0 result
(results/linux-x86_64/{dev,reserved}/python3.*/raw_results.jsonl) after removing `tool.version`,
`configuration.unicode_database_version` and `configuration_sha256`, the only fields expected to differ
(the last two vary with the running Python's Unicode database). The per-item evaluation classes are also
recomputed with evaluate.classify() and compared with the stored evaluation.json.
"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate  # noqa: E402
from review_cues import TOOL_VERSION, find_cues  # noqa: E402

STORED = HERE / 'results' / 'linux-x86_64'
MASKED_FIELDS = ['tool.version', 'configuration.unicode_database_version', 'configuration_sha256']


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
    out.mkdir(parents=True, exist_ok=True)
    (out / 'regression.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
