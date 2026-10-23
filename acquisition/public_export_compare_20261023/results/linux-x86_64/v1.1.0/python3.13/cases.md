# Cases through the CLI (Python 3.13.16, Linux-6.18.44-fc-v153-x86_64-with-glibc2.39)

## positive:full (exit 0, expected 0)

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning uncited_entries
warning markers_in_code_not_counted
```

## positive:minimal (exit 0, expected 0)

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning question_absent
```

## positive:id_in_body (exit 0, expected 0)

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning question_absent
```

## positive:bracketed_html (exit 0, expected 0)

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 1, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## negation_removed (exit 1, expected 1)

Edit: `('markdown', 'Do not infer permission', 'Do infer permission')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 5): plain: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.' | markdown: 'Run only if the source is verified⟦cite 1⟧. Do infer permission from a successful read⟦cite 2⟧.'
  changed words: 'not ' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## numeral_changed (exit 1, expected 1)

Edit: `('markdown', 'The check runs 3 times', 'The check runs 4 times')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 3, markdown 8): plain: 'The check runs 3 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧.' | markdown: 'The check runs 4 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧.'
  changed words: '3' -> '4'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## missing_condition (exit 1, expected 1)

Edit: `('markdown', 'Run only if the source is verified[^1].', 'Run if the source is verified[^1].')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 5): plain: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.' | markdown: 'Run if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.'
  changed words: ' only' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## missing_caveat (exit 1, expected 1)

Edit: `('markdown', 'Caveat: a successful read is not permission[^2]. See https://example.org/faq?q=a[1]&lang=en for the query form.\n\n', '')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body delete (plain 21, plain 22): plain: '' | plain: 'Caveat: a successful read is not permission⟦cite 2⟧. See https://example.org/faq?q=a[1]&lang=en for the query form.'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## table_row_changed (exit 1, expected 1)

Edit: `('markdown', '| Write | explicit permission[^2] | 0 attempts |', '| Write | explicit permission[^2] | 1 attempts |')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 8, markdown 13): plain: '| Write | explicit permission⟦cite 2⟧ | 0 attempts |' | markdown: '| Write | explicit permission⟦cite 2⟧ | 1 attempts |'
  changed words: '0' -> '1'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## paragraph_joined (exit 1, expected 1)

Edit: `('markdown', 'successful read[^2].\n\n\nThe check runs', 'successful read[^2]. The check runs')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, plain 2, plain 3, markdown 5): plain: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.' | plain: '' | plain: 'The check runs 3 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧.' | markdown: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧. The check runs 3 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧.'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## list_reordered (exit 1, expected 1)

Edit: `('markdown', '1. Verify the source[^1].\n2. Record the permission decision[^2].', '1. Record the permission decision[^2].\n2. Verify the source[^1].')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 19, plain 20, markdown 24, markdown 25): plain: '1. Verify the source⟦cite 1⟧.' | plain: '2. Record the permission decision⟦cite 2⟧.' | markdown: '1. Record the permission decision⟦cite 2⟧.' | markdown: '2. Verify the source⟦cite 1⟧.'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## citation_target_changed (exit 1, expected 1)

Edit: `('markdown', 'from a successful read[^2].', 'from a successful read[^1].')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 5): plain: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.' | markdown: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 1⟧.'
  changed words: '2' -> '1'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## url_mapping_changed (exit 1, expected 1)

Edit: `('markdown', '[^2]: https://example.org/permissions#read', '[^2]: https://example.org/permissions#write')`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: False; all entries equal: False; semantic judgment: NOT_ESTABLISHED
[2] URL differs at character 32: 'read' -> 'write'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## querystring_changed (exit 1, expected 1)

Edit: `('markdown', '[^1]: https://example.org/guide/verify?version=1', '[^1]: https://example.org/guide/verify?version=2')`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: False; all entries equal: False; semantic judgment: NOT_ESTABLISHED
[1] URL differs at character 41: '1' -> '2'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## marker_in_code_rewritten (exit 1, expected 1)

Edit: `('markdown', 'print(refs[1])', 'print(refs[^1])')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 14, markdown 19): plain: 'print(refs[1])' | markdown: 'print(refs[^1])'
  changed words: '' -> '^'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## escape_in_indented_code_rewritten (exit 1, expected 1)

