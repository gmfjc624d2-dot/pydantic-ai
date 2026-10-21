"""Lexical review-cue highlighter for Spanish and English. Standard library only; Python >= 3.9.

Pure function:  find_cues(text, language) -> dict          (raises CueInputError on invalid input)
Rendering:      render_cues(text, language, max_output_bytes=None) -> bytes   (exactly what the CLI writes)
CLI:            python3 review_cues.py [--rules PATH] [--max-output-bytes N] < request.json > response.json
                request: {"text": "...", "language": "es" | "en" | "es+en"}, at most MAX_REQUEST_BYTES
                exit 0 with a result, exit 2 with {"error": {...}} for invalid input.

A highlight means a configured phrase occurred at those coordinates. It never states scope, a speaker's
identity, entailment, semantic completeness, permission or an acceptance verdict. An empty match list
means that no configured cue matched, not that the text contains no qualification. See CONTRACT.md.
"""

from __future__ import annotations

import bisect
import decimal
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Sequence, Tuple

SCHEMA = 'review-cues/1'
TOOL_NAME = 'review_cues'
TOOL_VERSION = '1.2.0'
LANGUAGES = ('es', 'en', 'es+en')
MAX_TEXT_CODEPOINTS = 100_000
# The CLI never reads more than this many request bytes (+1 to detect excess). 12 bytes is the longest JSON
# spelling of one code point (an escaped surrogate pair such as "\ud83d\udccc"), so any text within
# MAX_TEXT_CODEPOINTS fits, plus 64 KiB for the keys, the language value and insignificant whitespace.
MAX_REQUEST_BYTES = 12 * MAX_TEXT_CODEPOINTS + 65_536
_READ_CHUNK_BYTES = 65_536
# A valid request nests one level. Deeper JSON is rejected before parsing because Python's json module
# raises RecursionError at an interpreter-dependent depth (from 994 levels on CPython 3.9.25 as a script).
MAX_JSON_NESTING = 64
# JSON integers longer than this are kept as Decimal instead of int (see _parse_int). 640 is the lowest
# integer string-conversion limit CPython can be configured with, so int() never raises below it.
MAX_INT_DIGITS = 640
_JSON_STRING_OR_BRACKET = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"?|[\[\]{}]', re.DOTALL)
# Opt-in output budget (render_cues(max_output_bytes=N), CLI --max-output-bytes N). It counts every byte the
# CLI writes to stdout: the UTF-8 encoding of json.dumps(obj, ensure_ascii=False, indent=2) plus one "\n".
# MIN_OUTPUT_BYTES is the smallest accepted budget: every rejection the CLI writes under a budget fits in it.
MIN_OUTPUT_BYTES = 512
MAX_OUTPUT_BYTES = 10**15 - 1
_OUTPUT_BUDGET_ARG = re.compile(r'[1-9][0-9]{0,14}')
_OMITTED_MESSAGE = 'message omitted: the complete error does not fit max_output_bytes'
_INDENTED = json.JSONEncoder(ensure_ascii=False, indent=2)
CLI_USAGE = 'usage: review_cues.py [--rules PATH] [--max-output-bytes N] < request.json'
DEFAULT_RULES_PATH = Path(__file__).resolve().with_name('rules_v1.json')
REQUEST_FIELDS = ('text', 'language')

