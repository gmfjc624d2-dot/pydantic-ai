"""Compare a plain-text export and a Markdown export of one research answer. Standard library only; Python >= 3.9.

Function: compare_exports(plain: bytes, markdown: bytes, **options) -> dict      (raises CompareError)
CLI:      python3 export_compare.py --plain PLAIN.txt --markdown EXPORT.md [options] > result.json
          exit 0: normalized bodies, cited ids and their URLs agree; 1: differences; 2: rejected input.

A deterministic textual aid under a narrow, stated normalization policy for two known layouts. It never
establishes authenticity, question identity, truth, completeness of evidence or semantic equivalence:
`semantic_judgment` is always NOT_ESTABLISHED. Inputs are read, never rewritten. See CONTRACT.md.
"""

from __future__ import annotations

import argparse
import bisect
import collections
import difflib
import hashlib
import json
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = 'export-compare/1'
TOOL_NAME = 'export_compare'
TOOL_VERSION = '1.0.1'
POLICY_ID = 'export-compare-body-policy/1'

MAX_DOCUMENT_BYTES = 262_144
MAX_DOCUMENT_LINES = 2_000
MAX_QUESTION_BYTES = 4_096
MAX_REQUEST_ID_BYTES = 256
MAX_REPORTED_DIFFERENCES = 100
MAX_WORD_DIFF_CHARS = 2_000
MAX_OUTPUT_BYTES = 4_194_304
MAX_EXCERPT_CHARS = 200

# The citation token both marker syntaxes become; documents containing these two characters are rejected.
CITE_OPEN, CITE_CLOSE = chr(0x27E6), chr(0x27E7)

POLICY_RULES = {
    'citation_markers': (
        'outside protected text, "[N]" in the plain body and "[^N]" not followed by ":" in the Markdown body '
        '(N = 1..9999 without leading zeros, not preceded by a backslash, plain form not followed by "(") '
        'both become one citation token for N'
    ),
    'escaped_hash': 'outside protected text, "\\#" in the Markdown body becomes "#"',
    'table_separator_rows': (
        'the delimiter row directly under a table header row (same cell count) becomes "|---|" form, keeping '
        'alignment colons; header and data rows are not changed'
    ),
    'blank_lines': (
        'outside code, whitespace-only lines are blank; a run of blank lines becomes one empty line and blank '
        'lines at the start and end of the body are dropped'
    ),
}
PROTECTED = [
    'fenced code blocks (``` or ~~~ fences, fence lines included)',
    'lines indented by 4 spaces or a tab (treated as code wherever they occur)',
    'inline code spans (matching backtick runs, also across lines of one paragraph)',
    'URLs: "http://" or "https://" up to the next whitespace',
    'everything outside the two body segments (preamble, question, logo, sources, definitions)',
]
UNSAFE_RULES = {
    'case_fold': 'turns changed identifiers into matches ("ID-a1" and "ID-A1")',
    'unicode_nfc': 'merges composed and decomposed spellings that code, identifiers or URLs may keep apart on purpose',
    'unicode_nfkc': 'changes numbers and symbols ("x²" becomes "x2", "①" becomes "1")',
    'collapse_inline_whitespace': 'two trailing spaces are a Markdown hard line break, and whitespace in code is content',
    'join_paragraphs': 'paragraph separation would no longer be compared',
    'ignore_line_order': 'a reordered list or sequence of steps would match',
    'resolve_citations_by_url': 'two ids pointing to the same URL would hide a changed citation target',
    'url_normalization': 'lower-casing, dropping a trailing slash or reordering a query can change the resource',
    'normalize_inside_code': 'code is literal: a marker or escape inside code is content',
    'strip_markdown_formatting': 'removes emphasis, links and escapes broadly and can hide changed link targets',
    'ignore_numbers': 'a changed numeral would match',
}
NOT_ESTABLISHED = [
    'semantic equivalence',
    'producer authenticity',
    'question identity',
    'truth',
    'completeness of evidence',
]
NOTICE = (
    'Equal normalized bodies and URL maps are a textual agreement under the stated policy. They do not establish '
    'authenticity, that both exports answer the same question, truth, or that the evidence is complete. Source '
    'titles exist only in the plain export, and listed or defined entries are not evidence that anything cites them.'
)

SOURCES_HEADING = 'Sources'
SOURCE_ENTRY = re.compile(r'([1-9][0-9]{0,3})\. (\S.*?) (https?://\S+)')
NEAR_SOURCES = re.compile(r'\W*sources\W*', re.IGNORECASE)
LOGO = re.compile(r'!\[[^\]]*\]\((https?://[^\s)]+)\)')
H1 = re.compile(r'# (\S.*)')
DEFINITION = re.compile(r'\[\^([1-9][0-9]{0,3})\]: (\S+)')
DEFINITION_LIKE = re.compile(r' {0,3}\[\^[^\]\s]+\]:')
SPAN_OPEN = '<span style="display:none">'
SPAN_CLOSE = '</span>'
URL = re.compile(r'https?://\S+')
FENCE_OPEN = re.compile(r'( {0,3})(`{3,}|~{3,})(.*)')
FENCE_CLOSE = re.compile(r' {0,3}(`{3,}|~{3,})[ \t]*')
PLAIN_MARKER = re.compile(r'(?<!\\)\[([1-9][0-9]{0,3})\](?!\()')
MARKDOWN_MARKER = re.compile(r'(?<!\\)\[\^([1-9][0-9]{0,3})\](?!:)')
ANY_MARKER = re.compile(r'\[\^?[0-9]+\]')
DELIMITER_CELL = re.compile(r'\s*(:?)-+(:?)\s*')
FORBIDDEN_CHARACTER = re.compile('[\x00-\x08\x0b-\x1f\x7f]')
TOKEN = re.compile(r'\s+|\w+|[^\w\s]')