Edit: `('markdown', '    indented note: notes[2] and C\\# stay literal', '    indented note: notes[2] and C# stay literal')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 17, markdown 22): plain: '    indented note: notes[2] and C\\# stay literal' | markdown: '    indented note: notes[2] and C# stay literal'
  changed words: '\\' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## unicode_identifier (exit 1, expected 1)

Edit: `('markdown', '1. Verify the source[^1].', '1. Verify the sоurce[^1].')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 19, markdown 24): plain: '1. Verify the source⟦cite 1⟧.' | markdown: '1. Verify the sоurce⟦cite 1⟧.'
  changed words: 'source' -> 's\u043eurce'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## undefined_reference (exit 1, expected 1)

Edit: `('markdown', 'follow the same rule[^3].', 'follow the same rule[^3][^7].')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: False; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 3, markdown 8): plain: 'The check runs 3 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧.' | markdown: 'The check runs 3 times before it reports a result⟦cite 1⟧. Examples in C# follow the same rule⟦cite 3⟧⟦cite 7⟧.'
  changed words: '' -> '\u27e6cite 7\u27e7'
[7] plain URL None, markdown URL None
warning source_titles_only_in_plain
warning uncited_entries
warning undefined_references
warning question_absent
warning markers_in_code_not_counted
```

## marker_syntax_swapped (exit 1, expected 1)

Edit: `('markdown', 'the source is verified[^1]. Do not', 'the source is verified[1]. Do not')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 5): plain: 'Run only if the source is verified⟦cite 1⟧. Do not infer permission from a successful read⟦cite 2⟧.' | markdown: 'Run only if the source is verified[1]. Do not infer permission from a successful read⟦cite 2⟧.'
  changed words: '\u27e6cite ' -> '['; '\u27e7' -> ']'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
warning foreign_marker_syntax
```

## ambiguous_sources_resolved_explicitly (exit 1, expected 1)

Edit: `('plain', 'Keep the literal markers', 'Sources\n\nKeep the literal markers')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body delete (plain 9, plain 10): plain: '' | plain: 'Sources'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## ambiguous_question_resolved_explicitly (exit 1, expected 1)

Edit: `('markdown', 'Keep the literal markers', '# Details\n\nKeep the literal markers')`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
body insert (markdown 14, markdown 15): markdown: '' | markdown: '# Details'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## title_changed_only_in_plain (exit 0, expected 0)

Edit: `('plain', '1. Verification guide https', '1. Verification handbook https')`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## hidden_uncited_definition_changed (exit 0, expected 0)

Edit: `('markdown', '[^4]: https://example.org/archive/background', '[^4]: https://example.org/archive/other')`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
warning markers_in_code_not_counted
```

## duplicate_definition (exit 2, expected 2)

Edit: `('markdown', '[^3]: https://example.org/languages/csharp', '[^3]: https://example.org/languages/csharp\n[^1]: https://example.org/elsewhere')`

```
REJECTED duplicate_definition: [^1] is defined on lines 29 and 32
```

## duplicate_source_number (exit 2, expected 2)

Edit: `('plain', '4. Archived background page https://example.org/archive/background', '4. Archived background page https://example.org/archive/background\n2. Another page https://example.org/permissions#write')`

```
REJECTED duplicate_source_number: source 2 is listed on lines 26 and 29
```

## ambiguous_sources_boundary (exit 2, expected 2)

Edit: `('plain', 'Keep the literal markers', 'Sources\n\nKeep the literal markers')`

```
REJECTED ambiguous_boundary: the plain export has more than one "Sources" line outside code; pass plain_sources_line
```

## sources_heading_variant (exit 2, expected 2)

Edit: `('plain', '\nSources\n', '\nSources:\n')`

```
REJECTED boundary_not_found: the plain export has no line that is exactly "Sources" outside code; it is not in the supported layout
```

## ambiguous_question_heading (exit 2, expected 2)

Edit: `('markdown', 'Keep the literal markers', '# Details\n\nKeep the literal markers')`

```
REJECTED ambiguous_question_heading: the Markdown export starts with a "# " heading but has other "# " headings outside code; pass markdown_body_start
```

