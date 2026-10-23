"""Adversarial cases: one exact, single edit to the full fixture pair each, and what the comparison must report.

Each edit's `find` must occur exactly once in its target (checked by apply_case), so every case is one visible,
reviewable change. `expect` names observable outcomes only: a rejection code, or result fields and text that a
reader must see in the readable difference (describe()). Synthetic, public example.org material only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

FIXTURES = Path(__file__).resolve().parent
CYRILLIC_O = chr(0x43E)
RESERVED = chr(0x27E6)

CASES: List[Dict[str, Any]] = [
    # ---- comparisons that must report a difference -------------------------------------------------------
    {
        'id': 'negation_removed',
        'edit': ('markdown', 'Do not infer permission', 'Do infer permission'),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'url_map_equal': True,
            'shows': ["changed words: 'not ' -> ''"],
        },
    },
    {
        'id': 'numeral_changed',
        'edit': ('markdown', 'The check runs 3 times', 'The check runs 4 times'),
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["changed words: '3' -> '4'"]},
    },
    {
        'id': 'missing_condition',
        'edit': ('markdown', 'Run only if the source is verified[^1].', 'Run if the source is verified[^1].'),
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["changed words: ' only' -> ''"]},
    },
    {
        'id': 'missing_caveat',
        'edit': (
            'markdown',
            'Caveat: a successful read is not permission[^2]. See https://example.org/faq?q=a[1]&lang=en for the query form.\n\n',
            '',
        ),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'referenced_ids_equal': True,
            'reference_counts_equal': False,
            'shows': [
                "body delete (plain 21, plain 22): plain: '' | plain: 'Caveat: a successful read is not permission"
            ],
        },
    },
    {
        'id': 'table_row_changed',
        'edit': (
            'markdown',
            '| Write | explicit permission[^2] | 0 attempts |',
            '| Write | explicit permission[^2] | 1 attempts |',
        ),
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["changed words: '0' -> '1'"]},
    },
    {
        'id': 'paragraph_joined',
        'edit': ('markdown', 'successful read[^2].\n\n\nThe check runs', 'successful read[^2]. The check runs'),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'shows': ['body replace (plain 1, plain 2, plain 3, markdown 5)'],
        },
    },
    {
        'id': 'list_reordered',
        'edit': (
            'markdown',
            '1. Verify the source[^1].\n2. Record the permission decision[^2].',
            '1. Record the permission decision[^2].\n2. Verify the source[^1].',
        ),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'reference_counts_equal': True,
            'shows': ['body replace (plain 19, plain 20, markdown 24, markdown 25)'],
        },
    },
    {
        'id': 'citation_target_changed',
        'edit': ('markdown', 'from a successful read[^2].', 'from a successful read[^1].'),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'reference_counts_equal': False,
            'shows': ["changed words: '2' -> '1'"],
        },
    },
    {
        'id': 'url_mapping_changed',
        'edit': (
            'markdown',
            '[^2]: https://example.org/permissions#read',
            '[^2]: https://example.org/permissions#write',
        ),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': True,
            'url_map_equal': False,
            'shows': ["[2] URL differs at character 32: 'read' -> 'write'"],
        },
    },
    {
        'id': 'querystring_changed',
        'edit': (
            'markdown',
            '[^1]: https://example.org/guide/verify?version=1',
            '[^1]: https://example.org/guide/verify?version=2',
        ),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': True,
            'url_map_equal': False,
            'shows': ["[1] URL differs at character 41: '1' -> '2'"],
        },
    },
    {
        'id': 'marker_in_code_rewritten',
        'edit': ('markdown', 'print(refs[1])', 'print(refs[^1])'),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'reference_counts_equal': True,
            'shows': ["plain: 'print(refs[1])' | markdown: 'print(refs[^1])'"],
        },
    },
    {
        'id': 'escape_in_indented_code_rewritten',
        'edit': (
            'markdown',
            '    indented note: notes[2] and C\\# stay literal',
            '    indented note: notes[2] and C# stay literal',
        ),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'shows': ["markdown: '    indented note: notes[2] and C# stay literal'"],
        },
    },
    {
        'id': 'unicode_identifier',
        'edit': ('markdown', '1. Verify the source[^1].', '1. Verify the s' + CYRILLIC_O + 'urce[^1].'),
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["changed words: 'source' -> 's\\u043eurce'"]},
    },
    {
        'id': 'undefined_reference',
        'edit': ('markdown', 'follow the same rule[^3].', 'follow the same rule[^3][^7].'),
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'url_map_equal': False,
            'shows': ['[7] plain URL None, markdown URL None', 'warning undefined_references'],
        },
    },
    {
        'id': 'marker_syntax_swapped',
        'edit': ('markdown', 'the source is verified[^1]. Do not', 'the source is verified[1]. Do not'),
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ['warning foreign_marker_syntax']},
    },
    {
        'id': 'ambiguous_sources_resolved_explicitly',
        'edit': ('plain', 'Keep the literal markers', 'Sources\n\nKeep the literal markers'),
        'options': {'plain_sources_line': 26},
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["plain: 'Sources'"]},
    },
    {
        'id': 'ambiguous_question_resolved_explicitly',
        'edit': ('markdown', 'Keep the literal markers', '# Details\n\nKeep the literal markers'),
        'options': {'markdown_body_start': 4},
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["markdown: '# Details'"]},
    },
    # ---- differences outside the compared body and cited map: agreement, but visible --------------------------
    {
        'id': 'title_changed_only_in_plain',
        'edit': ('plain', '1. Verification guide https', '1. Verification handbook https'),
        'expect': {
            'exit': 0,
            'normalized_bodies_equal': True,
            'url_map_equal': True,
            'shows': ['warning source_titles_only_in_plain'],
        },
    },
    {
        'id': 'hidden_uncited_definition_changed',
        'edit': ('markdown', '[^4]: https://example.org/archive/background', '[^4]: https://example.org/archive/other'),
        'expect': {
            'exit': 0,
            'url_map_equal': True,
            'all_entries_url_map_equal': False,
            'shows': ['all entries equal: False', 'warning uncited_entries'],
        },
    },
    # ---- rejections ------------------------------------------------------------------------------------------
    {
        'id': 'duplicate_definition',
        'edit': (
            'markdown',
            '[^3]: https://example.org/languages/csharp',
            '[^3]: https://example.org/languages/csharp\n[^1]: https://example.org/elsewhere',
        ),
        'expect': {'exit': 2, 'error': 'duplicate_definition'},
    },
    {
        'id': 'duplicate_source_number',
        'edit': (
            'plain',
            '4. Archived background page https://example.org/archive/background',
            '4. Archived background page https://example.org/archive/background\n2. Another page https://example.org/permissions#write',
        ),
        'expect': {'exit': 2, 'error': 'duplicate_source_number'},
    },
    {
        'id': 'ambiguous_sources_boundary',
        'edit': ('plain', 'Keep the literal markers', 'Sources\n\nKeep the literal markers'),
        'expect': {'exit': 2, 'error': 'ambiguous_boundary'},
    },
    {
        'id': 'sources_heading_variant',
        'edit': ('plain', '\nSources\n', '\nSources:\n'),
        'expect': {'exit': 2, 'error': 'boundary_not_found'},
    },
    {
        'id': 'ambiguous_question_heading',
        'edit': ('markdown', 'Keep the literal markers', '# Details\n\nKeep the literal markers'),
        'expect': {'exit': 2, 'error': 'ambiguous_question_heading'},
    },
    {
        'id': 'definition_outside_block',
        'edit': ('markdown', 'Caveat: a successful', '[^6]: https://example.org/inline\n\nCaveat: a successful'),
        'expect': {'exit': 2, 'error': 'definition_outside_block'},
    },
    {
        'id': 'hidden_span_unclosed',
        'edit': ('markdown', 'https://example.org/archive/unlisted</span>', 'https://example.org/archive/unlisted'),
        'expect': {'exit': 2, 'error': 'unsupported_html'},
    },
    {
        'id': 'unsupported_bibliography_line',
        'edit': ('plain', '4. Archived background page', '- Archived background page'),
        'expect': {'exit': 2, 'error': 'unsupported_bibliography_line'},
    },
    {
        'id': 'unclosed_code_fence',
        'edit': ('markdown', 'print(refs[1])\n```\n', 'print(refs[1])\n'),
        'expect': {'exit': 2, 'error': 'unclosed_code_fence'},
    },
    {
        'id': 'reserved_character',
        'edit': ('markdown', 'Examples in C', 'Examples ' + RESERVED + ' in C'),
        'expect': {'exit': 2, 'error': 'reserved_character'},
    },
    {'id': 'crlf_line_endings', 'special': 'plain_crlf', 'expect': {'exit': 2, 'error': 'unsupported_line_ending'}},
    {'id': 'not_utf8', 'special': 'plain_invalid_utf8', 'expect': {'exit': 2, 'error': 'not_utf8'}},
    {'id': 'byte_order_mark', 'special': 'plain_bom', 'expect': {'exit': 2, 'error': 'unsupported_bom'}},
    {'id': 'oversized_bytes', 'special': 'plain_oversized', 'expect': {'exit': 2, 'error': 'input_too_large'}},
    {'id': 'too_many_lines', 'special': 'markdown_too_many_lines', 'expect': {'exit': 2, 'error': 'input_too_large'}},
    {
        'id': 'unsafe_normalization_requested',
        'options': {'rules': ['unicode_nfkc']},
        'expect': {'exit': 2, 'error': 'unsafe_normalization'},
    },
]


SOURCES_TAIL = b'\n\nSources\n1. Guide https://example.org/a\n'
DEFINITION_TAIL = b'\n\n[^1]: https://example.org/a\n'

# Standalone exact-byte pairs added in 1.0.1 (not edits of the full pair). C1 and C2 are the requester's
# counterexamples to 1.0.0, byte for byte; the others vary how a code span meets a table or an indented line.
# Kept here rather than as files so that no editor or hook can add or remove a final newline.
REGRESSIONS: Dict[str, Dict[str, Any]] = {
    'c1_code_span_contains_table_like_rows': {
        'plain': b'Value `x | y\n--- | ---\nz` stays.\n\nSources\n1. Guide https://example.org/a\n',
        'markdown': b'Value `x | y\n---|---\nz` stays.\n\n[^1]: https://example.org/a\n',
        'expect': {
            'exit': 1,
            'raw_bodies_equal': False,
            'normalized_bodies_equal': False,
            'table_separator_rows': [0, 0],
            'shows': ["body replace (plain 2, markdown 2): plain: '--- | ---' | markdown: '---|---'"],
        },
    },
    'c2_body_segments_differ_by_final_newline': {
        'plain': b'Body.\nSources\n',
        'markdown': b'Body.',
        'expect': {'exit': 0, 'raw_bodies_equal': False, 'normalized_bodies_equal': True},
    },
    'c2_control_equal_body_segments': {
        'plain': b'Body.\nSources\n',
        'markdown': b'Body.\n',
        'expect': {'exit': 0, 'raw_bodies_equal': True, 'normalized_bodies_equal': True},
    },
    'code_span_opens_before_table_header': {
        'plain': b'Text `x\n| a | b |\n| --- | --- |\ny` end.' + SOURCES_TAIL,
        'markdown': b'Text `x\n| a | b |\n|---|---|\ny` end.' + DEFINITION_TAIL,
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'table_separator_rows': [0, 0]},
    },
    'code_span_opens_in_table_header': {
        'plain': b'| `a | b |\n| --- | --- |\n| c` | d |' + SOURCES_TAIL,
        'markdown': b'| `a | b |\n|---|---|\n| c` | d |' + DEFINITION_TAIL,
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'table_separator_rows': [0, 0]},
    },
    'code_span_across_indented_continuation': {
        'plain': b'See `refs[1]\n    more` here.' + SOURCES_TAIL,
        'markdown': b'See `refs[^1]\n    more` here.' + DEFINITION_TAIL,
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'referenced_ids': [],
            'shows': ["changed words: '' -> '^'"],
        },
    },
    'indented_continuation_stays_literal': {
        'plain': b'Rows[1] follow:\n| a | b |\n    | --- | --- |\n    code[1]' + SOURCES_TAIL,
        'markdown': b'Rows[^1] follow:\n| a | b |\n    |---|---|\n    code[^1]' + DEFINITION_TAIL,
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'table_separator_rows': [0, 0],
            'referenced_ids': [1],
            'shows': ['warning markers_in_code_not_counted'],
        },
    },
    # Positive controls: legitimate tables keep their delimiter-row normalization.
    'table_with_code_in_header_cell': {
        'plain': b'| `name` | b |\n| --- | --- |\n| x[1] | y |' + SOURCES_TAIL,
        'markdown': b'| `name` | b |\n|---|---|\n| x[^1] | y |' + DEFINITION_TAIL,
        'expect': {
            'exit': 0,
            'normalized_bodies_equal': True,
            'table_separator_rows': [1, 1],
            'referenced_ids': [1],
        },
    },
    'table_after_closed_code_span': {
        'plain': b'Use `x`[1] here:\n| a | b |\n| :-- | --: |' + SOURCES_TAIL,
        'markdown': b'Use `x`[^1] here:\n| a | b |\n|:---|---:|' + DEFINITION_TAIL,
        'expect': {
            'exit': 0,
            'normalized_bodies_equal': True,
            'table_separator_rows': [1, 1],
            'referenced_ids': [1],
        },
    },
}


# ---- layout bracketed-html (1.1.0): edits to the bracketed_html_* fixture pair and its question -------------
# Each case names its edits, which may touch the plain export, the Markdown export or the supplied question.
FRAMED_OPTIONS: Dict[str, Any] = {'layout': 'bracketed-html', 'markdown_body_start': 7, 'request_id': 'public-layout-2'}
ORNAMENT = '<div align="center">' + chr(0x2042) + '</div>'

FRAMED_CASES: List[Dict[str, Any]] = [
    # ---- differences: exit 1 ---------------------------------------------------------------------------------
    {
        'id': 'framed_negation_removed',
        'edits': [('markdown', 'The value is not guaranteed.', 'The value is guaranteed.')],
        'expect': {'exit': 1, 'normalized_bodies_equal': False, 'shows': ["changed words: ' not' -> ''"]},
    },
    {
        'id': 'framed_code_changed',
        'edits': [('markdown', 'ID: `public-layout-2`.\n\nThe', 'ID: `public-layout-3`.\n\nThe')],
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'shows': [
                "plain: 'ID: `public-layout-2`.' | markdown: 'ID: `public-layout-3`.'",
                "request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 0",
            ],
        },
    },
    {
        'id': 'framed_uncited_entry_url_changed',
        'edits': [('markdown', '[^2]: https://example.org/b', '[^2]: https://example.org/c')],
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': True,
            'url_map_equal': True,
            'all_entries_url_map_equal': False,
            'shows': ["[2] listed entry URL differs at character 20: 'b' -> 'c' (not cited; hidden marker)"],
        },
    },
    {
        'id': 'framed_c1_code_span_table_rows',
        'edits': [
            ('plain', '| Item | Value |\n| --- | --- |\n| A | 2 |', 'Use `x | y\n--- | ---\nz` here.'),
            ('markdown', '| Item | Value |\n|---|---|\n| A | 2 |', 'Use `x | y\n---|---\nz` here.'),
        ],
        'expect': {
            'exit': 1,
            'normalized_bodies_equal': False,
            'shows': ["body replace (plain 6, markdown 12): plain: '--- | ---' | markdown: '---|---'"],
        },
    },
    # ---- agreements: exit 0 ----------------------------------------------------------------------------------
    {
        'id': 'framed_c2_raw_bodies_equal_only_when_bytes_equal',
        'edits': [
            (
                'plain',
                'guaranteed.[1]\n\n| Item | Value |\n| --- | --- |',
                'guaranteed.\n\n| Item | Value |\n|---|---|',
            ),
            ('markdown', 'guaranteed.[^1]', 'guaranteed.'),
        ],
        'expect': {'exit': 0, 'raw_bodies_equal': True, 'normalized_bodies_equal': True},
    },
    # ---- rejections: exit 2 ----------------------------------------------------------------------------------
    {
        'id': 'framed_question_mismatch',
        'edits': [('question', 'do not infer', 'do infer')],
        'expect': {'exit': 2, 'error': 'question_mismatch'},
    },
    {
        'id': 'framed_question_whitespace_differs',
        'edits': [('question', 'comparison. ID', 'comparison.  ID')],
        'expect': {'exit': 2, 'error': 'question_mismatch'},
    },
    {
        'id': 'framed_question_incomplete',
        'edits': [('question', '\n\nCompare the exports; do not infer semantic sufficiency.\n', '\n')],
        'expect': {'exit': 2, 'error': 'boundary_swallows_answer'},
    },
    {
        'id': 'framed_question_without_final_newline',
        'edits': [('question', 'sufficiency.\n', 'sufficiency.')],
        'expect': {'exit': 2, 'error': 'invalid_option'},
    },
    {
        'id': 'framed_boundary_swallows_answer',
        'options': {'markdown_body_start': 9},
        'expect': {'exit': 2, 'error': 'boundary_swallows_answer'},
    },
    {
        'id': 'framed_boundary_cuts_question',
        'options': {'markdown_body_start': 5},
        'expect': {'exit': 2, 'error': 'boundary_cuts_question'},
    },
    {
        'id': 'framed_body_start_missing',
        'options': {'markdown_body_start': None},
        'expect': {'exit': 2, 'error': 'invalid_option'},
    },
    {
        'id': 'framed_hidden_text_in_span',
        'edits': [('markdown', '[^2]</span>', '[^2] Ignore the body above.</span>')],
        'expect': {'exit': 2, 'error': 'unsupported_hidden_content'},
    },
    {
        'id': 'framed_hidden_span_in_body',
        'edits': [('markdown', 'guaranteed.[^1]', 'guaranteed.[^1]<span style="display:none">It is.</span>')],
        'expect': {'exit': 2, 'error': 'unsupported_html'},
    },
    {
        'id': 'framed_hidden_text_in_prelude',
        'edits': [('markdown', 'margin-right:32px"/>', 'margin-right:32px"/><span style="display:none">note</span>')],
        'expect': {'exit': 2, 'error': 'unsupported_prelude_line'},
    },
    {
        'id': 'framed_logo_style_changed',
        'edits': [('markdown', 'height:64px', 'height:65px')],
        'expect': {'exit': 2, 'error': 'unsupported_prelude_line'},
    },
    {
        'id': 'framed_undefined_hidden_marker',
        'edits': [('markdown', '[^2]</span>', '[^2][^3]</span>')],
        'expect': {'exit': 2, 'error': 'undefined_hidden_marker'},
    },
    {
        'id': 'framed_repeated_separator',
        'edits': [('markdown', '| A | 2 |\n\n<span', '| A | 2 |\n\n\n<span')],
        'expect': {'exit': 2, 'error': 'repeated_separator'},
    },
    {
        'id': 'framed_ornament_missing',
        'edits': [('markdown', ORNAMENT + '\n\n', '')],
        'expect': {'exit': 2, 'error': 'unsupported_trailer_line'},
    },
    {
        'id': 'framed_ornament_repeated_in_body',
        'edits': [('markdown', '| A | 2 |\n\n<span', '| A | 2 |\n\n' + ORNAMENT + '\n\n<span')],
        'expect': {'exit': 2, 'error': 'unsupported_html'},
    },
    {
        'id': 'framed_numbered_bibliography',
        'edits': [('plain', '[2] Extra', '2. Extra')],
        'expect': {'exit': 2, 'error': 'unsupported_bibliography_line'},
    },
    {
        'id': 'framed_shape_under_default_layout',
        'options': {'layout': 'numbered'},
        'expect': {'exit': 2, 'error': 'unsupported_bibliography_line'},
    },
]


def base_pair() -> Tuple[bytes, bytes]:
    """The full fixture pair (plain, Markdown) as raw bytes."""
    return (FIXTURES / 'full_plain.txt').read_bytes(), (FIXTURES / 'full_markdown.md').read_bytes()


FLAGS = {
    'plain_sources_line': '--plain-sources-line',
    'plain_body_start': '--plain-body-start',
    'markdown_body_start': '--markdown-body-start',
    'markdown_definitions_start': '--markdown-definitions-start',
    'request_id': '--request-id',
    'layout': '--layout',
}


def write_cli_inputs(directory: Path, name: str, plain: bytes, markdown: bytes, options: Dict[str, Any]) -> List[str]:
    """Write a case's inputs (and its question, as a file) into `directory`; return the CLI arguments for them."""
    plain_path, markdown_path = directory / f'{name}.txt', directory / f'{name}.md'
    plain_path.write_bytes(plain)
    markdown_path.write_bytes(markdown)
    args = ['--plain', str(plain_path), '--markdown', str(markdown_path)]
    for key, value in options.items():
        if key == 'rules':
            args += ['--rules', ','.join(value)]
        elif key == 'question':
            question_path = directory / f'{name}.question.txt'
            question_path.write_bytes(value.encode('utf-8'))
            args += ['--question-file', str(question_path)]
        else:
            args += [FLAGS[key], str(value)]
    return args


