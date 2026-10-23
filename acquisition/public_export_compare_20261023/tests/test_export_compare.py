"""Tests for export_compare (unittest, standard library only, Python >= 3.9).

Run: python3 -m unittest discover -s tests -v   (from acquisition/public_export_compare_20261023)

Operation public-export-comparison-20261023-01; base commit ed6e9b152beeb3a6a9f1c2f419fda940318ca554 on
claude/sweet-carson-tjohp1. Synthetic, public example.org material only. Assertions are about observable
outcomes on fixture pairs (fields a reader relies on and the readable difference they see), not about how the
module computes them; tests/mutation_check.py shows that these tests reject broken variants.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / 'fixtures'
SCRIPT = ROOT / 'export_compare.py'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(FIXTURES))

import cases  # noqa: E402
import export_compare as ec  # noqa: E402

OPERATION = 'public-export-comparison-20261023-01'
BASE_COMMIT = 'ed6e9b152beeb3a6a9f1c2f419fda940318ca554'


def full_pair():
    return (FIXTURES / 'full_plain.txt').read_bytes(), (FIXTURES / 'full_markdown.md').read_bytes()


def compare(plain: bytes, markdown: bytes, **options):
    try:
        return ec.compare_exports(plain, markdown, **options)
    except ec.CompareError as e:
        return ec._error_document(e)


def full_result():
    plain, markdown = full_pair()
    question = (FIXTURES / 'full_question.txt').read_text(encoding='utf-8').rstrip('\n')
    return ec.compare_exports(plain, markdown, question=question, request_id='req-20261023-0001')


class KnownLayouts(unittest.TestCase):
    def test_full_pair_agrees_only_where_the_policy_says(self) -> None:
        result = full_result()
        r, c = result['results'], result['results']['citations']
        self.assertEqual(
            (r['raw_documents_equal'], r['raw_bodies_equal'], r['normalized_bodies_equal']), (False, False, True)
        )
        self.assertEqual(r['semantic_judgment'], 'NOT_ESTABLISHED')
        self.assertIn('producer authenticity', result['not_established'])
        self.assertEqual(r['producer_authenticity'], 'NOT_ESTABLISHED')
        self.assertIn('question identity', result['not_established'])
        # body citations: [1] four times, [2] four times, [3] once; markers inside code and the URL are not citations
        self.assertEqual(
            [(e['id'], e['plain_references'], e['markdown_references'], e['equal']) for e in c['url_map']],
            [(1, 4, 4, True), (2, 4, 4, True), (3, 1, 1, True)],
        )
        self.assertTrue(c['url_map_equal'] and c['referenced_ids_equal'] and c['reference_counts_equal'])
        # listed or defined but uncited entries stay distinguishable, with their hidden flag and titles
        self.assertEqual(
            c['plain_listed_not_cited'],
            [{'id': 4, 'title': 'Archived background page', 'url': 'https://example.org/archive/background'}],
        )
        self.assertEqual([(e['id'], e['hidden']) for e in c['markdown_defined_not_referenced']], [(4, True), (5, True)])
        self.assertFalse(c['all_entries_url_map_equal'])  # [^5] exists only in the Markdown export
        self.assertEqual([d['hidden'] for d in c['markdown_definitions']], [False, False, False, True, True])
        self.assertEqual(
            [s['title'] for s in c['plain_sources']][:2], ['Verification guide', 'Permission model overview']
        )
        codes = [w['code'] for w in result['warnings']]
        self.assertIn('source_titles_only_in_plain', codes)
        self.assertIn('uncited_entries', codes)
        self.assertIn('markers_in_code_not_counted', codes)

    def test_question_and_request_id_are_separate_fields(self) -> None:
        result = full_result()
        q, rid = result['results']['question'], result['results']['request_id']
        self.assertEqual(q['plain']['source'], 'supplied')
        self.assertEqual(
            q['markdown']['text'],
            'Which conditions apply before running the export check? Request ID: req-20261023-0001',
        )
        self.assertFalse(q['supplied_equals_markdown_heading'])  # the heading carries the request ID; the copy does not
        self.assertEqual(
            rid['occurrences'],
            {
                'plain_document': 0,
                'plain_preamble': 0,
                'plain_body': 0,
                'plain_sources': 0,
                'markdown_document': 1,
                'markdown_prelude': 1,
                'markdown_question_heading': 1,
                'markdown_body': 0,
                'markdown_definitions': 0,
                'supplied_question': 0,
            },
        )
        self.assertEqual(result['results']['producer_authenticity'], 'NOT_ESTABLISHED')
        plain, markdown = full_pair()
        bare = ec.compare_exports(plain, markdown)['results']
        self.assertEqual(
            (
                bare['question']['plain']['source'],
                bare['question']['supplied_equals_markdown_heading'],
                bare['request_id'],
            ),
            ('absent', None, None),
        )

    def test_missing_question_does_not_hide_an_id_in_the_body(self) -> None:
        plain = (FIXTURES / 'id_in_body_plain.txt').read_bytes()
        markdown = (FIXTURES / 'id_in_body_markdown.md').read_bytes()
        result = ec.compare_exports(plain, markdown, request_id='public-example-1')
        r = result['results']
        self.assertTrue(r['normalized_bodies_equal'] and r['citations']['url_map_equal'])
        self.assertEqual((r['question']['plain']['source'], r['question']['markdown']['source']), ('absent', 'heading'))
        rid = r['request_id']
        self.assertEqual(
            rid['occurrences'],
            {
                'plain_document': 1,
                'plain_preamble': 0,
                'plain_body': 1,
                'plain_sources': 0,
                'markdown_document': 2,
                'markdown_prelude': 1,
                'markdown_question_heading': 1,
                'markdown_body': 1,
                'markdown_definitions': 0,
                'supplied_question': 0,
            },
        )
        self.assertTrue(
            rid['present_in_plain_body'] and rid['present_in_plain_document']
        )  # no question, ID still present
        self.assertTrue(rid['present_in_markdown_body'] and rid['present_in_markdown_question_heading'])
        self.assertEqual((r['semantic_judgment'], r['producer_authenticity']), ('NOT_ESTABLISHED', 'NOT_ESTABLISHED'))
        self.assertIn('question_absent', [w['code'] for w in result['warnings']])
        for name, raw in (('plain', plain), ('markdown', markdown)):  # region counts partition the document count
            regions = [
                k
                for k in rid['occurrences']
                if k.startswith(name) and not k.endswith('document') and k != 'markdown_question_heading'
            ]
            self.assertEqual(sum(rid['occurrences'][k] for k in regions), raw.count(b'public-example-1'))
        removed = ec.compare_exports(
            plain.replace(b'Request public-example-1: run', b'Run'), markdown, request_id='public-example-1'
        )
        self.assertEqual(removed['results']['request_id']['occurrences']['plain_body'], 0)
        self.assertFalse(removed['results']['normalized_bodies_equal'])

    def test_segments_partition_each_input_exactly(self) -> None:
        plain, markdown = full_pair()
        result = ec.compare_exports(plain, markdown)
        for raw, name in ((plain, 'plain'), (markdown, 'markdown')):
            segments = result['layouts'][name]['segments']
            self.assertEqual(segments[0]['byte_start'], 0)
            self.assertEqual(segments[-1]['byte_end'], len(raw))
            for before, after in zip(segments, segments[1:]):
                self.assertEqual(before['byte_end'], after['byte_start'])
            for s in segments:
                self.assertEqual(s['sha256'], hashlib.sha256(raw[s['byte_start'] : s['byte_end']]).hexdigest())
            self.assertEqual(result['inputs'][name]['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(
            [s['name'] for s in result['layouts']['markdown']['segments']], ['prelude', 'body', 'definitions']
        )
        self.assertEqual(result['layouts']['markdown']['segments'][0]['question_line'], 3)

    def test_explicit_boundaries_equal_to_the_recognized_ones_change_nothing(self) -> None:
        plain, markdown = full_pair()
        auto = ec.compare_exports(plain, markdown)
        explicit = ec.compare_exports(
            plain,
            markdown,
            plain_body_start=1,
            plain_sources_line=24,
            markdown_body_start=4,
            markdown_definitions_start=29,
        )
        auto['layouts'].pop('boundaries')
        explicit['layouts'].pop('boundaries')
        self.assertEqual(auto, explicit)

    def test_minimal_pair_without_any_question(self) -> None:
        plain = (FIXTURES / 'minimal_plain.txt').read_bytes()
        markdown = (FIXTURES / 'minimal_markdown.md').read_bytes()
        result = ec.compare_exports(plain, markdown)
        self.assertTrue(
            result['results']['normalized_bodies_equal'] and result['results']['citations']['url_map_equal']
        )
        self.assertEqual(result['results']['question']['markdown']['source'], 'absent')
        self.assertIn('question_absent', [w['code'] for w in result['warnings']])


class AdversarialCases(unittest.TestCase):
    def test_every_case_reports_what_a_reader_must_see(self) -> None:
        self.assertGreaterEqual(len(cases.CASES), 30)
        for case in cases.CASES:
            with self.subTest(case=case['id']):
                plain, markdown, options = cases.apply_case(case)
                result = compare(plain, markdown, **options)
                expect = case['expect']
                if 'error' in expect:
                    self.assertEqual(result.get('error', {}).get('code'), expect['error'])
                    continue
                self.assertNotIn('error', result)
                r, c = result['results'], result['results']['citations']
                self.assertEqual(r['semantic_judgment'], 'NOT_ESTABLISHED')
                for key in ('normalized_bodies_equal',):
                    if key in expect:
                        self.assertEqual(r[key], expect[key])
                for key in (
                    'url_map_equal',
                    'referenced_ids_equal',
                    'reference_counts_equal',
                    'all_entries_url_map_equal',
                ):
                    if key in expect:
                        self.assertEqual(c[key], expect[key], key)
                text = cases.describe(result)
                for shown in expect.get('shows', []):
                    self.assertIn(shown, text)

    def test_rejections_name_the_place(self) -> None:
        plain, markdown, _ = cases.apply_case(next(c for c in cases.CASES if c['id'] == 'ambiguous_sources_boundary'))
        error = compare(plain, markdown)['error']
        self.assertEqual(error['lines'], [10, 26])
        plain, markdown, _ = cases.apply_case(next(c for c in cases.CASES if c['id'] == 'duplicate_definition'))
        error = compare(plain, markdown)['error']
        self.assertEqual(
            (error['id'], error['urls']),
            (1, ['https://example.org/guide/verify?version=1', 'https://example.org/elsewhere']),
        )
        plain, markdown, _ = cases.apply_case(next(c for c in cases.CASES if c['id'] == 'sources_heading_variant'))
        self.assertEqual(compare(plain, markdown)['error']['near_miss_lines'], [24])


def cli_status(plain: bytes, markdown: bytes) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / 'p.txt').write_bytes(plain)
        (Path(tmp) / 'm.md').write_bytes(markdown)
        return ec.main(
            ['--plain', str(Path(tmp) / 'p.txt'), '--markdown', str(Path(tmp) / 'm.md')], stdout=io.BytesIO()
        )


class Corrections(unittest.TestCase):
    """1.0.1: code-span protection holds through every rule (C1 and siblings); raw body equality is exact (C2)."""

    def test_regression_pairs_report_what_a_reader_must_see(self) -> None:
        for name, pair in cases.REGRESSIONS.items():
            with self.subTest(case=name):
                expect = pair['expect']
                result = ec.compare_exports(pair['plain'], pair['markdown'])
                r, counts = result['results'], result['normalization']['counts']
                self.assertEqual(cli_status(pair['plain'], pair['markdown']), expect['exit'])
                self.assertEqual(r['normalized_bodies_equal'], expect['normalized_bodies_equal'])
                if 'raw_bodies_equal' in expect:
                    self.assertEqual(r['raw_bodies_equal'], expect['raw_bodies_equal'])
                if 'table_separator_rows' in expect:
                    rows = [counts[side]['table_separator_rows'] for side in ('plain', 'markdown')]
                    self.assertEqual(rows, expect['table_separator_rows'])
                if 'referenced_ids' in expect:
                    self.assertEqual([e['id'] for e in r['citations']['url_map']], expect['referenced_ids'])
                text = cases.describe(result)
                for shown in expect.get('shows', []):
                    self.assertIn(shown, text)

    def test_rows_inside_a_code_span_are_never_a_table(self) -> None:
        # The same table rows with code spans that open or close at different places; {} is the delimiter row.
        layouts = {
            'span opens before the header': ('x `y\n| a | b |\n{}\n| c | d |\nz` w.', False),
            'span opens in the header': ('| `a | b |\n{}\n| c` | d |', False),
            'span closes in the header': ('x `y\n| a` | b |\n{}\n| c | d |', False),
            'span closed before the header': ('x `y` z\n| a | b |\n{}\n| c | d |', True),
            'span inside a header cell': ('| `a` | b |\n{}\n| c | d |', True),
        }
        for name, (template, table) in layouts.items():
            with self.subTest(layout=name):
                plain = template.format('| --- | --- |').encode() + cases.SOURCES_TAIL
                markdown = template.format('|---|---|').encode() + cases.DEFINITION_TAIL
                result = ec.compare_exports(plain, markdown)
                self.assertEqual(result['results']['normalized_bodies_equal'], table)
                if not table:
                    self.assertIn("plain: '| --- | --- |' | markdown: '|---|---|'", cases.describe(result))

    def test_raw_bodies_equal_is_equality_of_the_reported_body_bytes(self) -> None:
        pairs = [(*cases.base_pair(), {})] + [(p['plain'], p['markdown'], {}) for p in cases.REGRESSIONS.values()]
        pairs += [cases.apply_case(case) for case in cases.CASES + cases.FRAMED_CASES if 'error' not in case['expect']]
        for plain, markdown, options in pairs:
            result = compare(plain, markdown, **options)
            if 'error' in result:
                continue
            bodies = []
            for side, raw in (('plain', plain), ('markdown', markdown)):
                segment = next(s for s in result['layouts'][side]['segments'] if s['name'] == 'body')
                body = raw[segment['byte_start'] : segment['byte_end']]
                self.assertEqual(hashlib.sha256(body).hexdigest(), segment['sha256'])
                bodies.append(body)
            self.assertEqual(result['results']['raw_bodies_equal'], bodies[0] == bodies[1])


class BracketedHtmlLayout(unittest.TestCase):
    """1.1.0: the explicitly selected layout pair bracketed-html, on the requester's synthetic sample pair."""

    def test_sample_pair_keeps_every_field_separate(self) -> None:
        plain, markdown, options = cases.apply_framed_case({'id': 'framed_sample'})
        result = ec.compare_exports(plain, markdown, **options)
        layouts, r, c = result['layouts'], result['results'], result['results']['citations']
        self.assertEqual(
            (layouts['plain']['layout'], layouts['markdown']['layout'], layouts['markdown']['logo_url']),
            ('plain-bracketed-sources/1', 'markdown-html-framed/1', 'https://example.org/logo.png'),
        )
        for side, raw in (('plain', plain), ('markdown', markdown)):  # every byte in exactly one named segment
            segments = layouts[side]['segments']
            self.assertEqual(b''.join(raw[s['byte_start'] : s['byte_end']] for s in segments), raw)
            self.assertEqual([s['byte_start'] for s in segments[1:]], [s['byte_end'] for s in segments[:-1]])
            for s in segments:
                self.assertEqual(hashlib.sha256(raw[s['byte_start'] : s['byte_end']]).hexdigest(), s['sha256'])
        self.assertEqual(
            [(s['name'], s['first_line'], s['last_line']) for s in layouts['markdown']['segments']],
            [
                ('logo', 1, 1),
                ('separator_after_logo', 2, 2),
                ('question', 3, 5),
                ('separator_after_question', 6, 6),
                ('body', 7, 13),
                ('separator_before_hidden_markers', 14, 14),
                ('hidden_markers', 15, 15),
                ('separator_before_ornament', 16, 16),
                ('ornament', 17, 17),
                ('separator_before_definitions', 18, 18),
                ('definitions', 19, 21),
            ],
        )
        self.assertEqual(layouts['markdown']['segments'][-1]['separator_lines'], [20])
        self.assertEqual(
            [(s['name'], s['first_line'], s['last_line']) for s in layouts['plain']['segments']],
            [('body', 1, 7), ('separator_before_sources', 8, 8), ('sources', 9, 11)],
        )
        self.assertEqual((r['raw_bodies_equal'], r['normalized_bodies_equal']), (False, True))
        self.assertEqual([e['id'] for e in c['url_map']], [1])  # the body cites 1 only
        self.assertEqual(
            [(e['id'], e['equal'], e['cited_in_markdown_body'], e['hidden_marker']) for e in c['entries_url_map']],
            [(1, True, True, False), (2, True, False, True)],
        )
        self.assertEqual(c['hidden_markers'], {'line': 15, 'ids': [2], 'cited_in_markdown_body': []})
        self.assertEqual([(s['id'], s['title']) for s in c['plain_sources']], [(1, 'Guide'), (2, 'Extra')])
        question = r['question']
        self.assertEqual(question['supplied']['text'], cases.framed_question())
        self.assertEqual((question['plain']['region'], question['plain']['literal_occurrences']), (None, 0))
        region = question['markdown']['region']
        self.assertEqual(
            (region['first_line'], region['last_line'], question['markdown']['literal_occurrences']), (3, 5, 1)
        )
        o = r['request_id']['occurrences']
        self.assertEqual(
            (o['plain_document'], o['plain_body'], o['markdown_document'], o['markdown_question'], o['markdown_body']),
            (1, 1, 2, 1, 1),
        )
        self.assertEqual(sum(v for k, v in o.items() if k.startswith('markdown_') and k != 'markdown_document'), 2)
        self.assertEqual((r['semantic_judgment'], r['producer_authenticity']), ('NOT_ESTABLISHED', 'NOT_ESTABLISHED'))
        self.assertEqual(
            [w['code'] for w in result['warnings']],
            ['source_titles_only_in_plain', 'uncited_entries', 'hidden_markers_not_citations', 'question_absent'],
        )

    def test_every_case_reports_what_a_reader_must_see(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for case in cases.FRAMED_CASES:
                with self.subTest(case=case['id']):
                    plain, markdown, options = cases.apply_case(case)
                    out = io.BytesIO()
                    status = ec.main(
                        cases.write_cli_inputs(Path(tmp), case['id'], plain, markdown, options), stdout=out
                    )
                    result, expect = json.loads(out.getvalue()), case['expect']
                    self.assertEqual(status, expect['exit'])
                    if 'error' in expect:
                        self.assertEqual(result['error']['code'], expect['error'])
                        continue
                    r = result['results']
                    for key in ('raw_bodies_equal', 'normalized_bodies_equal'):
                        if key in expect:
                            self.assertEqual(r[key], expect[key], key)
                    for key in ('url_map_equal', 'all_entries_url_map_equal'):
                        if key in expect:
                            self.assertEqual(r['citations'][key], expect[key], key)
                    for shown in expect.get('shows', []):
                        self.assertIn(shown, cases.describe(result))

    def test_layout_options_are_checked(self) -> None:
        plain, markdown, options = cases.apply_framed_case({'id': 'framed_sample'})
        for change, option in (
            ({'layout': 'bracketed'}, 'layout'),
            ({'question': None}, 'question'),
            ({'plain_body_start': 1}, 'plain_body_start'),
            ({'markdown_definitions_start': 19}, 'markdown_definitions_start'),
        ):
            with self.subTest(change=change):
                error = compare(plain, markdown, **{**options, **change})['error']
                self.assertEqual((error['code'], error['option']), ('invalid_option', option))


class Policy(unittest.TestCase):
    def test_unsafe_normalizations_are_refused_with_a_reason(self) -> None:
        plain, markdown = full_pair()
        for rule, reason in ec.UNSAFE_RULES.items():
            error = compare(plain, markdown, rules=['citation_markers', rule])['error']
            self.assertEqual((error['code'], error['rules']), ('unsafe_normalization', [rule]))
            self.assertIn(reason, error['message'])
        self.assertEqual(compare(plain, markdown, rules=['smart_quotes'])['error']['code'], 'unknown_normalization')

    def test_disabling_a_rule_only_adds_differences(self) -> None:
        plain, markdown = full_pair()
        result = ec.compare_exports(plain, markdown, rules=['citation_markers', 'escaped_hash', 'blank_lines'])
        self.assertFalse(result['results']['normalized_bodies_equal'])
        self.assertEqual(result['results']['body_difference_count'], 1)
        self.assertIn("plain: '|---|---|---|' | markdown: '| --- | --- | --- |'", cases.describe(result))
        self.assertEqual(result['warnings'][-1]['disabled'], ['table_separator_rows'])
        raw = ec.compare_exports(plain, markdown, rules=[])
        self.assertGreater(raw['results']['body_difference_count'], result['results']['body_difference_count'])
        self.assertTrue(raw['results']['citations']['url_map_equal'])  # citation detection does not depend on rewriting


def naive_equal(plain: str, markdown: str) -> bool:
    """REJECTED DESIGN: heuristic extraction plus global rewriting, kept to show why it is unsafe.

    Cut each export at its first line mentioning "sources" or its first "[^N]:" line, drop a leading logo and
    heading, rewrite every "[^N]" to "[N]" and every backslash-hash anywhere, ignore spacing around pipes and
    collapse all whitespace.
    """

    def body(s: str) -> str:
        s = re.sub(r'(?s)\A!\[.*?\)\s*#[^\n]*\n', '', s)
        return re.split(r'(?im)^(?:.*sources.*|\[\^\d+\]:.*)$', s)[0]

    def norm(s: str) -> str:
        s = re.sub(r'\[\^(\d+)\]', r'[\1]', s).replace('\\#', '#')
        return ' '.join(re.sub(r'\s*\|\s*', '|', s).split())

    return norm(body(plain)) == norm(body(markdown))


class RejectedDesign(unittest.TestCase):
    def test_heuristic_global_rewrite_accepts_what_this_tool_reports(self) -> None:
        plain, markdown = full_pair()
        self.assertTrue(naive_equal(plain.decode(), markdown.decode()))  # it does agree on the clean pair
        for case_id in (
            'marker_in_code_rewritten',
            'escape_in_indented_code_rewritten',
            'paragraph_joined',
            'url_mapping_changed',
        ):
            with self.subTest(case=case_id):
                p, m, options = cases.apply_case(next(c for c in cases.CASES if c['id'] == case_id))
                self.assertTrue(naive_equal(p.decode(), m.decode()), 'the rejected design misses this difference')
                result = ec.compare_exports(p, m, **options)
                agree = result['results']['normalized_bodies_equal'] and result['results']['citations']['url_map_equal']
                self.assertFalse(agree, 'this tool reports it')

    def test_heuristic_sources_split_silently_truncates(self) -> None:
        plain = 'Check the inputs[1].\n\nSources of error\n\nRun only if the source is verified[1].\n\nSources\n1. Guide https://example.org/a\n'
        markdown = 'Check the inputs[^1].\n\nSources of error\n\n[^1]: https://example.org/a\n'
        self.assertTrue(naive_equal(plain, markdown))  # both cut at the subheading: the missing condition is never seen
        result = ec.compare_exports(plain.encode(), markdown.encode())
        self.assertFalse(result['results']['normalized_bodies_equal'])
        self.assertIn('Run only if the source is verified', cases.describe(result))


class Limits(unittest.TestCase):
    def padded(self, size: int) -> bytes:
        head = b'Run only if the source is verified[1].\n'
        tail = b'\nSources\n1. Guide https://example.org/a\n'
        return head + b'x' * (size - len(head) - len(tail) - 1) + b'\n' + tail

    def test_document_byte_limit_is_exact(self) -> None:
        markdown = b'Run only if the source is verified[^1].\n\n[^1]: https://example.org/a\n'
        at_limit = self.padded(ec.MAX_DOCUMENT_BYTES)
        self.assertEqual(len(at_limit), ec.MAX_DOCUMENT_BYTES)
        self.assertEqual(ec.compare_exports(at_limit, markdown)['inputs']['plain']['bytes'], ec.MAX_DOCUMENT_BYTES)
        self.assertEqual(compare(at_limit + b' ', markdown)['error']['code'], 'input_too_large')

    def test_line_limit_is_exact(self) -> None:
        markdown = b'x\n' * (ec.MAX_DOCUMENT_LINES - 2) + b'\n[^1]: https://example.org/a\n'
        plain = b'x\n\nSources\n1. Guide https://example.org/a\n'
        self.assertEqual(ec.compare_exports(plain, markdown)['inputs']['markdown']['lines'], ec.MAX_DOCUMENT_LINES)
        self.assertEqual(compare(plain, b'x\n' + markdown)['error']['code'], 'input_too_large')

    def test_question_and_request_id_limits(self) -> None:
        plain, markdown = full_pair()
        ok = 'q' * ec.MAX_QUESTION_BYTES
        self.assertEqual(
            ec.compare_exports(plain, markdown, question=ok)['results']['question']['plain']['supplied_text'], ok
        )
        self.assertEqual(compare(plain, markdown, question=ok + 'q')['error']['code'], 'input_too_large')
        self.assertEqual(
            compare(plain, markdown, request_id='r' * (ec.MAX_REQUEST_ID_BYTES + 1))['error']['code'], 'input_too_large'
        )
        for bad in ('', 'a\nb', 'a\rb', '\ud800'):
            self.assertEqual(compare(plain, markdown, request_id=bad)['error']['code'], 'invalid_option', repr(bad))
        for bad in (0, -1, 10_000, True, '3'):
            self.assertEqual(
                compare(plain, markdown, plain_sources_line=bad)['error']['code'], 'invalid_boundary', repr(bad)
            )

    def test_largest_inputs_stay_within_the_output_limit(self) -> None:
        # every body line differs and is long: the worst case for reported differences
        body_p = ''.join(f'{i} plain {"a" * 100}\n' for i in range(1, 1990))
        body_m = ''.join(f'{i} markdown {"b" * 100}\n' for i in range(1, 1990))
        plain = (body_p + '\nSources\n1. Guide https://example.org/a\n').encode()
        markdown = (body_m + '\n[^1]: https://example.org/a\n').encode()
        out = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'p.txt').write_bytes(plain)
            (Path(tmp) / 'm.md').write_bytes(markdown)
            status = ec.main(['--plain', str(Path(tmp) / 'p.txt'), '--markdown', str(Path(tmp) / 'm.md')], stdout=out)
        self.assertEqual(status, 1)
        self.assertLessEqual(len(out.getvalue()), ec.MAX_OUTPUT_BYTES)
        result = json.loads(out.getvalue())
        self.assertGreater(result['inputs']['markdown']['bytes'], 200_000)
        self.assertEqual(result['results']['body_difference_count'], 1)  # one replace of every line