## definition_outside_block (exit 2, expected 2)

Edit: `('markdown', 'Caveat: a successful', '[^6]: https://example.org/inline\n\nCaveat: a successful')`

```
REJECTED definition_outside_block: the Markdown body contains footnote definition lines outside code; only a trailing definition block is supported
```

## hidden_span_unclosed (exit 2, expected 2)

Edit: `('markdown', 'https://example.org/archive/unlisted</span>', 'https://example.org/archive/unlisted')`

```
REJECTED unsupported_html: a display:none span in the definitions is never closed
```

## unsupported_bibliography_line (exit 2, expected 2)

Edit: `('plain', '4. Archived background page', '- Archived background page')`

```
REJECTED unsupported_bibliography_line: plain line 28 after "Sources" is not "N. title URL"
```

## unclosed_code_fence (exit 2, expected 2)

Edit: `('markdown', 'print(refs[1])\n```\n', 'print(refs[1])\n')`

```
REJECTED unclosed_code_fence: markdown has a code fence opened on line 17 and never closed
```

## reserved_character (exit 2, expected 2)

Edit: `('markdown', 'Examples in C', 'Examples ⟦ in C')`

```
REJECTED reserved_character: markdown contains U+27E6 or U+27E7, which this tool reserves for citation tokens
```

## crlf_line_endings (exit 2, expected 2)

Edit: `'plain_crlf'`

```
REJECTED unsupported_line_ending: plain contains U+000D on line 1
```

## not_utf8 (exit 2, expected 2)

Edit: `'plain_invalid_utf8'`

```
REJECTED not_utf8: plain is not valid UTF-8 (byte 928)
```

## byte_order_mark (exit 2, expected 2)

Edit: `'plain_bom'`

```
REJECTED unsupported_bom: plain starts with a UTF-8 byte order mark
```

## oversized_bytes (exit 2, expected 2)

Edit: `'plain_oversized'`

```
REJECTED input_too_large: --plain has more than 262144 bytes
```

## too_many_lines (exit 2, expected 2)

Edit: `'markdown_too_many_lines'`

```
REJECTED input_too_large: markdown has 2035 lines; the limit is 2000
```

## unsafe_normalization_requested (exit 2, expected 2)

Edit: `{'rules': ['unicode_nfkc']}`

```
REJECTED unsafe_normalization: requested normalization would turn real differences into matches: unicode_nfkc: changes numbers and symbols ("x²" becomes "x2", "①" becomes "1")
```

## framed_negation_removed (exit 1, expected 1)

Edit: `[('markdown', 'The value is not guaranteed.', 'The value is guaranteed.')]`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 3, markdown 9): plain: 'The value is not guaranteed.⟦cite 1⟧' | markdown: 'The value is guaranteed.⟦cite 1⟧'
  changed words: ' not' -> ''
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 1, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## framed_code_changed (exit 1, expected 1)

Edit: `[('markdown', 'ID: `public-layout-2`.\n\nThe', 'ID: `public-layout-3`.\n\nThe')]`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 7): plain: 'ID: `public-layout-2`.' | markdown: 'ID: `public-layout-3`.'
  changed words: '2' -> '3'
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 0, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## framed_uncited_entry_url_changed (exit 1, expected 1)

Edit: `[('markdown', '[^2]: https://example.org/b', '[^2]: https://example.org/c')]`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: False; semantic judgment: NOT_ESTABLISHED
[2] listed entry URL differs at character 20: 'b' -> 'c' (not cited; hidden marker)
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 1, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## framed_c1_code_span_table_rows (exit 1, expected 1)

Edit: `[('plain', '| Item | Value |\n| --- | --- |\n| A | 2 |', 'Use `x | y\n--- | ---\nz` here.'), ('markdown', '| Item | Value |\n|---|---|\n| A | 2 |', 'Use `x | y\n---|---\nz` here.')]`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 6, markdown 12): plain: '--- | ---' | markdown: '---|---'
  changed words: ' ' -> ''; ' ' -> ''
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 1, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## framed_c2_raw_bodies_equal_only_when_bytes_equal (exit 0, expected 0)