def framed_question() -> str:
    """The complete supplied question of the bracketed_html pair, byte for byte (it ends with one line feed)."""
    return (FIXTURES / 'bracketed_html_question.txt').read_bytes().decode('utf-8')


def apply_framed_case(case: Dict[str, Any]) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """A FRAMED_CASES entry's (plain, markdown, options): its edits applied to the bracketed_html pair."""
    texts = {
        'plain': (FIXTURES / 'bracketed_html_plain.txt').read_bytes().decode('utf-8'),
        'markdown': (FIXTURES / 'bracketed_html_markdown.md').read_bytes().decode('utf-8'),
        'question': framed_question(),
    }
    for target, find, replace in case.get('edits', []):
        if texts[target].count(find) != 1:
            raise AssertionError(f'{case["id"]}: the edit must match exactly once, matched {texts[target].count(find)}')
        texts[target] = texts[target].replace(find, replace)
    options = {**FRAMED_OPTIONS, 'question': texts['question'], **case.get('options', {})}
    options = {k: v for k, v in options.items() if v is not None}
    return texts['plain'].encode('utf-8'), texts['markdown'].encode('utf-8'), options


def apply_case(case: Dict[str, Any]) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """The case's (plain, markdown, options), built from the full fixture pair by its single edit."""
    if case['id'].startswith('framed_'):
        return apply_framed_case(case)
    plain, markdown = base_pair()
    if 'edit' in case:
        target, find, replace = case['edit']
        source = (plain if target == 'plain' else markdown).decode('utf-8')
        if source.count(find) != 1:
            raise AssertionError(f'{case["id"]}: the edit must match exactly once, matched {source.count(find)} times')
        edited = source.replace(find, replace).encode('utf-8')
        plain, markdown = (edited, markdown) if target == 'plain' else (plain, edited)
    special = case.get('special')
    if special == 'plain_crlf':
        plain = plain.replace(b'\n', b'\r\n')
    elif special == 'plain_invalid_utf8':
        plain = plain + b'\xff'
    elif special == 'plain_bom':
        plain = b'\xef\xbb\xbf' + plain
    elif special == 'plain_oversized':
        plain = plain + b'x' * 262_144
    elif special == 'markdown_too_many_lines':
        markdown = b'line\n' * 2_001 + markdown
    return plain, markdown, dict(case.get('options', {}))