class Cli(unittest.TestCase):
    """The real script in subprocesses: exit status, stderr, exact stdout bytes, and untouched input files."""

    def run_script(self, *argv: str):
        proc = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, timeout=120, check=False)
        return proc.returncode, proc.stdout, proc.stderr

    def test_statuses_and_untouched_inputs(self) -> None:
        paths = [FIXTURES / name for name in ('full_plain.txt', 'full_markdown.md', 'full_question.txt')]
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        status, out, err = self.run_script(
            '--plain',
            str(paths[0]),
            '--markdown',
            str(paths[1]),
            '--question-file',
            str(paths[2]),
            '--request-id',
            'req-20261023-0001',
        )
        self.assertEqual((status, err), (0, b''))
        self.assertEqual(out, (json.dumps(full_result(), ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in paths], before)
        with tempfile.TemporaryDirectory() as tmp:
            for case_id, expected in (('negation_removed', 1), ('duplicate_definition', 2)):
                p, m, _ = cases.apply_case(next(c for c in cases.CASES if c['id'] == case_id))
                (Path(tmp) / 'p.txt').write_bytes(p)
                (Path(tmp) / 'm.md').write_bytes(m)
                status, out, err = self.run_script(
                    '--plain', str(Path(tmp) / 'p.txt'), '--markdown', str(Path(tmp) / 'm.md')
                )
                self.assertEqual((status, err), (expected, b''), case_id)
                json.loads(out)
        for argv, code in (
            (['--plain', str(paths[0])], 'invalid_arguments'),
            (['--plain', str(paths[0]), '--markdown', str(paths[1]), '--plain-sources-line', '0'], 'invalid_arguments'),
            (['--plain', str(paths[0]), '--markdown', str(ROOT / 'missing.md')], 'input_unreadable'),
            (['--plain', str(paths[0]), '--markdown', str(paths[1]), '--rules', 'case_fold'], 'unsafe_normalization'),
        ):
            status, out, err = self.run_script(*argv)
            self.assertEqual((status, err, json.loads(out)['error']['code']), (2, b'', code), argv)


class Report(unittest.TestCase):
    def test_report_records_operation_and_base(self) -> None:
        report = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn(OPERATION, report)
        self.assertIn(BASE_COMMIT, report)


if __name__ == '__main__':
    unittest.main()
