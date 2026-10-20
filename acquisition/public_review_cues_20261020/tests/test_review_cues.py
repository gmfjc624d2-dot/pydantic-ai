"""Contract tests for review_cues (unittest, standard library only, Python >= 3.9).

Run: python3 -m unittest discover -s tests -v   (from acquisition/public_review_cues_20261020)

Uses the dev fixtures and synthetic strings only; the reserved set is never read here.
"""

from __future__ import annotations

import io
import itertools
import json
import random
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'review_cues'))

from review_cues import (  # noqa: E402
    MAX_JSON_NESTING,
    MAX_REQUEST_BYTES,
    MAX_TEXT_CODEPOINTS,
    CueInputError,
    Ruleset,
    _overlap_lists,
    default_ruleset,
    find_cues,
    main,
)


def overlap_oracle(spans) -> list:
    """The contract's overlap definition checked on every pair (deliberately quadratic; independent of the tool)."""
    related = [set() for _ in spans]
    for (i, (start_i, end_i)), (j, (start_j, end_j)) in itertools.combinations(enumerate(spans), 2):
        if start_j < end_i and start_i < end_j:
            related[i].add(j)
            related[j].add(i)
    return [sorted(r) for r in related]


def check_invariants(test: unittest.TestCase, text: str, result: dict) -> None:
    encoded = text.encode('utf-8')
    test.assertEqual(result['input']['codepoints'], len(text))
    test.assertEqual(result['input']['utf8_bytes'], len(encoded))
    test.assertEqual(result['match_count'], len(result['matches']))
    previous = None
    for i, m in enumerate(result['matches']):
        test.assertTrue(0 <= m['start'] < m['end'] <= len(text))
        test.assertEqual(text[m['start'] : m['end']], m['text'])
        test.assertEqual(encoded[m['byte_start'] : m['byte_end']].decode('utf-8'), m['text'])
        test.assertEqual(m['byte_start'], len(text[: m['start']].encode('utf-8')))
        test.assertEqual(m['byte_end'], len(text[: m['end']].encode('utf-8')))
        key = (m['start'], m['end'], m['rule_id'])
        if previous is not None:
            test.assertLess(previous, key)
        previous = key
        for j in m['overlaps']:
            o = result['matches'][j]
            test.assertTrue(o['start'] < m['end'] and m['start'] < o['end'])
            test.assertIn(i, o['overlaps'])
    spans = [(m['start'], m['end']) for m in result['matches']]
    test.assertEqual([m['overlaps'] for m in result['matches']], overlap_oracle(spans))


def run_cli(payload: bytes, argv=None, stream=None):
    out = io.BytesIO()
    status = main(argv or [], stdin=stream or io.BytesIO(payload), stdout=out)
    return status, json.loads(out.getvalue().decode('utf-8'))


