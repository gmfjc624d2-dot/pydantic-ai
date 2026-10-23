"""Show that the tests reject plausible broken variants of export_compare (standard library only).

Run: python3 tests/mutation_check.py   (from acquisition/public_export_compare_20261023)

Each mutation replaces one module attribute in memory, reruns the unittest suite, and must make it fail.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'fixtures'))

import export_compare as ec  # noqa: E402

ORIGINAL_SPANS = ec._protected_spans
ORIGINAL_BLOCK_LINE = ec._definition_block_line
ORIGINAL_REQUEST_ID = ec._request_id_occurrences


def everything_is_prose(name, lines):  # type: ignore[no-untyped-def]
    return ['text'] * len(lines)


def urls_unprotected(text):  # type: ignore[no-untyped-def]
    return [s for s in ORIGINAL_SPANS(text) if not text[s[0] :].startswith(('http://', 'https://'))]


def url_without_query_or_case(a, b):  # type: ignore[no-untyped-def]
    return a is not None and b is not None and a.split('?')[0].lower() == b.split('?')[0].lower()


def span_ignored(line):  # type: ignore[no-untyped-def]
    parsed = ORIGINAL_BLOCK_LINE(line)
    return None if parsed is None else (False, parsed[1], False)


def id_only_with_question(request_id, question, p, pl, m, ml):  # type: ignore[no-untyped-def]
    result = ORIGINAL_REQUEST_ID(request_id, question, p, pl, m, ml)
    if question is None and pl['preamble'][1] == 0:  # "no question, so no ID": the mistake this guards against
        for key in ('plain_document', 'plain_body', 'plain_sources'):
            result['occurrences'][key] = 0
        result['present_in_plain_document'] = result['present_in_plain_body'] = False
    return result


MUTATIONS = {
    'code normalized like prose': ('_classify_lines', everything_is_prose),
    'URLs not protected from normalization': ('_protected_spans', urls_unprotected),
    'URL comparison ignores query and case': ('_same_url', url_without_query_or_case),
    'display:none span ignored (hidden flag lost)': ('_definition_block_line', span_ignored),
    'request ID counted only when a question exists': ('_request_id_occurrences', id_only_with_question),
}


def run_suite() -> unittest.TestResult:
    import test_export_compare

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_export_compare)
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


def main() -> int:
    baseline = run_suite()
    print(f'unmutated: {baseline.testsRun} tests, {len(baseline.failures) + len(baseline.errors)} failing')
    ok = baseline.wasSuccessful()
    for label, (attr, replacement) in MUTATIONS.items():
        original = getattr(ec, attr)
        setattr(ec, attr, replacement)
        try:
            result = run_suite()
        finally:
            setattr(ec, attr, original)
        failing = len(result.failures) + len(result.errors)
        print(f'{label}: {failing} failing test(s) -> {"rejected" if failing else "NOT DETECTED"}')
        ok = ok and failing > 0
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