NOTICE = (
    'Highlights are lexical candidates for a human reviewer. An empty list means no configured cue matched; '
    'it does not mean the text has no condition, exception, negation, uncertainty, attribution or obligation. '
    'The tool does not infer scope, speaker identity, entailment, semantic completeness, permission or acceptance.'
)
MATCHING = {
    'case': 'case-insensitive (Python re.IGNORECASE: Unicode simple case folding, no full folding such as "ß" -> "ss")',
    'token_boundaries': (
        'A match is kept only if the code point after it is neither alphanumeric, "_" nor a combining mark '
        '(so a mark modifying the last letter blocks it), and the nearest preceding code point that is not a '
        'combining mark is neither alphanumeric nor "_" (so emoji, variation selectors, punctuation and spaces '
        'before a cue do not block it). Suffix rules ("n\'t") instead require an alphanumeric host before them.'
    ),
    'multiword_separator': 'one or more code points matched by Python re "\\s" (includes space, TAB, CR, LF, NBSP)',
    'unicode_forms': (
        'each phrase is searched as listed, in NFC and in NFD; the input is never normalized, so partially '
        'decomposed text and compatibility characters (ligatures, full-width letters) do not match'
    ),
    'overlaps': 'every match of every rule is reported; overlapping matches list each other in "overlaps"',
    'offsets': (
        'start/end: half-open Python str code-point indices (not UTF-16 units, not grapheme clusters); '
        'byte_start/byte_end: half-open UTF-8 byte indices into the same text'
    ),
}


class CueInputError(ValueError):
    """Invalid input; `code` is a stable machine-readable reason, `details` extra integer fields of the error."""

    def __init__(self, code: str, message: str, **details: int) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message
        self.details = details


class _Rule:
    def __init__(self, raw: Dict[str, Any]) -> None:
        self.id: str = raw['id']
        self.lang: str = raw['lang']
        self.topics: List[str] = list(raw['topics'])
        self.notes: List[str] = list(raw.get('notes', []))
        self.boundary: str = raw.get('boundary', 'word')
        if self.boundary not in ('word', 'suffix') or self.lang not in ('es', 'en') or not self.topics:
            raise ValueError(f'invalid rule {self.id!r}')
        # (phrase as listed, forms that produce this search string, search string, compiled pattern)
        self.patterns: List[Tuple[str, List[str], str, 're.Pattern[str]']] = []
        for phrase in raw['phrases']:
            variants: List[Tuple[List[str], str]] = []
            for form, value in (
                ('as_listed', phrase),
                ('NFC', unicodedata.normalize('NFC', phrase)),
                ('NFD', unicodedata.normalize('NFD', phrase)),
            ):
                for forms, existing in variants:
                    if existing == value:
                        forms.append(form)
                        break
                else:
                    variants.append(([form], value))
            for forms, value in variants:
                regex = r'\s+'.join(re.escape(word) for word in value.split(' '))
                self.patterns.append((phrase, forms, value, re.compile(regex, re.IGNORECASE)))


class Ruleset:
    """A loaded, validated and compiled rule file with its exact identity."""

    def __init__(self, raw_bytes: bytes) -> None:
        data = json.loads(raw_bytes.decode('utf-8'))
        self.data = data
        self.file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.canonical_sha256 = hashlib.sha256(canonical).hexdigest()
        self.rules = [_Rule(r) for r in data['rules']]
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate rule ids')

    @classmethod
    def from_path(cls, path: Path) -> 'Ruleset':
        return cls(Path(path).read_bytes())


_DEFAULT: Optional[Ruleset] = None


def default_ruleset() -> Ruleset:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Ruleset.from_path(DEFAULT_RULES_PATH)
    return _DEFAULT


def _is_word(ch: str) -> bool:
    return ch.isalnum() or ch == '_'


def _is_mark(ch: str) -> bool:
    return unicodedata.category(ch).startswith('M')


def _boundary_ok(text: str, start: int, end: int, boundary: str) -> bool:
    if end < len(text) and (_is_word(text[end]) or _is_mark(text[end])):
        return False
    k = start - 1
    while k >= 0 and _is_mark(text[k]):
        k -= 1
    host_is_word = k >= 0 and _is_word(text[k])
    return host_is_word if boundary == 'suffix' else not host_is_word


def _case_of(s: str) -> str:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 'no letters'
    if all(c.isupper() for c in letters):
        return 'upper' if len(letters) > 1 else 'single upper-case letter'
    if all(c.islower() for c in letters):
        return 'lower'
    if letters[0].isupper() and all(c.islower() for c in letters[1:]):
        return 'title'
    return 'mixed'