Edit: `[('plain', 'guaranteed.[1]\n\n| Item | Value |\n| --- | --- |', 'guaranteed.\n\n| Item | Value |\n|---|---|'), ('markdown', 'guaranteed.[^1]', 'guaranteed.')]`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
hidden markers, not citations: [2]
question: Markdown lines 3-5 equal "# " + the supplied question; plain export: no question region
request ID 'public-layout-2': plain body 1, Markdown question 1, Markdown body 1, supplied question 1
warning source_titles_only_in_plain
warning uncited_entries
warning hidden_markers_not_citations
warning question_absent
```

## framed_question_mismatch (exit 2, expected 2)

Edit: `[('question', 'do not infer', 'do infer')]`

```
REJECTED question_mismatch: the Markdown question region (lines 3-5) without "# " differs from the supplied question at byte 72
```

## framed_question_whitespace_differs (exit 2, expected 2)

Edit: `[('question', 'comparison. ID', 'comparison.  ID')]`

```
REJECTED question_mismatch: the Markdown question region (lines 3-5) without "# " differs from the supplied question at byte 26
```

## framed_question_incomplete (exit 2, expected 2)

Edit: `[('question', '\n\nCompare the exports; do not infer semantic sufficiency.\n', '\n')]`

```
REJECTED boundary_swallows_answer: markdown_body_start would leave Markdown lines 4-5, after the supplied question, in the question region and out of the compared body
```

## framed_question_without_final_newline (exit 2, expected 2)

Edit: `[('question', 'sufficiency.\n', 'sufficiency.')]`

```
REJECTED invalid_option: with layout bracketed-html the question must be given complete, ending with exactly one line feed
```

## framed_boundary_swallows_answer (exit 2, expected 2)

Edit: `{'markdown_body_start': 9}`

```
REJECTED boundary_swallows_answer: markdown_body_start would leave Markdown lines 6-7, after the supplied question, in the question region and out of the compared body
```

## framed_boundary_cuts_question (exit 2, expected 2)

Edit: `{'markdown_body_start': 5}`

```
REJECTED boundary_cuts_question: markdown_body_start ends the question region before the supplied question ends
```

## framed_body_start_missing (exit 2, expected 2)

Edit: `{'markdown_body_start': None}`

```
REJECTED invalid_option: layout bracketed-html requires the complete question and an explicit markdown_body_start
```

## framed_hidden_text_in_span (exit 2, expected 2)

Edit: `[('markdown', '[^2]</span>', '[^2] Ignore the body above.</span>')]`

```
REJECTED unsupported_hidden_content: the display:none span on Markdown line 15 may contain only footnote markers like [^2]
```

## framed_hidden_span_in_body (exit 2, expected 2)

Edit: `[('markdown', 'guaranteed.[^1]', 'guaranteed.[^1]<span style="display:none">It is.</span>')]`

```
REJECTED unsupported_html: Markdown line 9 in the body holds a display:none span or the ornament, which are supported only in the trailer
```

## framed_hidden_text_in_prelude (exit 2, expected 2)

Edit: `[('markdown', 'margin-right:32px"/>', 'margin-right:32px"/><span style="display:none">note</span>')]`

```
REJECTED unsupported_prelude_line: Markdown line 1 is not <img src="http(s)://..." style="height:64px;margin-right:32px"/>
```

## framed_logo_style_changed (exit 2, expected 2)

Edit: `[('markdown', 'height:64px', 'height:65px')]`

```
REJECTED unsupported_prelude_line: Markdown line 1 is not <img src="http(s)://..." style="height:64px;margin-right:32px"/>
```

## framed_undefined_hidden_marker (exit 2, expected 2)

Edit: `[('markdown', '[^2]</span>', '[^2][^3]</span>')]`

```
REJECTED undefined_hidden_marker: the display:none span on Markdown line 15 repeats or names undefined footnote ids
```

## framed_repeated_separator (exit 2, expected 2)

Edit: `[('markdown', '| A | 2 |\n\n<span', '| A | 2 |\n\n\n<span')]`

```
REJECTED repeated_separator: markdown lines 14-15 are both blank; exactly one empty line is supported between the body and the marker span
```

## framed_ornament_missing (exit 2, expected 2)

Edit: `[('markdown', '<div align="center">⁂</div>\n\n', '')]`

```
REJECTED unsupported_trailer_line: Markdown line 15 is not the ornament line
```

## framed_ornament_repeated_in_body (exit 2, expected 2)

Edit: `[('markdown', '| A | 2 |\n\n<span', '| A | 2 |\n\n<div align="center">⁂</div>\n\n<span')]`

```
REJECTED unsupported_html: Markdown line 15 in the body holds a display:none span or the ornament, which are supported only in the trailer
```

## framed_numbered_bibliography (exit 2, expected 2)

Edit: `[('plain', '[2] Extra', '2. Extra')]`

```
REJECTED unsupported_bibliography_line: plain line 11 after "Sources" is not "[N] title URL"
```

## framed_shape_under_default_layout (exit 2, expected 2)

Edit: `{'layout': 'numbered'}`

```
REJECTED unsupported_bibliography_line: plain line 10 after "Sources" is not "N. title URL"
```

## regression:c1_code_span_contains_table_like_rows (exit 1, expected 1)

Plain: `b'Value `x | y\n--- | ---\nz` stays.\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'Value `x | y\n---|---\nz` stays.\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 2, markdown 2): plain: '--- | ---' | markdown: '---|---'
  changed words: ' ' -> ''; ' ' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
