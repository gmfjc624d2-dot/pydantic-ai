"""Show that the tests reject plausible broken variants of export_compare (standard library only).

Run: python3 tests/mutation_check.py   (from acquisition/public_export_compare_20261023)

Each mutation replaces one module or class attribute in memory, reruns the unittest suite, and must make it fail;
the failing tests are listed. Three restore the 1.0.0 behaviour that 1.0.1 corrects; the last four loosen the
bracketed-html layout of 1.1.0.
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'fixtures'))

import export_compare as ec  # noqa: E402

ORIGINAL_CLASSIFY = ec._classify_lines
ORIGINAL_SPANS = ec._protected_spans
ORIGINAL_BLOCK_LINE = ec._definition_block_line
ORIGINAL_REQUEST_ID = ec._request_id_occurrences
ORIGINAL_QUESTION = ec._check_question_region
ORIGINAL_SEPARATOR = ec._require_separator
ORIGINAL_ENTRIES = ec._entries_url_map


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


def nothing_overlaps(spans, starts, low, high):  # type: ignore[no-untyped-def]
    return False


def bytes_rebuilt_from_lines(self, first, end):  # type: ignore[no-untyped-def]
    return '\n'.join(self.lines[first:end]).encode('utf-8')


def indented_lines_end_paragraphs(name, lines):  # type: ignore[no-untyped-def]
    return ['code' if kind == 'indented' else kind for kind in ORIGINAL_CLASSIFY(name, lines)]


def question_whitespace_insensitive(doc, first, end, question):  # type: ignore[no-untyped-def]
    if doc.segment_bytes(first, end).decode('utf-8').split() != ('# ' + question).split():
        ORIGINAL_QUESTION(doc, first, end, question)


def blank_lines_accepted_as_separators(doc, index, between):  # type: ignore[no-untyped-def]
    if not (0 <= index < len(doc.lines) and not doc.lines[index].strip()):
        ORIGINAL_SEPARATOR(doc, index, between)


def only_cited_entries_compared(pb, mb, sources, definitions, hidden):  # type: ignore[no-untyped-def]
    entries = ORIGINAL_ENTRIES(pb, mb, sources, definitions, hidden)
    return [e for e in entries if e['cited_in_plain_body'] or e['cited_in_markdown_body']]


MUTATIONS = {
    'code normalized like prose': (ec, '_classify_lines', everything_is_prose),
    'URLs not protected from normalization': (ec, '_protected_spans', urls_unprotected),
    'URL comparison ignores query and case': (ec, '_same_url', url_without_query_or_case),
    'display:none span ignored (hidden flag lost)': (ec, '_definition_block_line', span_ignored),
    'request ID counted only when a question exists': (ec, '_request_id_occurrences', id_only_with_question),
    '1.0.0: table rule ignores code spans (C1)': (ec, '_overlaps', nothing_overlaps),
    '1.0.0: segment bytes rebuilt from lines (C2)': (ec._Document, 'segment_bytes', bytes_rebuilt_from_lines),
    '1.0.0: an indented line ends the paragraph': (ec, '_classify_lines', indented_lines_end_paragraphs),
    'bracketed-html: question compared ignoring whitespace': (
        ec,
        '_check_question_region',
        question_whitespace_insensitive,
    ),
    'bracketed-html: any blank lines accepted as a separator': (
        ec,
        '_require_separator',
        blank_lines_accepted_as_separators,
    ),
    'bracketed-html: hidden span may hold any text': (
        ec,
        'HIDDEN_MARKERS',
        re.compile(r'<span style="display:none">(.*)</span>'),
    ),
    'bracketed-html: uncited entries not compared': (ec, '_entries_url_map', only_cited_entries_compared),
}


def run_suite() -> unittest.TestResult:
    import test_export_compare

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_export_compare)
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


def main() -> int:
    baseline = run_suite()
    print(f'unmutated: {baseline.testsRun} tests, {len(baseline.failures) + len(baseline.errors)} failing')
    ok = baseline.wasSuccessful()
    for label, (owner, attr, replacement) in MUTATIONS.items():
        original = getattr(owner, attr)
        setattr(owner, attr, replacement)
        try:
            result = run_suite()
        finally:
            setattr(owner, attr, original)
        failing = sorted(test.id().split('.', 1)[1] for test, _ in result.failures + result.errors)
        print(f'{label}: {len(failing)} failing test(s) -> {"rejected" if failing else "NOT DETECTED"}')
        for name in failing:
            print(f'    {name}')
        ok = ok and bool(failing)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