def _observations(s: str, forms: List[str], search_string: str) -> List[str]:
    obs = [f'letter case of the match: {_case_of(s)}']
    if re.sub(r'\s+', ' ', s).lower() != search_string.lower():
        obs.append(
            'matched through a Unicode case equivalence beyond simple lower-casing '
            '(e.g. dotted "\u0130", dotless "\u0131", long "\u017f"); check the characters'
        )
    if '\r' in s or '\n' in s:
        obs.append('the match spans a line break (CR and/or LF are part of the returned substring)')
    if any(c.isspace() and c != ' ' for c in s if c not in '\r\n'):
        obs.append('the match contains whitespace other than U+0020 (e.g. NBSP or TAB)')
    if 'NFD' in forms and 'NFC' not in forms:
        obs.append('matched the decomposed (NFD) spelling of the phrase')
    return obs


def _validate(text: Any, language: Any) -> bytes:
    if not isinstance(text, str):
        raise CueInputError('text_not_string', f'"text" must be a string, got {type(text).__name__}')
    if language not in LANGUAGES:
        raise CueInputError('invalid_language', f'"language" must be one of {list(LANGUAGES)}, got {language!r}')
    if len(text) > MAX_TEXT_CODEPOINTS:
        raise CueInputError('text_too_long', f'text has {len(text)} code points; the limit is {MAX_TEXT_CODEPOINTS}')
    try:
        return text.encode('utf-8', 'strict')
    except UnicodeEncodeError as e:
        raise CueInputError(
            'text_not_utf8_encodable',
            f'code point U+{ord(text[e.start]):04X} at index {e.start} cannot be encoded as UTF-8 (lone surrogate)',
        ) from None


def _overlap_lists(spans: Sequence[Tuple[int, int]]) -> List[List[int]]:
    """List, for each span i, the ascending indices j != i with start_j < end_i and start_i < end_j.

    `spans` are (start, end) pairs sorted by (start, end). Because starts never decrease, the later spans
    meeting span i are exactly those from i + 1 up to the first start >= end_i (found by bisection); each
    such pair is also recorded on the later span, in ascending order. Cost: O(n log n) plus the number of
    overlapping pairs, so disjoint spans are never compared with each other.
    """
    starts = [start for start, _ in spans]
    lists: List[List[int]] = [[] for _ in spans]
    for i, (_, end) in enumerate(spans):
        later = range(i + 1, bisect.bisect_left(starts, end, i + 1))
        for j in later:
            lists[j].append(i)
        lists[i].extend(later)
    return lists


def _overlap_pair_count(spans: Sequence[Tuple[int, int]]) -> int:
    """The number of overlapping pairs _overlap_lists(spans) would record, without building the lists."""
    starts = [start for start, _ in spans]
    return sum(bisect.bisect_left(starts, end, i + 1) - i - 1 for i, (_, end) in enumerate(spans))


def _compact_size(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode('utf-8'))


_BASIS = 'lexical match of a configured phrase; unvalidated as to meaning'
# The smallest possible match object. Every real match has these keys with values that serialize to at least as
# many bytes (strings >= "", offsets >= 0, lists >= [], the same basis), and indentation only adds bytes, so its
# compact size is a lower bound for each match in the rendered output.
_MATCH_TEMPLATE: Dict[str, Any] = {
    'text': '',
    'start': 0,
    'end': 0,
    'byte_start': 0,
    'byte_end': 0,
    'review_topics': [],
    'rule_id': '',
    'rule_language': '',
    'phrase': '',
    'matched_forms': [],
    'uncertainty': {'basis': _BASIS, 'rule_notes': [], 'observations': []},
    'overlaps': [],
}
_MATCH_FLOOR_BYTES = _compact_size(_MATCH_TEMPLATE)