```

## regression:c2_body_segments_differ_by_final_newline (exit 0, expected 0)

Plain: `b'Body.\nSources\n'`

Markdown: `b'Body.'`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning question_absent
warning final_newline_differs
```

## regression:c2_control_equal_body_segments (exit 0, expected 0)

Plain: `b'Body.\nSources\n'`

Markdown: `b'Body.\n'`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning question_absent
```

## regression:code_span_opens_before_table_header (exit 1, expected 1)

Plain: `b'Text `x\n| a | b |\n| --- | --- |\ny` end.\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'Text `x\n| a | b |\n|---|---|\ny` end.\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 3, markdown 3): plain: '| --- | --- |' | markdown: '|---|---|'
  changed words: ' ' -> ''; ' ' -> ''; ' ' -> ''; ' ' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
```

## regression:code_span_opens_in_table_header (exit 1, expected 1)

Plain: `b'| `a | b |\n| --- | --- |\n| c` | d |\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'| `a | b |\n|---|---|\n| c` | d |\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 2, markdown 2): plain: '| --- | --- |' | markdown: '|---|---|'
  changed words: ' ' -> ''; ' ' -> ''; ' ' -> ''; ' ' -> ''
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
```

## regression:code_span_across_indented_continuation (exit 1, expected 1)

Plain: `b'See `refs[1]\n    more` here.\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'See `refs[^1]\n    more` here.\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 1, markdown 1): plain: 'See `refs[1]' | markdown: 'See `refs[^1]'
  changed words: '' -> '^'
warning source_titles_only_in_plain
warning uncited_entries
warning question_absent
```

## regression:indented_continuation_stays_literal (exit 1, expected 1)

Plain: `b'Rows[1] follow:\n| a | b |\n    | --- | --- |\n    code[1]\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'Rows[^1] follow:\n| a | b |\n    |---|---|\n    code[^1]\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: False; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
body replace (plain 3, plain 4, markdown 3, markdown 4): plain: '    | --- | --- |' | plain: '    code[1]' | markdown: '    |---|---|' | markdown: '    code[^1]'
warning source_titles_only_in_plain
warning question_absent
warning markers_in_code_not_counted
```

## regression:table_with_code_in_header_cell (exit 0, expected 0)

Plain: `b'| `name` | b |\n| --- | --- |\n| x[1] | y |\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'| `name` | b |\n|---|---|\n| x[^1] | y |\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning question_absent
```

## regression:table_after_closed_code_span (exit 0, expected 0)

Plain: `b'Use `x`[1] here:\n| a | b |\n| :-- | --: |\n\nSources\n1. Guide https://example.org/a\n'`

Markdown: `b'Use `x`[^1] here:\n| a | b |\n|:---|---:|\n\n[^1]: https://example.org/a\n'`

```
raw documents equal: False; normalized bodies equal: True; cited URL map equal: True; all entries equal: True; semantic judgment: NOT_ESTABLISHED
warning source_titles_only_in_plain
warning question_absent
```

