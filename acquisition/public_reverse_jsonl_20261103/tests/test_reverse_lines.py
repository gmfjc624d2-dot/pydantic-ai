"""Tests for reverse_lines (unittest, standard library only, Python >= 3.9).

Run: python3 -m unittest discover -s tests -v   (from acquisition/public_reverse_jsonl_20261103)

Operation public-reverse-jsonl-20261103-01. The reference is Python's own text mode, read forward:
list(open(path, encoding='utf-8', errors='replace', newline=None)), reversed. All data is synthetic.
REVERSE_LINES_UNDER_TEST, if set, names the directory to import reverse_lines from (tests/mutation_check.py).
"""

from __future__ import annotations

import itertools
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get('REVERSE_LINES_UNDER_TEST', str(ROOT)))

import reverse_lines as rl  # noqa: E402

SEED = 20261103
CHUNK_SIZES = (1, 2, 3, 4, 5, 7, 8, 64, 65_536)
U2028, U2029, NEL = chr(0x2028), chr(0x2029), chr(0x85)


def forward_lines(path: Path) -> list:
    """The trusted reference: Python text mode, read forward."""
    with open(path, encoding='utf-8', errors='replace', newline=None) as f:
        return list(f)


def collect(items, most: int) -> list:
    """All items, failing (instead of hanging on a broken reader) if there are more than `most`."""
    items = list(itertools.islice(items, most + 1))
    if len(items) > most:
        raise AssertionError(f'more than {most} items: more lines than the data can hold')
    return items


class TempDir(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix='reverse_lines_'))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = self.dir / 'data.jsonl'

    def write(self, data: bytes) -> Path:
        self.path.write_bytes(data)
        return self.path

    def assert_matches_reference(self, data: bytes, chunk_sizes=CHUNK_SIZES) -> None:
        """Text lines equal the reversed reference; the raw lines rebuild the bytes; offsets are contiguous."""
        path = self.write(data)
        expected = list(reversed(forward_lines(path)))
        for chunk_size in chunk_sizes:
            with rl.ReverseLineReader(path, chunk_size=chunk_size) as reader:
                lines = collect(reader, len(data) + 1)
            self.assertEqual([line.text() for line in lines], expected, (data, chunk_size))
            self.assertEqual(b''.join(line.content + line.terminator for line in reversed(lines)), data)
            starts, ends = [line.start for line in reversed(lines)], [line.end for line in reversed(lines)]
            self.assertEqual(starts, [0] + ends[:-1] if lines else [])
            self.assertEqual(ends[-1:], [len(data)] if lines else [])
            self.assertEqual(reader.bytes_read, len(data), 'every byte is read exactly once')


class KnownCases(TempDir):
    """Named cases with the reference's answer written out, so a change in the reference would also show."""

    CASES = {
        'empty file': (b'', []),
        'one LF': (b'\n', ['\n']),
        'one CR': (b'\r', ['\n']),
        'one CRLF': (b'\r\n', ['\n']),
        'unterminated last line': (b'a\nb', ['a\n', 'b']),
        'no extra final empty line': (b'a\n', ['a\n']),
        'initial empty line kept': (b'\nb\n', ['\n', 'b\n']),
        'CR CR is two line ends': (b'a\r\rb', ['a\n', '\n', 'b']),
        'CR CRLF is two line ends': (b'a\r\r\nb', ['a\n', '\n', 'b']),
        'LF CR is two line ends': (b'a\n\rb', ['a\n', '\n', 'b']),
        'blank lines of each kind': (b'\n\r\n\r\n\r', ['\n', '\n', '\n', '\n']),
        'U+2028 U+2029 VT FF FS NEL are not line ends': (
            ('p' + U2028 + 'q' + U2029 + 'r\x0bs\x0ct\x1cu' + NEL + 'v\n').encode('utf-8'),
            ['p' + U2028 + 'q' + U2029 + 'r\x0bs\x0ct\x1cu' + NEL + 'v\n'],
        ),
        'truncated sequence before LF is one U+FFFD': (b'\xe2\x82\nX', ['\ufffd\n', 'X']),
        'truncated sequence before CR': (b'\xf0\x9f\x98\rX', ['\ufffd\n', 'X']),
        'surrogate encoding is three U+FFFD': (b'\xed\xa0\x80\n', ['\ufffd\ufffd\ufffd\n']),
        'overlong encoding': (b'\xc0\xaf\r\n', ['\ufffd\ufffd\n']),
        'lone continuation and 0xFF': (b'\x80\xff\n', ['\ufffd\ufffd\n']),
        'BOM is a character with encoding utf-8': (b'\xef\xbb\xbfa\n', ['\ufeffa\n']),
        'NUL is a character': (b'a\x00b\r', ['a\x00b\n']),
        'unterminated invalid tail': (b'\xe2\x82\xac\r\n\xe2', ['\u20ac\n', '\ufffd']),
    }

    def test_each_case_at_every_chunk_size(self) -> None:
        for name, (data, forward) in self.CASES.items():
            with self.subTest(name):
                self.assertEqual(forward_lines(self.write(data)), forward, 'the reference itself')
                self.assert_matches_reference(data, chunk_sizes=range(1, len(data) + 3))

    def test_raw_terminators_are_kept(self) -> None:
        path = self.write(b'a\r\nb\rc\nd')
        with rl.ReverseLineReader(path, chunk_size=1) as reader:
            lines = collect(reader, 4)
        self.assertEqual(
            [(line.start, line.content, line.terminator) for line in lines],
            [(7, b'd', b''), (5, b'c', b'\n'), (3, b'b', b'\r'), (0, b'a', b'\r\n')],
        )
        self.assertEqual([line.text() for line in lines], ['d', 'c\n', 'b\n', 'a\n'])
        self.assertEqual([line.utf8_valid() for line in lines], [True] * 4)


