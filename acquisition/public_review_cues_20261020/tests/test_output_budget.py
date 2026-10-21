"""Tests for the opt-in output byte budget (render_cues(max_output_bytes=...), CLI --max-output-bytes).

Run: python3 -m unittest discover -s tests -v   (from acquisition/public_review_cues_20261020)

Public, synthetic inputs and the dev fixtures only. The CLI class runs the real script in subprocesses because
exit status, stderr and the exact stdout byte count are what a downstream reader sees.
"""

from __future__ import annotations

import io
import json
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / 'review_cues' / 'review_cues.py'
sys.path.insert(0, str(ROOT / 'review_cues'))

import review_cues as tool  # noqa: E402

UNICODE_TEXT = '\U0001f4ccSegún el guía, provided\r\nthat only if no, señor \U0001f468\U0000200d\U0001f469'
ERROR_CODES = (
    'text_not_string',
    'invalid_language',
    'text_too_long',
    'text_not_utf8_encodable',
    'request_too_large',
    'stdin_not_utf8',
    'json_too_deep',
    'invalid_json',
    'invalid_json_constant',
    'duplicate_key',
    'request_not_object',
    'missing_field',
    'unknown_field',
    'invalid_arguments',
    'invalid_output_budget',
    'output_too_large',
)


def unbounded(text: str, language: str) -> bytes:
    """The 1.1.1 CLI serialization, written out independently of render_cues."""
    return (json.dumps(tool.find_cues(text, language), ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def rejection(test: unittest.TestCase, text: str, language: str, budget: int) -> dict:
    with test.assertRaises(tool.CueInputError) as ctx:
        tool.render_cues(text, language, max_output_bytes=budget)
    test.assertEqual(ctx.exception.code, 'output_too_large')
    test.assertEqual(ctx.exception.details['max_output_bytes'], budget)
    test.assertGreater(ctx.exception.details['output_bytes_at_least'], budget)
    return ctx.exception.details


def run_main(payload: bytes, *argv: str):
    out, err = io.BytesIO(), io.BytesIO()
    status = tool.main(list(argv), stdin=io.BytesIO(payload), stdout=out, stderr=err)
    return status, out.getvalue(), err.getvalue()


def request(text: str, language: str) -> bytes:
    return json.dumps({'text': text, 'language': language}).encode('ascii')


class Boundaries(unittest.TestCase):
    def assert_exact_boundary(self, text: str, language: str) -> int:
        full = tool.render_cues(text, language)
        self.assertEqual(full, unbounded(text, language))
        size = len(full)
        if size - 1 >= tool.MIN_OUTPUT_BYTES:
            details = rejection(self, text, language, size - 1)
            self.assertLessEqual(details['output_bytes_at_least'], size)  # a lower bound of the true size
        for budget in (size, size + 1):
            self.assertEqual(tool.render_cues(text, language, max_output_bytes=budget), full, (text[:40], budget))
        return size

    def test_empty_no_match_overlap_and_unicode(self) -> None:
        for text, language in (
            ('', 'en'),
            ('The blue square sits next to a red circle.', 'en'),
            ('Only if dry, no.', 'es+en'),
            (UNICODE_TEXT, 'es+en'),
        ):
            self.assert_exact_boundary(text, language)

    def test_dev_fixtures_and_random_texts(self) -> None:
        texts = []
        for line in (ROOT / 'fixtures' / 'dev.jsonl').read_text(encoding='utf-8').splitlines():
            item = json.loads(line)
            texts += [(item['text'], item['lang']), (item['text'], 'es+en')]
        pieces = ['if', 'only if', 'no', "n't", 'según', 'a menos que', ' ', '\r\n', '\U0001f4cc', 'é', 'x', ',']
        rng = random.Random(20261021)
        texts += [(''.join(rng.choice(pieces) for _ in range(rng.randint(0, 60))), 'es+en') for _ in range(150)]
        for text, language in texts:
            self.assert_exact_boundary(text, language)

    def test_budget_counts_utf8_bytes_not_code_points(self) -> None:
        def extra_bytes(text: str) -> int:
            output = tool.render_cues(text, 'es')
            return len(output) - len(output.decode('utf-8'))

        text = '\U0001f4cc ' + 'según ' * 200  # each match repeats "según" as text and phrase, plus its rule notes
        self.assertGreaterEqual(extra_bytes(text) - extra_bytes(''), 2 * 200)
        full = tool.render_cues(text, 'es')
        rejection(self, text, 'es', len(full.decode('utf-8')))  # a budget in code points is too small
        self.assertEqual(tool.render_cues(text, 'es', max_output_bytes=len(full)), full)

    def test_successful_budgeted_output_is_the_unbounded_output(self) -> None:
        text = ' '.join(['Only if no, a menos que no; except for none of it, según no'] * 30)
        full = tool.render_cues(text, 'es+en')
        self.assertEqual(tool.render_cues(text, 'es+en', max_output_bytes=tool.MAX_OUTPUT_BYTES), full)
        self.assertEqual(json.loads(full), tool.find_cues(text, 'es+en'))


class EarlyStop(unittest.TestCase):
    def skeleton_floor(self, text: str, language: str) -> int:
        result = tool.find_cues(text, language)
        result['match_count'], result['matches'] = 0, []
        return len(json.dumps(result, ensure_ascii=False).encode('utf-8')) + 1

    def test_match_template_has_every_match_key(self) -> None:
        (match,) = [m for m in tool.find_cues('unless', 'en')['matches']]
        self.assertEqual(list(match), list(tool._MATCH_TEMPLATE))
        self.assertEqual(list(match['uncertainty']), list(tool._MATCH_TEMPLATE['uncertainty']))

    def test_dense_overlaps_are_rejected_before_overlap_lists_exist(self) -> None:
        text = ('Only if ' * 12_500)[: tool.MAX_TEXT_CODEPOINTS]  # 25,000 matches, 12,500 overlapping pairs
        with mock.patch.multiple(
            tool,
            _overlap_lists=mock.Mock(side_effect=AssertionError('overlap lists built')),
            _observations=mock.Mock(side_effect=AssertionError('observations built')),
        ):
            details = rejection(self, text, 'en', 1_000_000)
        self.assertLess(details['output_bytes_at_least'], 1_000_000 + 1_000)  # stopped soon after the budget

    def test_pair_count_is_checked_before_overlap_lists(self) -> None:
        text = 'Only if ' * 100  # 200 matches, 100 overlapping pairs
        match_floor = len(json.dumps(tool._MATCH_TEMPLATE, ensure_ascii=False).encode('utf-8'))
        floor = self.skeleton_floor(text, 'en') + 200 * match_floor
        with mock.patch.object(tool, '_overlap_lists', side_effect=AssertionError('overlap lists built')):
            details = rejection(self, text, 'en', floor + 100)
        self.assertEqual(details['output_bytes_at_least'], floor + 200)  # one byte per overlap reference
        self.assertGreater(len(tool.render_cues(text, 'en')), floor + 200)

    def test_pair_count_matches_overlap_lists(self) -> None:
        rng = random.Random(7)
        for _ in range(300):
            spans = sorted((s, s + rng.randint(1, 6)) for s in (rng.randint(0, 30) for _ in range(rng.randint(0, 30))))
            self.assertEqual(tool._overlap_pair_count(spans), sum(map(len, tool._overlap_lists(spans))) // 2)


class Validation(unittest.TestCase):
    def test_callable_budget_validation(self) -> None:
        for bad in (True, False, 511.0, '5000', b'5000', -1, 0, tool.MIN_OUTPUT_BYTES - 1, tool.MAX_OUTPUT_BYTES + 1):
            with self.assertRaises(tool.CueInputError) as ctx:
                tool.render_cues('if', 'en', max_output_bytes=bad)
            self.assertEqual(ctx.exception.code, 'invalid_output_budget', repr(bad))
        with self.assertRaises(tool.CueInputError) as ctx:
            tool.render_cues('if', 'en', max_output_bytes=10**5000)
        self.assertEqual(ctx.exception.code, 'invalid_output_budget')
        rejection(self, 'if', 'en', tool.MIN_OUTPUT_BYTES)  # the smallest budget is valid; no result fits in it

    def test_cli_rejects_unusable_budgets_with_empty_stdout(self) -> None:
        for value in (
            '',
            'abc',
            '-512',
            '+512',
            ' 512',
            '512 ',
            '1_000',
            '\U00000665\U00000661\U00000662',
            '0512',
            '511',
            '0',
            '1e3',
            '512.0',
        ):
            status, out, err = run_main(request('if', 'en'), '--max-output-bytes', value)
            self.assertEqual((status, out), (2, b''), repr(value))
            self.assertEqual(json.loads(err)['error']['code'], 'invalid_output_budget')
        for value in ('9' * 16, '9' * 100_000):
            status, out, err = run_main(request('if', 'en'), '--max-output-bytes', value)
            self.assertEqual((status, out, json.loads(err)['error']['code']), (2, b'', 'invalid_output_budget'))
            self.assertLess(len(err), 400)  # the value is never echoed
        status, out, err = run_main(request('if', 'en'), '--max-output-bytes', str(tool.MIN_OUTPUT_BYTES))
        self.assertEqual((status, json.loads(out)['error']['code'], err), (2, 'output_too_large', b''))

    def test_arguments(self) -> None:
        full = tool.render_cues('if', 'en')
        for argv in ((), ('--max-output-bytes', str(len(full))), ('--max-output-bytes', '999999999999999')):
            self.assertEqual(run_main(request('if', 'en'), *argv), (0, full, b''), argv)
        for argv in (
            ('--verbose',),
            ('--max-output-bytes',),
            ('--max-output-bytes', '600', '--max-output-bytes', '600'),
        ):
            status, out, err = run_main(request('if', 'en'), *argv)
            self.assertEqual((status, json.loads(out)['error']['code'], err), (2, 'invalid_arguments', b''), argv)

    def test_every_rejection_envelope_fits_the_smallest_budget(self) -> None:
        raised = set(re.findall(r"CueInputError\(\s*'(\w+)'", SCRIPT.read_text(encoding='utf-8')))
        self.assertEqual(raised, set(ERROR_CODES))  # every code the tool can produce is checked below
        for code in ERROR_CODES:
            error = tool.CueInputError(code, 'x' * 100_000)
            if code == 'output_too_large':
                error = tool._too_large(tool.MAX_OUTPUT_BYTES, 10**30)
            data = tool._error_output(error, tool.MIN_OUTPUT_BYTES)
            self.assertLessEqual(len(data), tool.MIN_OUTPUT_BYTES, code)
            self.assertEqual(json.loads(data)['error']['code'], code)
        envelope = json.loads(tool._error_output(tool._too_large(tool.MAX_OUTPUT_BYTES, 10**30), tool.MIN_OUTPUT_BYTES))
        self.assertEqual(envelope['error']['output_bytes_at_least'], tool.MAX_OUTPUT_BYTES + 1)
        self.assertNotIn('omitted', envelope['error']['message'])

    def test_long_error_message_is_omitted_only_under_a_budget(self) -> None:
        payload = request('if', 'x' * 5000)
        status, out, _ = run_main(payload)
        self.assertIn('x' * 5000, json.loads(out)['error']['message'])
        status, out, _ = run_main(payload, '--max-output-bytes', '600')
        error = json.loads(out)['error']
        self.assertEqual((status, error['code'], error['message']), (2, 'invalid_language', tool._OMITTED_MESSAGE))
        self.assertLessEqual(len(out), 600)


class CliSubprocess(unittest.TestCase):
    """The real script: exit status, stderr and the exact stdout byte count."""

    def run_script(self, payload: bytes, *argv: str):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *argv], input=payload, capture_output=True, timeout=120, check=False
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_boundaries(self) -> None:
        for text, language in ((UNICODE_TEXT, 'es+en'), ('', 'en')):
            full = tool.render_cues(text, language)
            self.assertEqual(self.run_script(request(text, language)), (0, full, b''))
            size = len(full)
            status, out, err = self.run_script(request(text, language), '--max-output-bytes', str(size - 1))
            self.assertEqual((status, err, json.loads(out)['error']['code']), (2, b'', 'output_too_large'))
            self.assertLessEqual(len(out), size - 1)
            for budget in (size, size + 1):
                self.assertEqual(
                    self.run_script(request(text, language), '--max-output-bytes', str(budget)), (0, full, b'')
                )

    def test_dense_rejection_and_invalid_budget(self) -> None:
        status, out, err = self.run_script(request('Only if ' * 12_500, 'en'), '--max-output-bytes', '1000000')
        self.assertEqual((status, err, json.loads(out)['error']['code']), (2, b'', 'output_too_large'))
        self.assertLessEqual(len(out), 1_000_000)
        status, out, err = self.run_script(request('if', 'en'), '--max-output-bytes', '9' * 5000)
        self.assertEqual((status, out, json.loads(err)['error']['code']), (2, b'', 'invalid_output_budget'))


if __name__ == '__main__':
    unittest.main()