class GuardedStream:
    """A request stream that fails the test on any unsized read or any read past MAX_REQUEST_BYTES + 1."""

    def __init__(self, data: bytes, endless: bytes = b'') -> None:
        self.data, self.endless, self.delivered = data, endless, 0

    def read(self, size=-1) -> bytes:
        if size is None or size < 0:
            raise AssertionError('unbounded read')
        if self.delivered + size > MAX_REQUEST_BYTES + 1:
            raise AssertionError(f'read({size}) after {self.delivered} bytes goes past the request limit')
        chunk = self.data[self.delivered : self.delivered + size]
        if self.endless:  # an endless producer: the data, then `endless` repeated forever
            chunk += (self.endless * (size // len(self.endless) + 1))[: size - len(chunk)]
        self.delivered += len(chunk)
        return chunk


class CountedInt(int):
    comparisons = 0

    def __lt__(self, other: int) -> bool:
        CountedInt.comparisons += 1
        return int.__lt__(self, other)


class RoundTrip(unittest.TestCase):
    def test_dev_fixtures(self) -> None:
        for line in (ROOT / 'fixtures' / 'dev.jsonl').read_text(encoding='utf-8').splitlines():
            item = json.loads(line)
            for language in (item['lang'], 'es+en'):
                check_invariants(self, item['text'], find_cues(item['text'], language))

    def test_random_unicode_strings(self) -> None:
        pieces = [
            'if',
            'unless',
            'no',
            'not',
            "n't",
            'n’t',
            'según',
            'según',
            'si',
            'sí',
            'a menos que',
            'provided\r\nthat',
            'as long as',
            ' ',
            '\r\n',
            '\n',
            '\t',
            ' ',
            '.',
            ',',
            'x',
            'é',
            'é',
            '\U0001f4cc',
            '❤️',
            '\U0001f468‍\U0001f469‍\U0001f467',
            '\U0001f44d\U0001f3fd',
            '中',
            'Σ',
            '​',
            '﻿',
            'IF',
            'İ',
            'ı',
            'ſ',
            'nada',
            'nadar',
            'sinfonía',
        ]
        rng = random.Random(20261020)
        for _ in range(500):
            text = ''.join(rng.choice(pieces) for _ in range(rng.randint(0, 25)))
            check_invariants(self, text, find_cues(text, rng.choice(['es', 'en', 'es+en'])))


class Rejection(unittest.TestCase):
    def assert_rejected(self, code: str, text, language='en') -> None:
        with self.assertRaises(CueInputError) as ctx:
            find_cues(text, language)
        self.assertEqual(ctx.exception.code, code)

    def test_function_rejects(self) -> None:
        for bad in (None, 1, 1.5, b'if', ['if'], {'text': 'if'}, True):
            self.assert_rejected('text_not_string', bad)
        for lang in (None, '', 'fr', 'ES', 'en+es', 'es,en', ['es']):
            self.assert_rejected('invalid_language', 'if', lang)
        self.assert_rejected('text_not_utf8_encodable', 'if \ud800 then')
        self.assert_rejected('text_not_utf8_encodable', '\udfff')
        self.assert_rejected('text_too_long', 'x' * (MAX_TEXT_CODEPOINTS + 1))
        self.assertEqual(find_cues('x' * MAX_TEXT_CODEPOINTS, 'en')['match_count'], 0)

    def test_cli_rejects(self) -> None:
        cases = {
            b'\xff\xfe{}': 'stdin_not_utf8',
            b'{"text": "if", "language": "en"': 'invalid_json',
            b'\xef\xbb\xbf{"text": "if", "language": "en"}': 'invalid_json',
            b'{"text": NaN, "language": "en"}': 'invalid_json_constant',
            b'{"text": "if", "text": "no", "language": "en"}': 'duplicate_key',
            b'["if"]': 'request_not_object',
            b'"if"': 'request_not_object',
            b'{"text": "if"}': 'missing_field',
            b'{"text": "if", "language": "en", "lang": "en"}': 'unknown_field',
            b'{"text": 7, "language": "en"}': 'text_not_string',
            b'{"text": "if", "language": "de"}': 'invalid_language',
            b'{"text": "a \\ud800 b", "language": "en"}': 'text_not_utf8_encodable',
            b'': 'invalid_json',
        }
        for payload, code in cases.items():
            status, body = run_cli(payload)
            self.assertEqual((status, body['error']['code']), (2, code), payload)
            self.assertNotIn('matches', body)
        status, body = run_cli(b'{"text": "if", "language": "en"}', ['--verbose'])
        self.assertEqual((status, body['error']['code']), (2, 'invalid_arguments'))


class RequestLimits(unittest.TestCase):
    def test_reported_deep_array_is_a_structured_rejection(self) -> None:
        # synthetic counterexample reported against 1.0.0: uncaught RecursionError (exit 1) on CPython 3.9.6
        status, body = run_cli(b'[' * 1100 + b'0' + b']' * 1100)
        self.assertEqual((status, body['error']['code']), (2, 'json_too_deep'))
        status, body = run_cli(b'[0]')
        self.assertEqual((status, body['error']['code']), (2, 'request_not_object'))

    def test_nesting_limit_is_exact(self) -> None:
        for opener, closer, code in ((b'[', b']', 'request_not_object'), (b'{"a": ', b'}', 'missing_field')):
            for depth, expected in ((MAX_JSON_NESTING, code), (MAX_JSON_NESTING + 1, 'json_too_deep')):
                status, body = run_cli(opener * depth + b'0' + closer * depth)
                self.assertEqual((status, body['error']['code']), (2, expected), (opener, depth))
        status, body = run_cli(b'[' * 10_000 + b'0' + b']' * 10_000)  # also crashed 1.0.0 on CPython 3.13.16
        self.assertEqual((status, body['error']['code']), (2, 'json_too_deep'))
        status, body = run_cli(b'[' * (MAX_JSON_NESTING + 1))  # malformed and too deep: depth is checked first
        self.assertEqual((status, body['error']['code']), (2, 'json_too_deep'))

    def test_brackets_inside_strings_are_not_nesting(self) -> None:
        text = '"[{\\' * 400 + 'según'
        status, body = run_cli(json.dumps({'text': text, 'language': 'es'}).encode('ascii'))
        self.assertEqual((status, [m['text'] for m in body['matches']]), (0, ['según']))
        check_invariants(self, text, body)
        status, body = run_cli(b'{"text": "' + b'[' * 1100)  # an unterminated string runs to the end
        self.assertEqual((status, body['error']['code']), (2, 'invalid_json'))

    def test_guard_rejects_unbounded_reads(self) -> None:
        for size in (None, -1, MAX_REQUEST_BYTES + 2):
            with self.assertRaises(AssertionError):
                GuardedStream(b'{}').read(size)

    def test_exact_limit_is_accepted_and_one_more_byte_is_rejected(self) -> None:
        # the longest text, in its longest JSON spelling: every code point an escaped surrogate pair (12 bytes)
        body = json.dumps({'text': '\U0001f4cc' * MAX_TEXT_CODEPOINTS, 'language': 'es'}).encode('ascii')
        self.assertEqual(body[:22], b'{"text": "\\ud83d\\udccc')
        exact = body + b' ' * (MAX_REQUEST_BYTES - len(body))
        stream = GuardedStream(exact)
        status, result = run_cli(b'', stream=stream)
        self.assertEqual((status, result['match_count'], stream.delivered), (0, 0, MAX_REQUEST_BYTES))
        self.assertEqual(result['input']['codepoints'], MAX_TEXT_CODEPOINTS)
        self.assertEqual(result['input']['utf8_bytes'], 4 * MAX_TEXT_CODEPOINTS)
        status, result = run_cli(b'', stream=GuardedStream(exact + b' '))
        self.assertEqual((status, result['error']['code']), (2, 'request_too_large'))
        self.assertNotIn('matches', result)

    def test_endless_request_stops_after_limit_plus_one_byte(self) -> None:
        stream = GuardedStream(b'{"text": "', endless=b'si no ')
        status, result = run_cli(b'', stream=stream)
        self.assertEqual((status, result['error']['code']), (2, 'request_too_large'))
        self.assertEqual(stream.delivered, MAX_REQUEST_BYTES + 1)

    def test_escaped_unicode_keeps_exact_offsets(self) -> None:
        payload = b'{"text": "\\ud83d\\udcccSeg\\u00fan el gu\\u00eda, provided\\r\\nthat", "language": "es+en"}'
        status, result = run_cli(b'', stream=GuardedStream(payload))
        self.assertEqual(status, 0)
        check_invariants(self, '\U0001f4ccSegún el guía, provided\r\nthat', result)
        self.assertEqual(
            [(m['text'], m['start'], m['end'], m['byte_start'], m['byte_end']) for m in result['matches']],
            [('Según', 1, 6, 4, 10), ('provided\r\nthat', 16, 30, 21, 35)],
        )


SPAN_LAYOUTS = {
    'equal starts': [(0, 1), (0, 2), (0, 2), (0, 5), (1, 2)],
    'nested': [(0, 10), (1, 9), (2, 8), (3, 7), (4, 5)],
    'duplicate spans': [(2, 4), (2, 4), (2, 4), (3, 5), (3, 5)],
    'touching, not overlapping': [(0, 2), (2, 4), (4, 6)],
    'chain': [(k, k + 2) for k in range(50)],
    'long disjoint': [(2 * k, 2 * k + 1) for k in range(500)],
    'empty spans (never produced by find_cues)': [(0, 3), (1, 1), (1, 5), (3, 3), (3, 3), (5, 5)],
}


class Overlaps(unittest.TestCase):
    def test_synthetic_layouts_match_oracle(self) -> None:
        for name, spans in SPAN_LAYOUTS.items():
            self.assertEqual(spans, sorted(spans), name)
            self.assertEqual(_overlap_lists(spans), overlap_oracle(spans), name)
        self.assertEqual(
            _overlap_lists(SPAN_LAYOUTS['equal starts']),
            [[1, 2, 3], [0, 2, 3, 4], [0, 1, 3, 4], [0, 1, 2, 4], [1, 2, 3]],
        )
        self.assertEqual(_overlap_lists(SPAN_LAYOUTS['touching, not overlapping']), [[], [], []])

    def test_random_layouts_match_oracle(self) -> None:
        rng = random.Random(20261020)
        for _ in range(2000):
            spans = sorted((s, s + rng.randint(0, 6)) for s in (rng.randint(0, 30) for _ in range(rng.randint(0, 40))))
            self.assertEqual(_overlap_lists(spans), overlap_oracle(spans), spans)

    def test_disjoint_spans_need_no_pairwise_comparisons(self) -> None:
        n = 20_000
        spans = [(CountedInt(2 * k), CountedInt(2 * k + 1)) for k in range(n)]
        CountedInt.comparisons = 0
        self.assertEqual(_overlap_lists(spans), [[] for _ in range(n)])
        self.assertLessEqual(CountedInt.comparisons, n * n.bit_length())  # a pairwise check needs n * (n - 1)

    def test_dense_real_matches_match_oracle(self) -> None:
        text = ' '.join(['Only if no, a menos que no; except for none of it, según no'] * 40)
        check_invariants(self, text, find_cues(text, 'es+en'))


class LexicalControls(unittest.TestCase):
    def test_every_phrase_matches_itself(self) -> None:
        for rule in default_ruleset().data['rules']:
            for phrase in rule['phrases']:
                for form in {phrase, unicodedata.normalize('NFC', phrase), unicodedata.normalize('NFD', phrase)}:
                    text = f'is{form}.' if rule.get('boundary') == 'suffix' else f'«{form}».'
                    result = find_cues(text, rule['lang'])
                    spans = {(m['rule_id'], m['text']) for m in result['matches']}
                    self.assertIn((rule['id'], form), spans, (rule['id'], form))

    def test_words_containing_cue_letters_do_not_match(self) -> None:
        cases = {
            'en': [
                'notable knot',
                'iffy elif ifs',
                'mayor dismay',
                'nonce',
                'unlessened',
                'mustard',
                'shallow',
                'snowy',
                'nothingness',
                'sayso',
            ],
            'es': [
                'sinfonía sino sinónimo',
                'nadar nadamos',
                'debemos',
                'puedes',
                'nini',
                'segúń',
                'sí',
                'sí',
                'exceptó',
                'notario',
                'siempre',
            ],
        }
        for lang, texts in cases.items():
            for text in texts:
                self.assertEqual(find_cues(text, lang)['matches'], [], (lang, text))

    def test_cue_free_text_is_empty_with_notice(self) -> None:
        result = find_cues('The blue square sits next to a red circle.', 'en')
        self.assertEqual(result['matches'], [])
        self.assertIn('does not mean the text has no condition', result['notice'])


class DocumentedBehavior(unittest.TestCase):
    def spans(self, text: str, lang: str = 'es+en'):
        return [(m['text'], m['start'], m['end'], m['rule_id']) for m in find_cues(text, lang)['matches']]

    def test_crlf_inside_multiword_cue_is_kept(self) -> None:
        text = 'Borrow it, provided\r\nthat you return it.'
        (m,) = find_cues(text, 'en')['matches']
        self.assertEqual(m['text'], 'provided\r\nthat')
        self.assertEqual((m['start'], m['end'], m['byte_start'], m['byte_end']), (11, 25, 11, 25))
        self.assertTrue(any('line break' in o for o in m['uncertainty']['observations']))

    def test_crlf_before_and_after_cue(self) -> None:
        self.assertEqual(self.spans('ok\r\nif\r\n', 'en'), [('if', 4, 6, 'en.condition.if')])

    def test_multiword_separator_is_any_unicode_whitespace(self) -> None:
        for sep in (' ', '  ', '\t', ' ', '\r\n', ' \n '):
            self.assertEqual(len(self.spans(f'a menos{sep}que', 'es')), 1, repr(sep))
        for sep in ('​', '-', '_', ''):
            self.assertEqual(self.spans(f'a menos{sep}que', 'es'), [], repr(sep))

    def test_emoji_before_cue(self) -> None:
        for prefix in ('\U0001f4cc', '❤️', '\U0001f468‍\U0001f469‍\U0001f467', '\U0001f44d\U0001f3fd'):
            text = prefix + 'unless'
            ((surface, start, end, rule),) = self.spans(text, 'en')
            self.assertEqual((surface, end - start, rule), ('unless', 6, 'en.condition.unless'))
            m = find_cues(text, 'en')['matches'][0]
            self.assertEqual(m['byte_start'], len(prefix.encode('utf-8')))
            self.assertNotEqual(m['byte_start'], m['start'])

    def test_letters_and_marks_block_boundaries(self) -> None:
        self.assertEqual(self.spans('áunless', 'en'), [])
        self.assertEqual(self.spans('áunless', 'en'), [])  # decomposed letter before
        self.assertEqual(self.spans('sí claro', 'es'), [])  # mark after the cue modifies its last letter
        self.assertEqual(self.spans('2if if2 _if', 'en'), [])

    def test_composed_and_decomposed_spellings(self) -> None:
        composed = find_cues('según el guía', 'es')['matches'][0]
        decomposed = find_cues('según el guía', 'es')['matches'][0]
        self.assertEqual((composed['text'], composed['end']), ('según', 5))
        self.assertEqual((decomposed['text'], decomposed['end'], decomposed['byte_end']), ('según', 6, 7))
        self.assertEqual(composed['matched_forms'], ['as_listed', 'NFC'])
        self.assertEqual(decomposed['matched_forms'], ['NFD'])
        self.assertTrue(any('decomposed' in o for o in decomposed['uncertainty']['observations']))

    def test_case_insensitive_with_reported_case(self) -> None:
        for text, case in (('IF', 'upper'), ('If', 'title'), ('iF', 'mixed'), ('SEGÚN', 'upper'), ('sEgÚn', 'mixed')):
            m = find_cues(text, 'es+en')['matches'][0]
            self.assertEqual(m['text'], text)
            self.assertIn(f'letter case of the match: {case}', m['uncertainty']['observations'])
        self.assertEqual(self.spans('May 3', 'en'), [('May', 0, 3, 'en.uncertainty.may')])

    def test_unicode_case_equivalences_are_matched_and_flagged(self) -> None:
        for text, rule in (('İF', 'en.condition.if'), ('nı', 'es.negation.ni'), ('ſi', 'es.condition.si')):
            m = find_cues(text, 'es+en')['matches'][0]
            self.assertEqual((m['text'], m['rule_id']), (text, rule))
            self.assertTrue(any('case equivalence' in o for o in m['uncertainty']['observations']))
        self.assertEqual(self.spans('ｉｆ', 'en'), [])  # full-width letters are compatibility characters

    def test_overlaps_are_all_reported(self) -> None:
        result = find_cues('Only if dry.', 'en')
        self.assertEqual(
            [(m['text'], m['rule_id']) for m in result['matches']],
            [('Only if', 'en.condition.only_if'), ('if', 'en.condition.if')],
        )
        self.assertEqual([m['overlaps'] for m in result['matches']], [[1], [0]])
        both = find_cues('no', 'es+en')['matches']
        self.assertEqual([m['rule_id'] for m in both], ['en.negation.no', 'es.negation.no'])
        self.assertEqual(find_cues('no obstante', 'es')['matches'][0]['text'], 'no')

    def test_suffix_rule_needs_a_host(self) -> None:
        self.assertEqual(
            self.spans("isn't can’t", 'en'), [("n't", 2, 5, 'en.negation.nt'), ('n’t', 8, 11, 'en.negation.nt')]
        )
        self.assertEqual(self.spans("n't 'n't", 'en'), [])

    def test_bom_and_empty_text(self) -> None:
        self.assertEqual(self.spans('﻿if', 'en'), [('if', 1, 3, 'en.condition.if')])
        empty = find_cues('', 'en')
        self.assertEqual((empty['match_count'], empty['input']['sha256'][:8]), (0, 'e3b0c442'))

    def test_language_selection(self) -> None:
        self.assertEqual(self.spans('si', 'en'), [])
        self.assertEqual(self.spans('if', 'es'), [])


class Identity(unittest.TestCase):
    def test_deterministic_output_and_hashes(self) -> None:
        a = json.dumps(find_cues('Si no, según dice.', 'es'), sort_keys=True)
        b = json.dumps(find_cues('Si no, según dice.', 'es'), sort_keys=True)
        self.assertEqual(a, b)
        r = find_cues('x', 'es')
        self.assertEqual(r['input']['sha256'], '2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881')
        self.assertNotEqual(r['configuration_sha256'], find_cues('x', 'en')['configuration_sha256'])
        self.assertIn('unicode_database_version', r['configuration'])

    def test_rule_change_changes_identity(self) -> None:
        raw = json.loads((ROOT / 'review_cues' / 'rules_v1.json').read_text(encoding='utf-8'))
        raw['rules'][0]['notes'].append('changed')
        changed = Ruleset(json.dumps(raw).encode('utf-8'))
        base = find_cues('if', 'en')
        other = find_cues('if', 'en', changed)
        self.assertNotEqual(base['ruleset']['canonical_sha256'], other['ruleset']['canonical_sha256'])
        self.assertNotEqual(base['configuration_sha256'], other['configuration_sha256'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rules.json'
            path.write_text(json.dumps(raw), encoding='utf-8')
            status, body = run_cli(b'{"text": "if", "language": "en"}', ['--rules', str(path)])
            self.assertEqual((status, body['ruleset']['canonical_sha256']), (0, other['ruleset']['canonical_sha256']))

    def test_cli_round_trip_via_real_process(self) -> None:
        payload = json.dumps({'text': '\U0001f4ccSegún el guía, provided\r\nthat', 'language': 'es+en'}).encode()
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'review_cues' / 'review_cues.py')],
            input=payload,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        body = json.loads(proc.stdout.decode('utf-8'))
        text = json.loads(payload)['text']
        check_invariants(self, text, body)
        self.assertEqual([m['text'] for m in body['matches']], ['Según', 'provided\r\nthat'])


if __name__ == '__main__':
    unittest.main()