def _too_large(max_output_bytes: int, at_least: int) -> CueInputError:
    at_least = min(at_least, MAX_OUTPUT_BYTES + 1)  # still a true lower bound, and at most 16 digits
    return CueInputError(
        'output_too_large',
        f'the complete output needs at least {at_least} bytes, more than max_output_bytes ({max_output_bytes}); '
        'no partial output is returned',
        max_output_bytes=max_output_bytes,
        output_bytes_at_least=at_least,
    )


def find_cues(text: str, language: str, ruleset: Optional[Ruleset] = None) -> Dict[str, Any]:
    """Return lexical cue candidates in `text`. Pure: same inputs -> same output; no I/O beyond the rule file."""
    return _find_cues(text, language, ruleset, None)


def _find_cues(text: str, language: str, ruleset: Optional[Ruleset], max_output_bytes: Optional[int]) -> Dict[str, Any]:
    """find_cues(); with a budget, raise output_too_large as soon as a lower bound of the rendered size exceeds it.

    The lower bound is the compact size of the result without matches, plus the final newline, plus
    _MATCH_FLOOR_BYTES per match and one byte per overlap reference; it is checked while matches are found and
    again before the overlap lists are built, so neither grows far beyond what the budget could hold.
    """
    encoded = _validate(text, language)
    rules = ruleset or default_ruleset()
    langs = ('es', 'en') if language == 'es+en' else (language,)
    configuration = {
        'language': language,
        'rule_languages_applied': list(langs),
        'max_text_codepoints': MAX_TEXT_CODEPOINTS,
        'unicode_database_version': unicodedata.unidata_version,
        'matching': MATCHING,
    }
    identity = {
        'schema': SCHEMA,
        'tool_version': TOOL_VERSION,
        'ruleset_canonical_sha256': rules.canonical_sha256,
        'configuration': configuration,
    }
    result: Dict[str, Any] = {
        'schema': SCHEMA,
        'tool': {'name': TOOL_NAME, 'version': TOOL_VERSION},
        'ruleset': {
            'id': rules.data['ruleset_id'],
            'version': rules.data['ruleset_version'],
            'file_sha256': rules.file_sha256,
            'canonical_sha256': rules.canonical_sha256,
        },
        'configuration': configuration,
        'configuration_sha256': hashlib.sha256(
            json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        ).hexdigest(),
        'input': {'sha256': hashlib.sha256(encoded).hexdigest(), 'codepoints': len(text), 'utf8_bytes': len(encoded)},
        'match_count': 0,
        'matches': [],
        'notice': NOTICE,
    }
    floor = 0 if max_output_bytes is None else _compact_size(result) + 1

    byte_at = [0] * (len(text) + 1)
    for i, ch in enumerate(text):
        byte_at[i + 1] = byte_at[i] + len(ch.encode('utf-8'))

    found: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for rule in rules.rules:
        if rule.lang not in langs:
            continue
        for phrase, forms, value, pattern in rule.patterns:
            pos = 0
            while True:
                m = pattern.search(text, pos)
                if m is None:
                    break
                pos = m.start() + 1  # keep scanning from the next code point, so no candidate is skipped
                start, end = m.start(), m.end()
                if not _boundary_ok(text, start, end, rule.boundary):
                    continue
                key = (rule.id, start, end)
                if key in found:
                    found[key]['matched_forms'] = sorted(set(found[key]['matched_forms']) | set(forms))
                    continue
                found[key] = {
                    'text': text[start:end],
                    'start': start,
                    'end': end,
                    'byte_start': byte_at[start],
                    'byte_end': byte_at[end],
                    'review_topics': list(rule.topics),
                    'rule_id': rule.id,
                    'rule_language': rule.lang,
                    'phrase': phrase,
                    'matched_forms': list(forms),
                    '_search_string': value,
                }
                if max_output_bytes is not None and floor + len(found) * _MATCH_FLOOR_BYTES > max_output_bytes:
                    raise _too_large(max_output_bytes, floor + len(found) * _MATCH_FLOOR_BYTES)
    matches = sorted(found.values(), key=lambda m: (m['start'], m['end'], m['rule_id']))
    spans = [(m['start'], m['end']) for m in matches]
    if max_output_bytes is not None:
        floor += len(matches) * _MATCH_FLOOR_BYTES + 2 * _overlap_pair_count(spans)
        if floor > max_output_bytes:
            raise _too_large(max_output_bytes, floor)
    rules_by_id = {r.id: r for r in rules.rules}
    for m, overlaps in zip(matches, _overlap_lists(spans)):
        m['uncertainty'] = {
            'basis': _BASIS,
            'rule_notes': list(rules_by_id[m['rule_id']].notes),
            'observations': _observations(m['text'], m['matched_forms'], m.pop('_search_string')),
        }
        m['overlaps'] = overlaps
    result['match_count'] = len(matches)
    result['matches'] = matches
    return result


