"""Show that the contract tests reject deliberately broken implementations (standard library only).

Run: python3 tests/mutation_check.py   (from acquisition/public_review_cues_20261020)

Each mutation patches one behavior in memory, reruns the unittest suite, and must produce failures.
"""

from __future__ import annotations

import bisect
import decimal
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'review_cues'))
sys.path.insert(0, str(ROOT / 'tests'))

import review_cues  # noqa: E402

ORIGINAL_BOUNDARY = review_cues._boundary_ok
ORIGINAL_FIND = review_cues.find_cues
ORIGINAL_READ = review_cues.read_request


def no_boundaries(text, start, end, boundary):  # type: ignore[no-untyped-def]
    return True


def ignore_marks(text, start, end, boundary):  # type: ignore[no-untyped-def]
    if end < len(text) and review_cues._is_word(text[end]):
        return False
    host = start > 0 and review_cues._is_word(text[start - 1])
    return host if boundary == 'suffix' else not host


def bytes_equal_codepoints(text, language, ruleset=None):  # type: ignore[no-untyped-def]
    result = ORIGINAL_FIND(text, language, ruleset)
    for m in result['matches']:
        m['byte_start'], m['byte_end'] = m['start'], m['end']
    return result


def stripped_text(text, language, ruleset=None):  # type: ignore[no-untyped-def]
    result = ORIGINAL_FIND(text, language, ruleset)
    for m in result['matches']:
        m['text'] = ' '.join(m['text'].split())
    return result


def accepts_surrogates(text, language, ruleset=None):  # type: ignore[no-untyped-def]
    if isinstance(text, str):
        text = text.encode('utf-8', 'replace').decode('utf-8')
    return ORIGINAL_FIND(text, language, ruleset)


def later_overlaps_only(spans):  # type: ignore[no-untyped-def]
    starts = [s for s, _ in spans]
    return [list(range(i + 1, bisect.bisect_left(starts, end, i + 1))) for i, (_, end) in enumerate(spans)]


def touching_spans_overlap(spans):  # type: ignore[no-untyped-def]
    starts = [s for s, _ in spans]
    lists = [[] for _ in spans]
    for i, (_, end) in enumerate(spans):
        later = range(i + 1, bisect.bisect_right(starts, end, i + 1))  # start_j <= end_i instead of <
        for j in later:
            lists[j].append(i)
        lists[i].extend(later)
    return lists


def unsized_read(stream, limit=review_cues.MAX_REQUEST_BYTES):  # type: ignore[no-untyped-def]
    raw = stream.read()
    if len(raw) > limit:
        raise review_cues.CueInputError('request_too_large', 'too large')
    return raw


def limit_off_by_one(stream, limit=review_cues.MAX_REQUEST_BYTES):  # type: ignore[no-untyped-def]
    return ORIGINAL_READ(stream, limit + 1)


def no_nesting_limit(decoded):  # type: ignore[no-untyped-def]
    return None


def decimal_only_after_int_fails(literal):  # type: ignore[no-untyped-def]
    try:
        return int(literal)
    except ValueError:
        return decimal.Decimal(literal)


MUTATIONS = {
    'no token boundaries': ('_boundary_ok', no_boundaries),
    'combining marks ignored at boundaries': ('_boundary_ok', ignore_marks),
    'byte offsets equal code-point offsets': ('find_cues', bytes_equal_codepoints),
    'returned substring whitespace-normalized': ('find_cues', stripped_text),
    'lone surrogates silently replaced': ('find_cues', accepts_surrogates),
    'overlaps with earlier matches omitted': ('_overlap_lists', later_overlaps_only),
    'touching spans reported as overlapping': ('_overlap_lists', touching_spans_overlap),
    'request read without a size': ('read_request', unsized_read),
    'request byte limit off by one': ('read_request', limit_off_by_one),
    'no JSON nesting limit': ('_reject_deep_nesting', no_nesting_limit),
    'JSON integers parsed with int() only': ('_parse_int', int),
    'digit threshold applied only after int() fails': ('_parse_int', decimal_only_after_int_fails),
}


def run_suite() -> unittest.TestResult:
    import test_review_cues

    for name in ('find_cues', '_overlap_lists'):
        setattr(test_review_cues, name, getattr(review_cues, name))
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_review_cues)
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


def main() -> int:
    baseline = run_suite()
    print(f'unmutated: {baseline.testsRun} tests, {len(baseline.failures) + len(baseline.errors)} failing')
    ok = baseline.wasSuccessful()
    for label, (attr, replacement) in MUTATIONS.items():
        original = getattr(review_cues, attr)
        setattr(review_cues, attr, replacement)
        try:
            result = run_suite()
        finally:
            setattr(review_cues, attr, original)
        failing = len(result.failures) + len(result.errors)
        print(f'{label}: {failing} failing test(s) -> {"rejected" if failing else "NOT DETECTED"}')
        ok = ok and failing > 0
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