class CompareError(ValueError):
    """Rejected input or layout; `code` is a stable machine-readable reason, `details` small extra fields."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message
        self.details = details


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _excerpt(text: str) -> str:
    return text if len(text) <= MAX_EXCERPT_CHARS else text[:MAX_EXCERPT_CHARS] + '...'


class _Document:
    """One decoded export: its raw bytes, LF-separated lines, line byte offsets and a code/text kind per line."""

    def __init__(self, name: str, raw: bytes) -> None:
        if not isinstance(raw, (bytes, bytearray)):
            raise CompareError('input_not_bytes', f'{name} must be bytes, got {type(raw).__name__}', document=name)
        raw = bytes(raw)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise CompareError(
                'input_too_large',
                f'{name} has {len(raw)} bytes; the limit is {MAX_DOCUMENT_BYTES}',
                document=name,
                limit=MAX_DOCUMENT_BYTES,
            )
        if raw.startswith(b'\xef\xbb\xbf'):
            raise CompareError('unsupported_bom', f'{name} starts with a UTF-8 byte order mark', document=name)
        try:
            text = raw.decode('utf-8', 'strict')
        except UnicodeDecodeError as e:
            raise CompareError('not_utf8', f'{name} is not valid UTF-8 (byte {e.start})', document=name) from None
        bad = FORBIDDEN_CHARACTER.search(text)
        if bad:
            code = 'unsupported_line_ending' if bad.group() == '\r' else 'unsupported_control_character'
            line = text.count('\n', 0, bad.start()) + 1
            raise CompareError(
                code, f'{name} contains U+{ord(bad.group()):04X} on line {line}', document=name, line=line
            )
        if CITE_OPEN in text or CITE_CLOSE in text:
            raise CompareError(
                'reserved_character',
                f'{name} contains U+27E6 or U+27E7, which this tool reserves for citation tokens',
                document=name,
            )
        self.name = name
        self.raw = raw
        self.final_newline = text.endswith('\n')
        self.lines = text.split('\n') if text else []
        if self.final_newline:
            self.lines.pop()
        if len(self.lines) > MAX_DOCUMENT_LINES:
            raise CompareError(
                'input_too_large',
                f'{name} has {len(self.lines)} lines; the limit is {MAX_DOCUMENT_LINES}',
                document=name,
                limit=MAX_DOCUMENT_LINES,
            )
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line.encode('utf-8')) + 1)
        self.starts[-1] = len(raw)
        self.kinds = _classify_lines(name, self.lines)

    def segment_bytes(self, first: int, end: int) -> bytes:
        """The raw bytes of lines [first, end) (0-based), including their line endings as they are in the input."""
        return self.raw[self.starts[first] : self.starts[end]]

    def segment(self, name: str, first: int, end: int, **extra: Any) -> Dict[str, Any]:
        """Lines [first, end) (0-based) as a byte-exact segment of the raw input."""
        return {
            'name': name,
            'first_line': first + 1 if end > first else None,
            'last_line': end if end > first else None,
            'byte_start': self.starts[first],
            'byte_end': self.starts[end],
            'sha256': _sha256(self.segment_bytes(first, end)),
            **extra,
        }

    def text(self, first: int, end: int) -> str:
        return '\n'.join(self.lines[first:end])


def _classify_lines(name: str, lines: Sequence[str]) -> List[str]:
    """'code' for fenced code (fences included), 'indented' for lines indented by 4 spaces or a tab, else 'text'."""
    kinds: List[str] = []
    fence: Optional[Tuple[str, int, int]] = None
    for i, line in enumerate(lines):
        if fence is not None:
            kinds.append('code')
            close = FENCE_CLOSE.fullmatch(line)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= fence[1]:
                fence = None
            continue
        opening = FENCE_OPEN.fullmatch(line)
        if opening and not (opening.group(2)[0] == '`' and '`' in opening.group(3)):
            fence = (opening.group(2)[0], len(opening.group(2)), i)
            kinds.append('code')
        elif line.strip() and (line.startswith('    ') or line.startswith('\t')):
            kinds.append('indented')
        else:
            kinds.append('text')
    if fence is not None:
        raise CompareError(
            'unclosed_code_fence',
            f'{name} has a code fence opened on line {fence[2] + 1} and never closed',
            document=name,
            line=fence[2] + 1,
        )
    return kinds


def _line_index(option: str, value: Any, count: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= count:
        raise CompareError('invalid_boundary', f'{option} must be a line number from 1 to {count}', option=option)
    return value - 1


def _parse_plain(doc: _Document, body_start: Optional[int], sources_line: Optional[int]) -> Dict[str, Any]:
    """Plain layout: [preamble] body, one line that is exactly "Sources", then "N. title URL" entries."""
    n = len(doc.lines)
    first = 0 if body_start is None else _line_index('plain_body_start', body_start, n)
    if sources_line is None:
        found = [i for i in range(first, n) if doc.kinds[i] == 'text' and doc.lines[i] == SOURCES_HEADING]
        if not found:
            near = [i + 1 for i in range(n) if doc.kinds[i] == 'text' and NEAR_SOURCES.fullmatch(doc.lines[i])]
            raise CompareError(
                'boundary_not_found',
                'the plain export has no line that is exactly "Sources" outside code; it is not in the supported layout',
                document='plain',
                near_miss_lines=near[:50],
            )
        if len(found) > 1:
            raise CompareError(
                'ambiguous_boundary',
                'the plain export has more than one "Sources" line outside code; pass plain_sources_line',
                document='plain',
                lines=[i + 1 for i in found][:50],
            )
        k = found[0]
    else:
        k = _line_index('plain_sources_line', sources_line, n)
        if k < first or doc.kinds[k] != 'text' or doc.lines[k] != SOURCES_HEADING:
            raise CompareError(
                'invalid_boundary',
                f'plain_sources_line {sources_line} is not a "Sources" line outside code at or after the body start',
                option='plain_sources_line',
            )
    sources: Dict[int, Dict[str, Any]] = {}
    for i in range(k + 1, n):
        line = doc.lines[i]
        if not line.strip():
            continue
        entry = SOURCE_ENTRY.fullmatch(line) if doc.kinds[i] == 'text' else None
        if entry is None:
            raise CompareError(
                'unsupported_bibliography_line',
                f'plain line {i + 1} after "Sources" is not "N. title URL"',
                document='plain',
                line=i + 1,
                text=_excerpt(line),
            )
        number = int(entry.group(1))
        if number in sources:
            raise CompareError(
                'duplicate_source_number',
                f'source {number} is listed on lines {sources[number]["line"]} and {i + 1}',
                document='plain',
                id=number,
                lines=[sources[number]['line'], i + 1],
                urls=[sources[number]['url'], entry.group(3)],
            )
        sources[number] = {'title': entry.group(2), 'url': entry.group(3), 'line': i + 1}
    segments = [
        doc.segment('preamble', 0, first),
        doc.segment('body', first, k),
        doc.segment('sources', k, n, heading_line=k + 1),
    ]
    return {'body': (first, k), 'preamble': (0, first), 'sources': sources, 'segments': segments}


def _definition_block_line(line: str) -> Optional[Tuple[bool, Optional[re.Match[str]], bool]]:
    """(opens a display:none span, definition match, closes the span), or None if not a definition-block line."""
    opens = line.startswith(SPAN_OPEN)
    rest = line[len(SPAN_OPEN) :] if opens else line
    closes = rest.endswith(SPAN_CLOSE)
    rest = rest[: -len(SPAN_CLOSE)] if closes else rest
    if not rest.strip():
        return (opens, None, closes) if (opens or closes or not line.strip()) else None
    definition = DEFINITION.fullmatch(rest)
    return (opens, definition, closes) if definition else None


def _markdown_prelude(doc: _Document, body_start: Optional[int]) -> Tuple[int, Optional[int], Optional[int]]:
    """(first body line, logo line, question line), 0-based; recognized, or validated against body_start."""
    lines, kinds, n = doc.lines, doc.kinds, len(doc.lines)
    logo: Optional[int] = None
    question: Optional[int] = None
    if body_start is not None:
        first = _line_index('markdown_body_start', body_start, n)
        for k in range(first):
            if kinds[k] == 'text' and not lines[k].strip():
                continue
            if k == 0 and kinds[k] == 'text' and LOGO.fullmatch(lines[k]):
                logo = 0
            elif question is None and kinds[k] == 'text' and H1.fullmatch(lines[k]):
                question = k
            else:
                raise CompareError(
                    'unsupported_prelude_line',
                    f'Markdown line {k + 1} before the body is not a logo, the one "# " question heading or blank',
                    document='markdown',
                    line=k + 1,
                    text=_excerpt(lines[k]),
                )
        return first, logo, question
    i = 0
    if n and kinds[0] == 'text' and LOGO.fullmatch(lines[0]):
        logo, i = 0, 1
    while i < n and kinds[i] == 'text' and not lines[i].strip():
        i += 1
    if i < n and kinds[i] == 'text' and H1.fullmatch(lines[i]):
        headings = [k + 1 for k in range(n) if kinds[k] == 'text' and H1.fullmatch(lines[k])]
        if len(headings) > 1:
            raise CompareError(
                'ambiguous_question_heading',
                'the Markdown export starts with a "# " heading but has other "# " headings outside code; '
                'pass markdown_body_start',
                document='markdown',
                lines=headings[:50],
            )
        question, i = i, i + 1
    return (i if (logo is not None or question is not None) else 0), logo, question


def _markdown_block_start(doc: _Document, first: int, definitions_start: Optional[int]) -> int:
    """The first line of the trailing definition block (n if none); recognized, or validated."""
    lines, kinds, n = doc.lines, doc.kinds, len(doc.lines)
    if definitions_start is None:
        block = n
        while block > first and kinds[block - 1] == 'text' and _definition_block_line(lines[block - 1]) is not None:
            block -= 1
        while block < n and not lines[block].strip():
            block += 1
    else:
        block = _line_index('markdown_definitions_start', definitions_start, n)
        if block < first:
            raise CompareError(
                'invalid_boundary',
                'markdown_definitions_start is before the body start',
                option='markdown_definitions_start',
            )
        for k in range(block, n):
            if kinds[k] != 'text' or _definition_block_line(lines[k]) is None:
                raise CompareError(
                    'unsupported_definition_line',
                    f'Markdown line {k + 1} in the definitions is not "[^N]: URL", a display:none span tag or blank',
                    document='markdown',
                    line=k + 1,
                    text=_excerpt(lines[k]),
                )
    outside = [
        k + 1
        for k in range(first, block)
        if kinds[k] == 'text'
        and (
            DEFINITION_LIKE.match(lines[k])
            or (lines[k].startswith(SPAN_OPEN) and DEFINITION_LIKE.match(lines[k][len(SPAN_OPEN) :]))
        )
    ]
    if outside:
        raise CompareError(
            'definition_outside_block',
            'the Markdown body contains footnote definition lines outside code; only a trailing definition block is supported',
            document='markdown',
            lines=outside[:50],
        )
    return block


def _markdown_definitions(doc: _Document, block: int) -> Dict[int, Dict[str, Any]]:
    """Definitions from the block, each with its URL, line and whether it sits inside a display:none span."""
    definitions: Dict[int, Dict[str, Any]] = {}
    hidden = False
    for k in range(block, len(doc.lines)):
        parsed = _definition_block_line(doc.lines[k])
        assert parsed is not None
        opens, definition, closes = parsed
        if opens:
            if hidden:
                raise CompareError('unsupported_html', f'nested display:none span on Markdown line {k + 1}', line=k + 1)
            hidden = True
        if definition is not None:
            number, url = int(definition.group(1)), definition.group(2)
            if not URL.fullmatch(url):
                raise CompareError(
                    'unsupported_definition_line',
                    f'Markdown definition [^{number}] on line {k + 1} does not point to an http(s) URL',
                    document='markdown',
                    line=k + 1,
                    text=_excerpt(doc.lines[k]),
                )
            if number in definitions:
                raise CompareError(
                    'duplicate_definition',
                    f'[^{number}] is defined on lines {definitions[number]["line"]} and {k + 1}',
                    document='markdown',
                    id=number,
                    lines=[definitions[number]['line'], k + 1],
                    urls=[definitions[number]['url'], url],
                )
            definitions[number] = {'url': url, 'hidden': hidden, 'line': k + 1}
        if closes:
            if not hidden:
                raise CompareError(
                    'unsupported_html', f'"</span>" without an opening display:none span, line {k + 1}', line=k + 1
                )
            hidden = False
    if hidden:
        raise CompareError('unsupported_html', 'a display:none span in the definitions is never closed')
    return definitions


def _parse_markdown(doc: _Document, body_start: Optional[int], definitions_start: Optional[int]) -> Dict[str, Any]:
    """Markdown layout: [logo] [one "# question" heading] body, then trailing "[^N]: URL" definitions."""
    first, logo, question = _markdown_prelude(doc, body_start)
    block = _markdown_block_start(doc, first, definitions_start)
    definitions = _markdown_definitions(doc, block)
    logo_match = None if logo is None else LOGO.fullmatch(doc.lines[logo])
    question_match = None if question is None else H1.fullmatch(doc.lines[question])
    return {
        'body': (first, block),
        'logo': None if logo_match is None else logo_match.group(1),
        'question_line': question,
        'question': None if question_match is None else question_match.group(1),
        'definitions': definitions,
        'segments': [
            doc.segment(
                'prelude',
                0,
                first,
                logo_line=None if logo is None else logo + 1,
                question_line=None if question is None else question + 1,
            ),
            doc.segment('body', first, block),
            doc.segment('definitions', block, len(doc.lines)),
        ],
    }


def _protected_spans(text: str) -> List[Tuple[int, int]]:
    """Merged, sorted spans of URLs and inline code spans (backtick runs closed by a run of equal length)."""
    spans = [m.span() for m in URL.finditer(text)]
    runs = [m.span() for m in re.finditer(r'`+', text)]
    by_length: Dict[int, List[int]] = collections.defaultdict(list)
    for index, (start, end) in enumerate(runs):
        by_length[end - start].append(index)
    i = 0
    while i < len(runs):
        start, end = runs[i]
        same = by_length[end - start]
        position = bisect.bisect_right(same, i)
        if position < len(same):
            spans.append((start, runs[same[position]][1]))
            i = same[position] + 1
        else:
            i += 1
    return _merge_spans(spans)


def _merge_spans(spans: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    merged: List[Tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _overlaps(spans: List[Tuple[int, int]], starts: List[int], low: int, high: int) -> bool:
    """Whether any of the merged, sorted `spans` (whose starts are `starts`) overlaps [low, high)."""
    index = bisect.bisect_left(starts, high) - 1
    return index >= 0 and spans[index][1] > low


def _delimiter_row(line: str, header: str) -> Optional[str]:
    def cells(row: str) -> List[str]:
        row = row.strip()
        row = row[1:] if row.startswith('|') else row
        row = row[:-1] if row.endswith('|') and not row.endswith('\\|') else row
        return row.split('|')

    if '|' not in line or '|' not in header:
        return None
    parsed = [DELIMITER_CELL.fullmatch(cell) for cell in cells(line)]
    if not all(parsed) or len(parsed) != len(cells(header)):
        return None
    marks = [
        (':-:' if m.group(1) and m.group(2) else ':--' if m.group(1) else '--:' if m.group(2) else '---')
        for m in parsed
    ]  # type: ignore[union-attr]
    return '|' + '|'.join(marks) + '|'


class _Body:
    """The normalized body lines of one export with the raw line number of each, and what the policy did."""

    def __init__(self, doc: _Document, first: int, end: int, flavor: str, rules: Sequence[str]) -> None:
        own, foreign = (PLAIN_MARKER, MARKDOWN_MARKER) if flavor == 'plain' else (MARKDOWN_MARKER, PLAIN_MARKER)
        self.references: collections.Counter[int] = collections.Counter()
        self.counts = {'citation_markers': 0, 'escaped_hash': 0, 'table_separator_rows': 0, 'blank_lines_removed': 0}
        self.markers_in_code = 0
        self.foreign_markers = 0
        entries: List[Tuple[int, str, bool]] = []  # (raw line number, text, is blank)
        k = first
        while k < end:
            if doc.kinds[k] != 'text':
                self.markers_in_code += len(ANY_MARKER.findall(doc.lines[k]))
                entries.append((k + 1, doc.lines[k], False))
                k += 1
                continue
            if not doc.lines[k].strip():
                entries.append((k + 1, doc.lines[k], True))
                k += 1
                continue
            # An indented line cannot interrupt a paragraph, so the paragraph (and any code span in it) runs on
            # through indented lines up to a blank line or a fence; those indented lines stay literal.
            j = k + 1
            while j < end and doc.kinds[j] != 'code' and doc.lines[j].strip():
                j += 1
            for offset, line in enumerate(self._paragraph(doc, k, j, flavor, own, foreign, rules)):
                entries.append((k + 1 + offset, line, False))
            k = j
        if 'blank_lines' in rules:
            kept: List[Tuple[int, str, bool]] = []
            for number, text, blank in entries:
                if blank and (not kept or kept[-1][2]):
                    self.counts['blank_lines_removed'] += 1
                    continue
                kept.append((number, '' if blank else text, blank))
            while kept and kept[-1][2]:
                kept.pop()
                self.counts['blank_lines_removed'] += 1
            entries = kept
        self.line_numbers = [number for number, _, _ in entries]
        self.lines = [text for _, text, _ in entries]

    def _paragraph(
        self,
        doc: _Document,
        first: int,
        end: int,
        flavor: str,
        own: re.Pattern[str],
        foreign: re.Pattern[str],
        rules: Sequence[str],
    ) -> List[str]:
        text = doc.text(first, end)
        offsets = [0]  # character offset of each line in `text`, plus len(text) + 1
        for line in doc.lines[first:end]:
            offsets.append(offsets[-1] + len(line) + 1)
        indented = [i - first for i in range(first, end) if doc.kinds[i] == 'indented']
        for i in indented:
            self.markers_in_code += len(ANY_MARKER.findall(doc.lines[first + i]))
        # One set of protected spans serves every rule. An indented line is protected with the line break before it.
        protected = _merge_spans(_protected_spans(text) + [(offsets[i] - 1, offsets[i + 1] - 1) for i in indented])
        pieces, position = [], 0
        for start, stop in protected + [(len(text), len(text))]:
            pieces.append(self._inline(text[position:start], flavor, own, foreign, rules))
            pieces.append(text[start:stop])
            position = stop
        out = ''.join(pieces).split('\n')
        if 'table_separator_rows' in rules:
            starts = [start for start, _ in protected]
            for t in range(len(out) - 1):
                # A delimiter row counts only if the line break before its header row, the line break before
                # the row itself and the row are all unprotected: a code span may not run into or across them.
                if t and _overlaps(protected, starts, offsets[t] - 1, offsets[t]):
                    continue
                if _overlaps(protected, starts, offsets[t + 1] - 1, offsets[t + 2] - 1):
                    continue
                canonical = _delimiter_row(out[t + 1], out[t])
                if canonical is not None:
                    self.counts['table_separator_rows'] += 1
                    out[t + 1] = canonical
                    break  # the rest of this block is the table's data rows
        return out

    def _inline(
        self, text: str, flavor: str, own: re.Pattern[str], foreign: re.Pattern[str], rules: Sequence[str]
    ) -> str:
        self.foreign_markers += len(foreign.findall(text))
        for match in own.finditer(text):
            self.references[int(match.group(1))] += 1
        if 'citation_markers' in rules:
            text, count = own.subn(lambda m: f'{CITE_OPEN}cite {m.group(1)}{CITE_CLOSE}', text)
            self.counts['citation_markers'] += count
        if flavor == 'markdown' and 'escaped_hash' in rules:
            self.counts['escaped_hash'] += text.count('\\#')
            text = text.replace('\\#', '#')
        return text

    def sha256(self) -> str:
        return _sha256('\n'.join(self.lines).encode('utf-8'))


def _word_diff(a: str, b: str) -> List[Dict[str, str]]:
    ta, tb = TOKEN.findall(a), TOKEN.findall(b)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        entry = {'op': tag, 'plain': ''.join(ta[i1:i2]), 'markdown': ''.join(tb[j1:j2])}
        if not (entry['plain'] + entry['markdown']).isascii():
            entry['plain_ascii'], entry['markdown_ascii'] = ascii(entry['plain']), ascii(entry['markdown'])
        out.append(entry)
    return out


def _body_differences(plain: _Body, markdown: _Body) -> Tuple[int, List[Dict[str, Any]]]:
    opcodes = [
        op
        for op in difflib.SequenceMatcher(None, plain.lines, markdown.lines, autojunk=False).get_opcodes()
        if op[0] != 'equal'
    ]
    reported = []
    for tag, i1, i2, j1, j2 in opcodes[:MAX_REPORTED_DIFFERENCES]:
        entry: Dict[str, Any] = {
            'op': tag,
            'plain': [{'line': plain.line_numbers[i], 'text': plain.lines[i]} for i in range(i1, i2)],
            'markdown': [{'line': markdown.line_numbers[j], 'text': markdown.lines[j]} for j in range(j1, j2)],
        }
        if tag == 'replace' and i2 - i1 == 1 and j2 - j1 == 1:
            a, b = plain.lines[i1], markdown.lines[j1]
            if len(a) <= MAX_WORD_DIFF_CHARS and len(b) <= MAX_WORD_DIFF_CHARS:
                entry['words'] = _word_diff(a, b)
        reported.append(entry)
    return len(opcodes), reported


def _same_url(a: Optional[str], b: Optional[str]) -> bool:
    """Exact string equality: no case folding, trailing-slash, percent-encoding or query normalization."""
    return a is not None and a == b


def _url_difference(a: str, b: str) -> Dict[str, Any]:
    index = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return {'first_difference_at': index, 'plain_from_there': a[index:], 'markdown_from_there': b[index:]}


def _check_text(name: str, value: Any, limit: int, single_line: bool) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CompareError('invalid_option', f'{name} must be a string', option=name)
    try:
        encoded = value.encode('utf-8', 'strict')
    except UnicodeEncodeError:
        raise CompareError('invalid_option', f'{name} contains a lone surrogate', option=name) from None
    if len(encoded) > limit:
        raise CompareError(
            'input_too_large', f'{name} has {len(encoded)} bytes; the limit is {limit}', option=name, limit=limit
        )
    if not value or (single_line and '\n' in value) or FORBIDDEN_CHARACTER.search(value):
        raise CompareError('invalid_option', f'{name} must be non-empty text without control characters', option=name)
    return value


def _check_rules(rules: Optional[Sequence[str]]) -> List[str]:
    if rules is None:
        return list(POLICY_RULES)
    if isinstance(rules, str) or not all(isinstance(r, str) for r in rules):
        raise CompareError('invalid_option', 'rules must be a list of rule names', option='rules')
    unsafe = {r: UNSAFE_RULES[r] for r in rules if r in UNSAFE_RULES}
    if unsafe:
        raise CompareError(
            'unsafe_normalization',
            'requested normalization would turn real differences into matches: '
            + '; '.join(f'{k}: {v}' for k, v in unsafe.items()),
            rules=sorted(unsafe),
        )
    unknown = sorted(r for r in rules if r not in POLICY_RULES)
    if unknown:
        raise CompareError(
            'unknown_normalization', f'unknown rule(s); the policy has {list(POLICY_RULES)}', rules=unknown[:20]
        )
    return [r for r in POLICY_RULES if r in rules]


def _request_id_occurrences(
    request_id: str, question: Optional[str], p: _Document, pl: Dict[str, Any], m: _Document, ml: Dict[str, Any]
) -> Dict[str, Any]:
    """Literal, non-overlapping matches of the ID's UTF-8 bytes in each exact segment, whether or not a question exists."""
    needle = request_id.encode('utf-8')

    def count(doc: _Document, first: int, end: int) -> int:
        return doc.segment_bytes(first, end).count(needle)

    q_line = ml['question_line']
    occurrences = {
        'plain_document': p.raw.count(needle),
        'plain_preamble': count(p, *pl['preamble']),
        'plain_body': count(p, *pl['body']),
        'plain_sources': count(p, pl['body'][1], len(p.lines)),
        'markdown_document': m.raw.count(needle),
        'markdown_prelude': count(m, 0, ml['body'][0]),
        'markdown_question_heading': 0 if q_line is None else count(m, q_line, q_line + 1),
        'markdown_body': count(m, *ml['body']),
        'markdown_definitions': count(m, ml['body'][1], len(m.lines)),
        'supplied_question': 0 if question is None else question.encode('utf-8').count(needle),
    }
    return {
        'value': request_id,
        'counting': 'non-overlapping literal matches of its UTF-8 bytes; no case folding or Unicode normalization',
        'occurrences': occurrences,
        'present_in_plain_document': occurrences['plain_document'] > 0,
        'present_in_plain_body': occurrences['plain_body'] > 0,
        'present_in_markdown_document': occurrences['markdown_document'] > 0,
        'present_in_markdown_body': occurrences['markdown_body'] > 0,
        'present_in_markdown_question_heading': occurrences['markdown_question_heading'] > 0,
    }