def _check_output_budget(max_output_bytes: Any) -> None:
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or not MIN_OUTPUT_BYTES <= max_output_bytes <= MAX_OUTPUT_BYTES
    ):
        raise CueInputError(
            'invalid_output_budget',
            f'max_output_bytes must be an integer from {MIN_OUTPUT_BYTES} to {MAX_OUTPUT_BYTES}',
        )


def render_cues(
    text: str, language: str, ruleset: Optional[Ruleset] = None, max_output_bytes: Optional[int] = None
) -> bytes:
    """Return exactly the bytes the CLI writes for a successful request: UTF-8 JSON (indent 2) and a final "\\n".

    With `max_output_bytes`, the result is either those same bytes, if they fit, or CueInputError
    'output_too_large' (never a partial result); 'invalid_output_budget' if the budget is not an int from
    MIN_OUTPUT_BYTES to MAX_OUTPUT_BYTES. Rendering stops at the first byte over the budget.
    """
    if max_output_bytes is None:
        return (json.dumps(find_cues(text, language, ruleset), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _check_output_budget(max_output_bytes)
    result = _find_cues(text, language, ruleset, max_output_bytes)
    chunks: List[bytes] = []
    size = 1  # the final newline
    for piece in _INDENTED.iterencode(result):
        chunk = piece.encode('utf-8')
        size += len(chunk)
        if size > max_output_bytes:
            raise _too_large(max_output_bytes, size)
        chunks.append(chunk)
    chunks.append(b'\n')
    return b''.join(chunks)


def _reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CueInputError('duplicate_key', f'JSON object repeats the key {key!r}')
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise CueInputError('invalid_json_constant', f'{name} is not valid JSON')


def read_request(stream: BinaryIO, limit: int = MAX_REQUEST_BYTES) -> bytes:
    """Read a CLI request in bounded chunks: never more than `limit` + 1 bytes, and reject it if it is larger."""
    chunks: List[bytes] = []
    remaining = limit + 1
    while remaining > 0:
        chunk = stream.read(min(remaining, _READ_CHUNK_BYTES))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    if remaining <= 0:
        raise CueInputError('request_too_large', f'the request is larger than {limit} bytes; nothing was parsed')
    return b''.join(chunks)


def _reject_deep_nesting(decoded: str) -> None:
    """Count brackets outside JSON strings (an unterminated string runs to the end) without parsing."""
    depth = 0
    for token in _JSON_STRING_OR_BRACKET.finditer(decoded):
        if token.group() in ('[', '{'):
            depth += 1
            if depth > MAX_JSON_NESTING:
                raise CueInputError(
                    'json_too_deep', f'JSON nesting is deeper than {MAX_JSON_NESTING} levels; nothing was parsed'
                )
        elif token.group() in (']', '}'):
            depth -= 1


def _parse_int(literal: str) -> Any:
    """Parse a JSON integer; literals over MAX_INT_DIGITS digits become an exact Decimal, never an int.

    int() of a long decimal string costs quadratic time where CPython has no conversion limit (e.g. 3.9.6)
    and raises ValueError where it has one (4,300 digits by default; never fewer than 640). No request
    field accepts a number, so the request is rejected with the same code either way (e.g. text_not_string).
    """
    if len(literal) - literal.startswith('-') > MAX_INT_DIGITS:
        return decimal.Decimal(literal)
    return int(literal)


def parse_request(raw: bytes) -> Dict[str, Any]:
    """Strictly parse a CLI request: UTF-8 bytes, one JSON object, exactly the fields text and language."""
    try:
        decoded = raw.decode('utf-8', 'strict')
    except UnicodeDecodeError as e:
        raise CueInputError('stdin_not_utf8', f'input is not valid UTF-8 (byte {e.start})') from None
    _reject_deep_nesting(decoded)
    try:
        request = json.loads(
            decoded, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant, parse_int=_parse_int
        )
    except json.JSONDecodeError as e:
        raise CueInputError('invalid_json', f'{e.msg} at line {e.lineno} column {e.colno}') from None
    if not isinstance(request, dict):
        raise CueInputError('request_not_object', 'the request must be a JSON object')
    missing = [k for k in REQUEST_FIELDS if k not in request]
    unknown = sorted(k for k in request if k not in REQUEST_FIELDS)
    if missing:
        raise CueInputError('missing_field', f'missing field(s): {missing}')
    if unknown:
        raise CueInputError('unknown_field', f'unknown field(s): {unknown}')
    return request


def _error_output(e: CueInputError, max_output_bytes: Optional[int]) -> bytes:
    """The CLI's rejection envelope; under a budget it omits a message that would not fit (MIN_OUTPUT_BYTES)."""
    error: Dict[str, Any] = {'code': e.code, 'message': e.message, **e.details}
    data = (json.dumps({'schema': SCHEMA, 'error': error}, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if max_output_bytes is not None and len(data) > max_output_bytes:
        error['message'] = _OMITTED_MESSAGE
        data = (json.dumps({'schema': SCHEMA, 'error': error}, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return data


def main(
    argv: Optional[Sequence[str]] = None,
    stdin: Optional[BinaryIO] = None,
    stdout: Optional[BinaryIO] = None,
    stderr: Optional[BinaryIO] = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    in_stream = stdin if stdin is not None else sys.stdin.buffer
    out_stream = stdout if stdout is not None else sys.stdout.buffer
    options = dict(zip(args[::2], args[1::2]))
    well_formed = len(args) == 2 * len(options) and set(options) <= {'--rules', '--max-output-bytes'}
    max_output_bytes: Optional[int] = None
    if '--max-output-bytes' in options:
        value = options['--max-output-bytes']
        max_output_bytes = int(value) if _OUTPUT_BUDGET_ARG.fullmatch(value) else 0
        if max_output_bytes < MIN_OUTPUT_BYTES:
            # no usable budget: write nothing to stdout, so even a budget below MIN_OUTPUT_BYTES is respected
            error = CueInputError(
                'invalid_output_budget',
                f'--max-output-bytes must be a decimal integer from {MIN_OUTPUT_BYTES} to {MAX_OUTPUT_BYTES} '
                'without sign, spaces or leading zeros; nothing was written to stdout',
            )
            err_stream = stderr if stderr is not None else sys.stderr.buffer
            err_stream.write(_error_output(error, None))
            err_stream.flush()
            return 2
    try:
        if not well_formed:
            raise CueInputError('invalid_arguments', CLI_USAGE)
        ruleset = Ruleset.from_path(Path(options['--rules'])) if '--rules' in options else None
        request = parse_request(read_request(in_stream))
        output = render_cues(request['text'], request['language'], ruleset, max_output_bytes)
        status = 0
    except CueInputError as e:
        output = _error_output(e, max_output_bytes)
        status = 2
    out_stream.write(output)
    out_stream.flush()
    return status


if __name__ == '__main__':
    sys.exit(main())
