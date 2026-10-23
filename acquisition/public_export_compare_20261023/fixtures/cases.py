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


def base_pair() -> Tuple[bytes, bytes]:
    """The full fixture pair (plain, Markdown) as raw bytes."""
    return (FIXTURES / 'full_plain.txt').read_bytes(), (FIXTURES / 'full_markdown.md').read_bytes()


def apply_case(case: Dict[str, Any]) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """The case's (plain, markdown, options), built from the full fixture pair by its single edit."""
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
    out.extend(f'warning {w["code"]}' for w in result['warnings'])
    return '\n'.join(out)