class Differential(TempDir):
    def test_every_short_string_at_every_split(self) -> None:
        """All 1,555 strings of up to 4 bytes over CR, LF, 'a' and the bytes of the euro sign E2 82 AC."""
        alphabet = [b'\r', b'\n', b'a', b'\xe2', b'\x82', b'\xac']
        count = 0
        for n in range(5):
            for combo in itertools.product(alphabet, repeat=n):
                self.assert_matches_reference(b''.join(combo), chunk_sizes=(1, 2, 3, 4, 5))
                count += 1
        self.assertEqual(count, 1555)

    def test_random_documents_fixed_seed(self) -> None:
        """2,000 random documents mixing line ends, valid and invalid UTF-8 and non-delimiting separators."""
        rng = random.Random(SEED)
        tokens = [b'\r', b'\n', b'\r\n', b'a', b'{"k": 1}', b' ', b'\xe2\x82\xac', b'\xf0\x9f\x98\x80', b'\xc3\xa9']
        tokens += [b'\xe2', b'\x82', b'\xac', b'\xf0\x9f', b'\xff', b'\xed\xa0\x80', b'\xef\xbb\xbf', b'\x00']
        tokens += [b'\x0b', b'\x0c', U2028.encode('utf-8'), U2029.encode('utf-8'), NEL.encode('utf-8')]
        for _ in range(2000):
            data = b''.join(rng.choice(tokens) for _ in range(rng.randrange(0, 60)))
            chunk_sizes = sorted({1, rng.choice((2, 3, 5)), rng.choice((7, 13, 64)), 65_536})
            self.assert_matches_reference(data, chunk_sizes=chunk_sizes)

    def test_every_prefix_extent(self) -> None:
        """end=k reads exactly the first k bytes, as if the file had not yet grown past k."""
        rng = random.Random(SEED + 1)
        data = b''.join(rng.choice([b'\r', b'\n', b'\r\n', b'x', b'\xe2\x82\xac', b'\xe2']) for _ in range(80))
        path = self.write(data)
        prefix = self.dir / 'prefix'
        for k in range(len(data) + 1):
            prefix.write_bytes(data[:k])
            expected = list(reversed(forward_lines(prefix)))
            for chunk_size in (1, 3, 64):
                with rl.ReverseLineReader(path, chunk_size=chunk_size, end=k) as reader:
                    self.assertEqual(
                        [line.text() for line in collect(reader, len(data) + 1)], expected, (k, chunk_size)
                    )
                    self.assertEqual(reader.bytes_read, k)