def compare_exports(
    plain: bytes,
    markdown: bytes,
    *,
    question: Optional[str] = None,
    request_id: Optional[str] = None,
    plain_body_start: Optional[int] = None,
    plain_sources_line: Optional[int] = None,
    markdown_body_start: Optional[int] = None,
    markdown_definitions_start: Optional[int] = None,
    rules: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Compare two exports of one answer. Pure; raises CompareError for unsupported or ambiguous input."""
    applied = _check_rules(rules)
    question = _check_text('question', question, MAX_QUESTION_BYTES, single_line=False)
    request_id = _check_text('request_id', request_id, MAX_REQUEST_ID_BYTES, single_line=True)
    p, m = _Document('plain', plain), _Document('markdown', markdown)
    pl = _parse_plain(p, plain_body_start, plain_sources_line)
    ml = _parse_markdown(m, markdown_body_start, markdown_definitions_start)
    pb, mb = _Body(p, *pl['body'], 'plain', applied), _Body(m, *ml['body'], 'markdown', applied)
    difference_count, differences = _body_differences(pb, mb)

    sources, definitions = pl['sources'], ml['definitions']
    cited = sorted(set(pb.references) | set(mb.references))
    url_map = []
    for number in cited:
        a = sources.get(number, {}).get('url')
        b = definitions.get(number, {}).get('url')
        entry: Dict[str, Any] = {
            'id': number,
            'plain_url': a,
            'markdown_url': b,
            'equal': _same_url(a, b),
            'plain_references': pb.references[number],
            'markdown_references': mb.references[number],
        }
        if a is not None and b is not None and a != b:
            entry.update(_url_difference(a, b))
        url_map.append(entry)
    undefined = {
        'plain': sorted(set(pb.references) - set(sources)),
        'markdown': sorted(set(mb.references) - set(definitions)),
    }
    citations = {
        'referenced_ids_equal': set(pb.references) == set(mb.references),
        'reference_counts_equal': pb.references == mb.references,
        'url_map_equal': all(e['equal'] for e in url_map),
        'url_map': url_map,
        'all_entries_url_map_equal': set(sources) == set(definitions)
        and all(_same_url(sources[k]['url'], definitions[k]['url']) for k in sources),
        'undefined_references': undefined,
        'plain_listed_not_cited': [
            {'id': k, 'title': v['title'], 'url': v['url']}
            for k, v in sorted(sources.items())
            if k not in pb.references
        ],
        'markdown_defined_not_referenced': [
            {'id': k, 'url': v['url'], 'hidden': v['hidden']}
            for k, v in sorted(definitions.items())
            if k not in mb.references
        ],
        'plain_sources': [{'id': k, **v} for k, v in sorted(sources.items())],
        'markdown_definitions': [{'id': k, **v} for k, v in sorted(definitions.items())],
    }

    plain_question_source = 'preamble' if pl['preamble'][1] > 0 else ('supplied' if question is not None else 'absent')
    question_result: Dict[str, Any] = {
        'plain': {
            'source': plain_question_source,
            'preamble_text': p.text(*pl['preamble']) if pl['preamble'][1] > 0 else None,
            'supplied_text': question,
        },
        'markdown': {'source': 'heading' if ml['question'] is not None else 'absent', 'text': ml['question']},
        'supplied_equals_markdown_heading': None
        if question is None or ml['question'] is None
        else question == ml['question'],
    }
    request_id_result = None if request_id is None else _request_id_occurrences(request_id, question, p, pl, m, ml)

    warnings: List[Dict[str, Any]] = []
    titled = [s['id'] for s in citations['plain_sources'] if s['title']]
    if titled:
        warnings.append(
            {
                'code': 'source_titles_only_in_plain',
                'message': 'the plain export gives a title for each source; the Markdown definitions carry URLs only, so titles cannot be compared',
                'ids': titled,
            }
        )
    if citations['plain_listed_not_cited'] or citations['markdown_defined_not_referenced']:
        warnings.append(
            {
                'code': 'uncited_entries',
                'message': 'some listed sources or definitions are not referenced in the body; they are not cited evidence',
                'plain': [e['id'] for e in citations['plain_listed_not_cited']],
                'markdown': [e['id'] for e in citations['markdown_defined_not_referenced']],
            }
        )
    if undefined['plain'] or undefined['markdown']:
        warnings.append(
            {'code': 'undefined_references', 'message': 'a body cites an id with no source or definition', **undefined}
        )
    if question_result['plain']['source'] == 'absent' or question_result['markdown']['source'] == 'absent':
        warnings.append(
            {
                'code': 'question_absent',
                'message': 'at least one export carries no question; question identity cannot be compared',
            }
        )
    if pb.markers_in_code or mb.markers_in_code:
        warnings.append(
            {
                'code': 'markers_in_code_not_counted',
                'message': 'marker-like text inside code was compared literally and not counted as a citation',
                'plain': pb.markers_in_code,
                'markdown': mb.markers_in_code,
            }
        )
    if pb.foreign_markers or mb.foreign_markers:
        warnings.append(
            {
                'code': 'foreign_marker_syntax',
                'message': "a body uses the other export's marker syntax; such markers are not citations under this policy",
                'plain': pb.foreign_markers,
                'markdown': mb.foreign_markers,
            }
        )
    if p.final_newline != m.final_newline:
        warnings.append(
            {'code': 'final_newline_differs', 'message': 'one input ends with a newline and the other does not'}
        )
    if difference_count > MAX_REPORTED_DIFFERENCES:
        warnings.append(
            {
                'code': 'body_differences_truncated',
                'message': f'only the first {MAX_REPORTED_DIFFERENCES} of {difference_count} body differences are listed',
            }
        )
    if len(applied) < len(POLICY_RULES):
        warnings.append(
            {
                'code': 'policy_rules_disabled',
                'message': 'the caller disabled policy rules, so more differences are expected',
                'disabled': [r for r in POLICY_RULES if r not in applied],
            }
        )

    return {
        'schema': SCHEMA,
        'tool': {'name': TOOL_NAME, 'version': TOOL_VERSION},
        'inputs': {
            doc.name: {
                'sha256': _sha256(doc.raw),
                'bytes': len(doc.raw),
                'lines': len(doc.lines),
                'final_newline': doc.final_newline,
            }
            for doc in (p, m)
        },
        'layouts': {
            'plain': {'layout': 'plain-numbered-sources/1', 'segments': pl['segments']},
            'markdown': {
                'layout': 'markdown-footnote-definitions/1',
                'logo_url': ml['logo'],
                'segments': ml['segments'],
            },
            'boundaries': {
                'plain_body_start': plain_body_start,
                'plain_sources_line': plain_sources_line,
                'markdown_body_start': markdown_body_start,
                'markdown_definitions_start': markdown_definitions_start,
            },
        },
        'normalization': {
            'policy': POLICY_ID,
            'rules_applied': applied,
            'rules': POLICY_RULES,
            'never_applied_to': PROTECTED,
            'counts': {'plain': pb.counts, 'markdown': mb.counts},
            'normalized_body_sha256': {'plain': pb.sha256(), 'markdown': mb.sha256()},
            'normalized_body_lines': {'plain': len(pb.lines), 'markdown': len(mb.lines)},
        },
        'results': {
            'raw_documents_equal': p.raw == m.raw,
            'raw_bodies_equal': p.segment_bytes(*pl['body']) == m.segment_bytes(*ml['body']),
            'normalized_bodies_equal': difference_count == 0,
            'body_difference_count': difference_count,
            'body_differences': differences,
            'citations': citations,
            'question': question_result,
            'request_id': request_id_result,
            'semantic_judgment': 'NOT_ESTABLISHED',
            'producer_authenticity': 'NOT_ESTABLISHED',
        },
        'not_established': NOT_ESTABLISHED,
        'warnings': warnings,
        'notice': NOTICE,
    }


def _error_document(e: CompareError) -> Dict[str, Any]:
    return {'schema': SCHEMA, 'error': {'code': e.code, 'message': e.message, **e.details}}


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise CompareError('invalid_arguments', _excerpt(message))


def _read(path: str, limit: int, option: str) -> bytes:
    try:
        with open(path, 'rb') as f:
            data = f.read(limit + 1)
    except OSError as e:
        raise CompareError('input_unreadable', f'{option}: {e.strerror}', option=option, path=_excerpt(path)) from None
    if len(data) > limit:
        raise CompareError('input_too_large', f'{option} has more than {limit} bytes', option=option, limit=limit)
    return data


def _line_number(text: str) -> int:
    if not re.fullmatch(r'[1-9][0-9]{0,6}', text):
        raise argparse.ArgumentTypeError('a line number must be 1 to 9999999 in ASCII digits')
    return int(text)


def main(argv: Optional[Sequence[str]] = None, stdout: Optional[Any] = None) -> int:
    """The CLI: one JSON document on stdout; exit 0 (agree), 1 (differences) or 2 (rejected)."""
    out = stdout if stdout is not None else sys.stdout.buffer
    parser = _ArgumentParser(prog='export_compare.py', add_help=False)
    parser.add_argument('--plain', required=True)
    parser.add_argument('--markdown', required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--question')
    group.add_argument('--question-file')
    parser.add_argument('--request-id')
    for option in (
        '--plain-body-start',
        '--plain-sources-line',
        '--markdown-body-start',
        '--markdown-definitions-start',
    ):
        parser.add_argument(option, type=_line_number)
    parser.add_argument('--rules', help='comma-separated subset of the policy rules; empty for none')
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
        question = args.question
        if args.question_file is not None:
            data = _read(args.question_file, MAX_QUESTION_BYTES, '--question-file')
            try:
                question = data.decode('utf-8', 'strict')
            except UnicodeDecodeError:
                raise CompareError('not_utf8', '--question-file is not valid UTF-8', option='--question-file') from None
            question = question[:-1] if question.endswith('\n') else question
        rules = None if args.rules is None else [r for r in args.rules.split(',') if r]
        result = compare_exports(
            _read(args.plain, MAX_DOCUMENT_BYTES, '--plain'),
            _read(args.markdown, MAX_DOCUMENT_BYTES, '--markdown'),
            question=question,
            request_id=args.request_id,
            plain_body_start=args.plain_body_start,
            plain_sources_line=args.plain_sources_line,
            markdown_body_start=args.markdown_body_start,
            markdown_definitions_start=args.markdown_definitions_start,
            rules=rules,
        )
        data = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_OUTPUT_BYTES:
            raise CompareError('output_too_large', f'the result has {len(data)} bytes; the limit is {MAX_OUTPUT_BYTES}')
        r = result['results']
        c = r['citations']
        agree = (
            r['normalized_bodies_equal']
            and c['referenced_ids_equal']
            and c['url_map_equal']
            and not (c['undefined_references']['plain'] or c['undefined_references']['markdown'])
        )
        status = 0 if agree else 1
    except CompareError as e:
        data = (json.dumps(_error_document(e), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        status = 2
    out.write(data)
    out.flush()
    return status


if __name__ == '__main__':
    sys.exit(main())