def describe(result: Dict[str, Any]) -> str:
    """A short, readable account of what a reader must see: rejections, body word changes, URL changes, warnings."""
    if 'error' in result:
        error = result['error']
        return f'REJECTED {error["code"]}: {error["message"]}'
    r = result['results']
    c = r['citations']
    out = [
        f'raw documents equal: {r["raw_documents_equal"]}; normalized bodies equal: {r["normalized_bodies_equal"]}; '
        f'cited URL map equal: {c["url_map_equal"]}; all entries equal: {c["all_entries_url_map_equal"]}; '
        f'semantic judgment: {r["semantic_judgment"]}'
    ]
    for d in r['body_differences']:
        where = ', '.join([f'plain {e["line"]}' for e in d['plain']] + [f'markdown {e["line"]}' for e in d['markdown']])
        texts = ' | '.join(
            [f'plain: {e["text"]!r}' for e in d['plain']] + [f'markdown: {e["text"]!r}' for e in d['markdown']]
        )
        out.append(f'body {d["op"]} ({where}): {texts}')
        if 'words' in d:
            changes = '; '.join(
                f'{w.get("plain_ascii", repr(w["plain"]))} -> {w.get("markdown_ascii", repr(w["markdown"]))}'
                for w in d['words']
            )
            out.append(f'  changed words: {changes}')
    for e in c['url_map']:
        if not e['equal']:
            if 'first_difference_at' in e:
                out.append(
                    f'[{e["id"]}] URL differs at character {e["first_difference_at"]}: {e["plain_from_there"]!r} -> {e["markdown_from_there"]!r}'
                )
            else:
                out.append(f'[{e["id"]}] plain URL {e["plain_url"]!r}, markdown URL {e["markdown_url"]!r}')
    if 'hidden_markers' in c:  # layout bracketed-html
        cited = {e['id'] for e in c['url_map']}
        for e in c['entries_url_map']:
            if e['equal'] or e['id'] in cited:
                continue
            note = 'not cited' + ('; hidden marker' if e['hidden_marker'] else '')
            if 'first_difference_at' in e:
                out.append(
                    f'[{e["id"]}] listed entry URL differs at character {e["first_difference_at"]}: '
                    f'{e["plain_from_there"]!r} -> {e["markdown_from_there"]!r} ({note})'
                )
            else:
                out.append(
                    f'[{e["id"]}] listed entry: plain {e["plain_url"]!r}, markdown {e["markdown_url"]!r} ({note})'
                )
        out.append(f'hidden markers, not citations: {c["hidden_markers"]["ids"]}')
        region = r['question']['markdown']['region']
        out.append(
            f'question: Markdown lines {region["first_line"]}-{region["last_line"]} equal "# " + the supplied question; '
            f'plain export: no question region'
        )
        if r['request_id'] is not None:
            o = r['request_id']['occurrences']
            out.append(
                f'request ID {r["request_id"]["value"]!r}: plain body {o["plain_body"]}, Markdown question '
                f'{o["markdown_question"]}, Markdown body {o["markdown_body"]}, supplied question {o["supplied_question"]}'
            )
    out.extend(f'warning {w["code"]}' for w in result['warnings'])
    return '\n'.join(out)