class EarlyStop(TempDir):
    def test_bytes_read_stay_near_the_lines_consumed(self) -> None:
        records = [json.dumps({'seq': i, 'ok': i % 7 != 0}) for i in range(5000)]
        data = ('\n'.join(records) + '\n').encode()
        path = self.write(data)
        for chunk_size in (1, 16, 4096):
            with rl.ReverseLineReader(path, chunk_size=chunk_size) as reader:
                lines = iter(reader)
                for k in range(1, 40):
                    line = next(lines)
                    self.assertEqual(json.loads(line.text())['seq'], 5000 - k)
                    # to yield a line the reader needs its start, i.e. the line end before it (up to 2 bytes)
                    self.assertGreaterEqual(reader.bytes_read, len(data) - line.start)
                    self.assertLessEqual(reader.bytes_read, len(data) - line.start + chunk_size + 1)
            self.assertLess(reader.bytes_read, len(data) // 10)

    def test_streak_scan_stops_at_the_first_break(self) -> None:
        records = [{'seq': i, 'ok': i < 100 or i >= 2600} for i in range(3000)]  # newest streak: 400 records
        self.write(''.join(json.dumps(r) + '\n' for r in records).encode())
        with rl.ReverseLineReader(self.path, chunk_size=4096) as reader:
            streak = 0
            for record in rl.reverse_json_records(iter(reader), malformed='raise'):
                if not record.value['ok']:
                    break
                streak += 1
        self.assertEqual(streak, 400)
        self.assertLess(reader.bytes_read, self.path.stat().st_size // 4)


class Failures(TempDir):
    def test_truncation_while_reading_is_an_error_not_a_short_result(self) -> None:
        data = b''.join(b'line %d\n' % i for i in range(1000))
        path = self.write(data)
        with rl.ReverseLineReader(path, chunk_size=64) as reader:
            lines = iter(reader)
            next(lines)
            os.truncate(path, 100)
            with self.assertRaises(rl.ExtentChangedError):
                for _ in lines:
                    pass
            self.assertIn('shorter than the extent', ' '.join(reader.observed_changes()))

    def test_read_errors_propagate(self) -> None:
        path = self.write(b'a\nb\nc\n' * 100)

        class Failing:
            def __init__(self, inner):
                self.inner, self.calls = inner, 0

            def seek(self, offset):
                return self.inner.seek(offset)

            def read(self, n):
                self.calls += 1
                if self.calls == 3:
                    raise OSError(5, 'synthetic I/O error')
                return self.inner.read(n)

            def close(self):
                self.inner.close()

        reader = rl.ReverseLineReader(path, chunk_size=8)
        reader._file = Failing(reader._file)  # type: ignore[assignment]
        with reader, self.assertRaises(OSError) as caught:
            collect(reader, 300)
        self.assertEqual(caught.exception.errno, 5)

    def test_short_reads_are_completed(self) -> None:
        data = b'x' * 50 + b'\r\n' + b'y' * 50
        path = self.write(data)

        class Trickle:
            def __init__(self, inner):
                self.inner = inner

            def seek(self, offset):
                return self.inner.seek(offset)

            def read(self, n):
                return self.inner.read(min(n, 3))

            def close(self):
                self.inner.close()

        reader = rl.ReverseLineReader(path, chunk_size=16)
        reader._file = Trickle(reader._file)  # type: ignore[assignment]
        with reader:
            self.assertEqual([line.text() for line in collect(reader, 2)], ['y' * 50, 'x' * 50 + '\n'])
        self.assertEqual(reader.bytes_read, len(data))

    def test_invalid_arguments_and_files(self) -> None:
        path = self.write(b'abc\n')
        for options in ({'chunk_size': 0}, {'chunk_size': True}, {'end': 5}, {'end': -1}, {'max_line_bytes': -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                rl.ReverseLineReader(path, **options)
        with self.assertRaisesRegex(ValueError, 'not a regular file'):
            rl.ReverseLineReader(self.dir)  # a directory
        if hasattr(os, 'mkfifo'):
            fifo = self.dir / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, 'not a regular file'):
                rl.ReverseLineReader(fifo)  # rejected without waiting for a writer
        with rl.ReverseLineReader(path) as reader:
            collect(reader, 1)
            with self.assertRaises(RuntimeError):
                iter(reader)

    def test_line_limit_fails_before_reading_the_whole_line(self) -> None:
        data = b'head\n' + b'z' * 1_000_000 + b'\n'
        path = self.write(data)
        with rl.ReverseLineReader(path, chunk_size=4096, max_line_bytes=10_000) as reader:
            with self.assertRaises(rl.LineTooLongError):
                collect(reader, 2)
            self.assertLessEqual(reader.bytes_read, 10_000 + 2 * 4096)
        with rl.ReverseLineReader(path, chunk_size=4096, max_line_bytes=1_000_000) as reader:
            self.assertEqual([len(line.content) for line in collect(reader, 2)], [1_000_000, 4])


class Snapshot(TempDir):
    """What the extent means when the file changes (CONTRACT.md, "Extent and concurrent changes")."""

    def test_appends_after_opening_are_not_seen_but_are_reported(self) -> None:
        path = self.write(b'{"n": 1}\n{"n": 2}\n{"partial')
        with rl.ReverseLineReader(path) as reader:
            with open(path, 'ab') as f:
                f.write(b'": 3}\n{"n": 4}\n')
            lines = collect(reader, 3)
            self.assertEqual([line.text() for line in lines], ['{"partial', '{"n": 2}\n', '{"n": 1}\n'])
            self.assertEqual(lines[0].terminator, b'', 'an unterminated last line may be a write in progress')
            self.assertTrue(any('grew' in c for c in reader.observed_changes()))

    def test_path_replacement_keeps_reading_the_opened_file(self) -> None:
        path = self.write(b'old 1\nold 2\n')
        replacement = self.dir / 'new.jsonl'
        replacement.write_bytes(b'new\n')
        with rl.ReverseLineReader(path) as reader:
            os.replace(replacement, path)
            self.assertEqual([line.text() for line in collect(reader, 2)], ['old 2\n', 'old 1\n'])
            self.assertIn('the path now names a different file', reader.observed_changes())

    def test_in_place_rewrite_inside_the_extent_is_not_detected_by_reading(self) -> None:
        path = self.write(b'aaaa\nbbbb\n')
        with rl.ReverseLineReader(path, chunk_size=1) as reader:
            lines = iter(reader)
            self.assertEqual(next(lines).text(), 'bbbb\n')  # bytes 3-9 read: the line, its line end, one more
            with open(path, 'r+b') as f:
                f.write(b'AAAA')  # same size: reads cannot tell
            self.assertEqual(next(lines).text(), 'AAAa\n')  # a mix of before and after; documented limitation


class Json(TempDir):
    def test_policy_must_be_chosen(self) -> None:
        path = self.write(b'{"a": 1}\n')
        with rl.ReverseLineReader(path) as reader:
            lines = iter(reader)
            with self.assertRaises(TypeError):
                rl.reverse_json_records(lines)  # type: ignore[call-arg]
            with self.assertRaises(ValueError):
                collect(rl.reverse_json_records(lines, malformed='skip'), 1)

    def test_report_keeps_every_line_and_raise_stops(self) -> None:
        data = b'{"a": 1}\n\n{"a": \n"caf\xe9"\n{"b": 2}\n{"partial'
        path = self.write(data)
        with rl.ReverseLineReader(path) as reader:
            records = collect(rl.reverse_json_records(iter(reader), malformed='report'), 6)
        self.assertEqual([r.value for r in records], [None, {'b': 2}, 'caf\ufffd', None, None, {'a': 1}])
        self.assertEqual([r.error is None for r in records], [False, True, True, False, False, True])
        self.assertEqual([r.line.utf8_valid() for r in records], [True, True, False, True, True, True])
        self.assertEqual(b''.join(r.line.content + r.line.terminator for r in reversed(records)), data)
        with rl.ReverseLineReader(path) as reader:
            with self.assertRaises(rl.MalformedJsonLineError) as caught:
                collect(rl.reverse_json_records(iter(reader), malformed='raise'), 6)
        self.assertEqual(caught.exception.line.text(), '{"partial')


class TextLines(TempDir):
    def test_generator_closes_the_file(self) -> None:
        path = self.write(b'1\n2\n3\n')
        lines = rl.reverse_text_lines(path, chunk_size=2)
        self.assertEqual(next(lines), '3\n')
        lines.close()
        self.assertEqual(collect(rl.reverse_text_lines(path), 3), ['3\n', '2\n', '1\n'])


if __name__ == '__main__':
    unittest.main()
