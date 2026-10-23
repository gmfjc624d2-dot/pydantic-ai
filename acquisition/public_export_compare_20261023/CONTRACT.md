# Contract: `export_compare` 1.2.0 (schema `export-compare/1`, policy `export-compare-body-policy/1`)

## Purpose and non-goals

A deterministic aid for a reader who holds two exports of one research answer: a plain-text copy and a
Markdown export. It reports, as separate fields:
- whether the raw files and the raw bodies are equal;
- whether the bodies agree under a narrow, named normalization policy, with every remaining difference;
- whether cited ids map to the same URLs;
- which sources are listed or defined without being cited;
- whether a question and a caller-given request ID are present, and where.

It is **not** a semantic-equivalence judge or a Markdown framework. `semantic_judgment` and
`producer_authenticity` are always `NOT_ESTABLISHED`, and `not_established` lists semantic equivalence,
producer authenticity, question identity, truth and completeness of evidence. Equal normalized bodies mean
only textual agreement under the policy. Inputs are read, never rewritten. There is no network access.

## Interfaces

- `compare_exports(plain: bytes, markdown: bytes, *, question=None, request_id=None, plain_body_start=None,
  plain_sources_line=None, markdown_body_start=None, markdown_definitions_start=None, rules=None,
  layout='numbered') -> dict`. It is pure and raises `CompareError` (`code`, `message`, `details`) for
  rejected input.
- `python3 export_compare.py --plain FILE --markdown FILE [--question TEXT | --question-file FILE]
  [--request-id ID] [--plain-body-start N] [--plain-sources-line N] [--markdown-body-start N]
  [--markdown-definitions-start N] [--rules R1,R2] [--layout numbered|bracketed-html]`.
  - It writes one UTF-8 JSON document and a final `\n` to stdout. Nothing goes to stderr.
  - Exit status 0: normalized bodies equal, the same ids cited, every cited id's URL equal, and no
    undefined citation. With `--layout bracketed-html`, also every listed and defined id and URL equal
    (`all_entries_url_map_equal`).
  - Exit status 1: any of those differ; the document lists what differs.
  - Exit status 2: rejected, with `{"schema", "error": {"code", "message", ...}}`.
  - Exit status 0 is not a substitute for reading the fields. Raw equality, uncited entries, hidden
    markers, titles that exist only in the plain export, and warnings are reported, not folded into the
    status.
  - With the default layout, a question file loses one trailing `\n`, if present, and nothing else is
    changed. With `bracketed-html`, the file's bytes are used exactly.
- `layout` selects the layout pair. `numbered` (the default) is described below, unchanged since 1.0.0.
  `bracketed-html` must be selected explicitly; see its own section.
- Standard library only; CPython ≥ 3.9 (run on 3.9.25 and 3.13.16, Linux only).

## Supported layouts (anything else is rejected, not guessed)

Both inputs must be UTF-8 without a byte order mark. Lines are separated by LF only: a CR anywhere, or any
other C0 control except TAB, is rejected. U+27E6 and U+27E7 are reserved for citation tokens and rejected.

**Plain, `plain-numbered-sources/1`:** `[preamble] body`, then one line that is exactly `Sources`, then
entries.
- Every non-blank line after `Sources` must be `N. title URL`: N is 1–9999 without leading zeros, the
  title is everything between `N. ` and the last space, and the URL is the last token, starting with
  `http://` or `https://`.
- Entry numbers must be unique.
- The title is kept verbatim.
- There is a preamble only when `plain_body_start` is given; by default the body starts at line 1.

**Markdown, `markdown-footnote-definitions/1`:** `[logo] [question] body`, then a trailing definition block.
- Logo: line 1 may be `![alt](http(s)://...)`.
- Question: the first non-blank line after it may be one `# question` heading.
- Definition block: the maximal trailing block of lines that are blank, `[^N]: URL` (URL starting with
  `http://` or `https://`), or such definitions wrapped in `<span style="display:none">` … `</span>`. The
  span may open at the start of a definition line, close at its end, or stand alone on its own line.
- Definitions inside the span are reported with `hidden: true`.
- Definition ids must be unique.
- A `[^...]:` line elsewhere outside code is rejected.

**Boundaries.** By default the tool recognizes the layout and rejects anything ambiguous:
- zero `Sources` lines: `boundary_not_found`, listing near misses such as `Sources:` or `SOURCES`;
- two or more `Sources` lines: `ambiguous_boundary`, listing their line numbers;
- a leading `# ` heading while other `# ` headings exist outside code: `ambiguous_question_heading`.

The caller may instead give exact 1-based line numbers: `plain_body_start`, `plain_sources_line` (must be
a `Sources` line outside code), `markdown_body_start` (the lines before it may only be a logo, one heading
or blank) and `markdown_definitions_start` (every line from it must be a definition-block line). Explicit
boundaries are validated, not trusted. Each input's segments (`preamble`/`body`/`sources` and
`prelude`/`body`/`definitions`) partition it exactly, with 1-based line ranges, half-open byte ranges and
the SHA-256 of each segment's raw bytes.

**Code.** Fenced code (``` or ~~~, closed by the same character at least as long) and any non-blank
line indented by 4 spaces or a tab are code, wherever they occur. An unclosed fence is rejected. Code is
compared literally and is never searched for citations or boundaries.

**Paragraphs** (where inline code spans are matched) are runs of non-blank lines outside fenced code that
start at a line that is not indented. Indented lines directly after such a line belong to the paragraph,
as in CommonMark, where an indented line cannot interrupt a paragraph. So a code span may cross them, but
they remain code and are compared literally. Headings, list items and table rows are not split apart from
the lines around them. Code-span matching is therefore an approximation of CommonMark, not a parser.

## Layout pair `bracketed-html` (1.1.0, final empty line since 1.2.0; explicit selection only)

This pair fits one export shape. Nothing about the default layout changed for it, and nothing in it is
inferred. It needs the complete question and an explicit Markdown body start, and it takes neither
`plain_body_start` nor `markdown_definitions_start`. Any other variation is rejected rather than accepted
by widening a rule. HTML is never interpreted, and the logo URL is never fetched. Both inputs are read as
the original bytes.

**Question.** `question` is the complete question, ending with exactly one `\n`. The CLI reads
`--question-file` byte for byte. The Markdown question region runs from line 3 to the line before the
separator that precedes `markdown_body_start`. Its raw bytes must equal `# ` followed by the question's
UTF-8 bytes. Only that leading `# ` is removed: no whitespace is trimmed, and no boundary is located by
searching for the question or the request ID. Mismatches are rejected:

| Code | Meaning |
|---|---|
| `unsupported_question_framing` | the region does not start with `# ` |
| `boundary_swallows_answer` | the region is the question followed by more lines, which would then be neither question nor compared body (`swallowed_lines`) |
| `boundary_cuts_question` | the region ends inside the question |
| `question_mismatch` | the bytes differ, with the first differing byte and excerpts |

**Plain, `plain-bracketed-sources/1`.** The segments are `body` from line 1, then
`separator_before_sources`, then `sources`:
- `body` starts at line 1; there is no preamble.
- `separator_before_sources` is exactly one empty line.
- `sources` is one line that is exactly `Sources`, then one or more `[N] title URL` lines with no blank lines
  between them. N is 1–9999 without a leading zero, the title is kept verbatim, and the URL is
  `http(s)://…`.
- `Sources` is found as in the default layout, or given by `plain_sources_line`.

**Markdown, `markdown-html-framed/1`.** Every line outside the body has a fixed role, and each role is a
segment:

| Segment | Exact form |
|---|---|
| `logo` | line 1, exactly `<img src="URL" style="height:64px;margin-right:32px"/>`; URL `http(s)://` without whitespace, `"`, `<` or `>` |
| `separator_after_logo` | line 2, exactly one empty line |
| `question` | from line 3: `# ` and the supplied question (above) |
| `separator_after_question` | exactly one empty line, directly before `markdown_body_start` |
| `body` | from `markdown_body_start` to the line before the next separator |
| `separator_before_hidden_markers` | exactly one empty line |
| `hidden_markers` | exactly `<span style="display:none">[^A][^B]…</span>`: one or more markers, nothing else, each id unique and defined |
| `separator_before_ornament` | exactly one empty line |
| `ornament` | exactly `<div align="center">⁂</div>` (U+2042) |
| `separator_before_definitions` | exactly one empty line |
| `definitions` | `[^N]: URL` lines up to the final definition. Between two definitions there may be zero or one empty line; these lines stay in this segment and are listed in its `separator_lines` |
| `separator_after_definitions` | since 1.2.0, optional: present only when the file ends with exactly one empty line after the final definition (the single byte `\n`). It is its own segment and is never part of `definitions` or its `separator_lines`; without it, the output is as in 1.1.0 |

**Separators.**
- Every separator above is required and is exactly one empty line: no spaces, and not inside code.
- There are two optional separators, each at most one exactly empty line: between two definitions, and
  after the final definition (`separator_after_definitions`).
- A missing or whitespace-only separator is `unsupported_separator`. This includes a final line that holds
  only spaces or tabs, with or without its line feed.
- A blank line next to a separator is `repeated_separator`. This includes two or more blank lines after the
  final definition.
- Non-blank text after the final definition is `unsupported_trailer_line`.
- The body's first and last lines are therefore never blank.

**Rejected inside the body (outside code):**
- a `display:none` span opener anywhere on a line, or an ornament line (`unsupported_html`);
- footnote definition lines (`definition_outside_block`).

**Other rejections:**
- a different logo or prelude line: `unsupported_prelude_line`;
- a trailer line that is not the expected element: `unsupported_trailer_line`;
- non-marker text in the hidden span: `unsupported_hidden_content`;
- a repeated hidden id: `duplicate_hidden_marker`;
- an undefined hidden id: `undefined_hidden_marker`.

**Results specific to this pair.** Body comparison, policy, protection and raw/normalized equality are those
of the default layout, applied to the two `body` segments. `raw_bodies_equal` therefore compares the bodies
without their separators. The pair adds or changes these fields:
- `results.question`:
  - `supplied` (text, byte count, SHA-256);
  - per export, `region` (`null` for plain, which has no question region; for Markdown its lines, its
    framing, and `equals_supplied_after_framing`);
  - `literal_occurrences`, the count of the question's exact bytes in each whole document.

  Question presence in a document is reported separately from the supplied context, and the plain export's
  missing region gives the `question_absent` warning.
- `results.request_id.occurrences`: literal counts in each whole document, in each named segment
  (`plain_body`, `markdown_question`, `markdown_body` and so on) and in the supplied question. There are
  `present_in_*` booleans for both documents, both bodies, the Markdown question and the supplied question.
  Counts never depend on whether a question was found.
- `results.citations.hidden_markers`: the span's line and ids, and which of them the Markdown body also
  cites. Hidden markers are not body citations and not evidence that anything was read; the
  `hidden_markers_not_citations` warning says so.
- `results.citations.entries_url_map`: every listed or defined id, cited or not. Each entry has both URLs,
  exact equality, whether either body cites it, and whether it is a hidden marker.
- `uncited_entries`, `source_titles_only_in_plain` and `all_entries_url_map_equal` are as in the default
  layout.
- `semantic_judgment` and `producer_authenticity` remain `NOT_ESTABLISHED`.

Consumers must tell the pairs apart by `layouts.plain.layout` and `layouts.markdown.layout`. The default
layout's output is unchanged: the 1.0.0 and 1.0.1 recorded outputs are reproduced byte for byte apart from
`tool.version`.

**Change in 1.2.0.** 1.1.0 rejected a final empty line after the definitions as `unsupported_trailer_line`.
Since 1.2.0, `bracketed-html` accepts exactly one such line and reports it as `separator_after_definitions`.
- **Request IDs.** The segment then also has its count, `request_id.occurrences.markdown_separator_after_definitions`.
- **Unchanged.** Nothing else changed: the plain layout, the other separators, the question, body and
  hidden-marker checks, every comparison field, and the default layout. All recorded 1.0.0, 1.0.1 and
  1.1.0 outputs are reproduced byte for byte apart from `tool.version`.

## Normalization policy `export-compare-body-policy/1` (bodies only)

| Rule | Effect |
|---|---|
| `citation_markers` | `[N]` in the plain body and `[^N]` not followed by `:` in the Markdown body (N 1–9999, no leading zero, not after a backslash; the plain form not followed by `(`) both become `⟦cite N⟧`. Detection of cited ids does not depend on this rule being enabled. |
| `escaped_hash` | `\#` becomes `#` in the Markdown body. |
| `table_separator_rows` | The delimiter row directly under a header row with the same cell count becomes `\|---\|` form, keeping alignment colons. Header and data rows are unchanged. |
| `blank_lines` | Whitespace-only lines count as blank; each run of blank lines becomes one empty line; blank lines at the start and end of a body are dropped. Paragraph separation (blank versus none) is kept. |

No rule is applied to code, to inline code spans (matching backtick runs, also across the lines of one
paragraph), to URLs (`http(s)://` up to whitespace), or to anything outside the bodies. These protected
spans are computed once per paragraph and bind every rule, the row-based `table_separator_rows` included.
A delimiter row is normalized only if three things lie outside every protected span: the line break before
its header row, the line break before the delimiter row itself, and the delimiter row. So rows that sit
inside a code span, or are indented, are never treated as a table. A code span that lies wholly inside a
header cell does not prevent normalization.

GitHub-flavored Markdown finds tables before it finds code spans, so a renderer may show such rows as a
table. Here they stay literal and are reported as a difference, never as a match. Everything else is
compared exactly, including Unicode (no NFC/NFKC or case folding), numbers, URLs, line breaks inside a
paragraph, emphasis and trailing spaces.

`rules` may name a subset of the four (stricter; a `policy_rules_disabled` warning is added). Naming any
rule in the unsafe catalogue is rejected as `unsafe_normalization`, with its reason:
`case_fold`, `unicode_nfc`, `unicode_nfkc`, `collapse_inline_whitespace`, `join_paragraphs`,
`ignore_line_order`, `resolve_citations_by_url`, `url_normalization`, `normalize_inside_code`,
`strip_markdown_formatting` and `ignore_numbers`. Any other name is `unknown_normalization`.

## Result fields

- `inputs`: per export, the raw SHA-256, bytes, lines and final newline.
- `layouts`: segments with line and byte ranges and SHA-256, the logo URL, and the boundaries given.
- `normalization`:
  - the policy, the rules applied and their texts, and what is never normalized;
  - per-rule counts;
  - the normalized body's SHA-256 and line count.
- `results`:
  - **Equality:** `raw_documents_equal`; `raw_bodies_equal`, the exact equality of the raw bytes of the
    two `body` segments reported in `layouts` (their byte ranges, including the final line ending, if any);
    and `normalized_bodies_equal`. The fields are independent: equal normalized bodies may have unequal
    raw bytes.
  - **Body differences:** `body_difference_count` and `body_differences`, which are difflib opcodes over
    normalized lines with raw line numbers. A one-line replacement also gets `words`, the changed tokens,
    with `ascii()` forms when non-ASCII.
  - **`citations`:**
    - `referenced_ids_equal` and `reference_counts_equal`;
    - `url_map`, per cited id: both URLs, exact equality, reference counts, and the first differing
      character;
    - `url_map_equal`, covering cited ids only;
    - `all_entries_url_map_equal`, covering every listed source and definition;
    - `undefined_references`, `plain_listed_not_cited` (with titles) and `markdown_defined_not_referenced`
      (with `hidden`);
    - the full `plain_sources` (number, title, URL, line) and `markdown_definitions` (number, URL, hidden,
      line).
  - **`question`:** where each export's question comes from (`supplied`, `preamble` or `absent` for plain;
    `heading` or `absent` for Markdown), its texts, and `supplied_equals_markdown_heading`, an exact
    comparison or `null`.
  - **`request_id`:** `null` unless one is given. It holds non-overlapping literal matches of the ID's
    UTF-8 bytes per exact region (whole plain document, preamble, body, sources; whole Markdown document,
    prelude, question heading, body, definitions; supplied question), plus `present_in_*` booleans.
    - The counts do not depend on whether a question was found: a missing question never implies that the
      ID is absent from a body.
    - Question presence, request-ID presence and producer authenticity are separate fields.
  - `semantic_judgment` and `producer_authenticity` are always `NOT_ESTABLISHED`.
- `warnings`: `source_titles_only_in_plain` (title information the Markdown export does not carry),
  `uncited_entries`, `undefined_references`, `question_absent`, `markers_in_code_not_counted`,
  `foreign_marker_syntax`, `final_newline_differs`, `body_differences_truncated` and
  `policy_rules_disabled`.
- `not_established`, `notice`.

## Limits (explicit; exceeding one is a structured rejection, never truncation of a verdict)

| Limit | Value | On excess |
|---|---|---|
| each export | 262,144 bytes and 2,000 lines | `input_too_large` (the CLI reads at most limit + 1 bytes) |
| question | 4,096 bytes | `input_too_large` |
| request ID | 256 bytes, one line, non-empty | `input_too_large` / `invalid_option` |
| listed body differences | 100 difflib opcodes | `body_difference_count` stays exact; warning `body_differences_truncated` |
| word-level detail | lines of at most 2,000 characters | `words` omitted for that difference |
| CLI output | 4,194,304 bytes | `output_too_large` (exit 2) |

Excerpts of offending lines in errors are at most 200 characters.

## Rejection codes

`input_not_bytes`, `input_too_large`, `unsupported_bom`, `not_utf8`, `unsupported_line_ending`,
`unsupported_control_character`, `reserved_character`, `unclosed_code_fence`, `boundary_not_found`,
`ambiguous_boundary`, `invalid_boundary`, `unsupported_bibliography_line`, `duplicate_source_number`,
`ambiguous_question_heading`, `unsupported_prelude_line`, `unsupported_definition_line`,
`definition_outside_block`, `duplicate_definition`, `unsupported_html`, `invalid_option`,
`unsafe_normalization`, `unknown_normalization`, `invalid_arguments`, `input_unreadable`,
`output_too_large`.

Only with `bracketed-html`: `unsupported_separator`, `repeated_separator`, `unsupported_question_framing`,
`boundary_swallows_answer`, `boundary_cuts_question`, `question_mismatch`, `unsupported_trailer_line`,
`unsupported_hidden_content`, `duplicate_hidden_marker`, `undefined_hidden_marker`.

## Corrections from 1.0.0

1.0.1 changes no field, rule text, policy ID or rejection, and no output for the 38 recorded 1.0.0 runs
apart from `tool.version`. It corrects three ways in which 1.0.0 did not do what this contract already said:

1. **C1 (reported by the requester).** The `table_separator_rows` pass ignored protected spans. So
   table-like rows inside a multi-line inline code span were normalized, and two different code spans could
   compare equal (`--- | ---` against `---|---`, exit 0). Now the table pass uses the same protected spans
   as the other rules.
2. **Sibling found while reproducing C1.** A paragraph ended at an indented line. So a code span opened
   before the indented line was not matched with its closing backticks after it. A marker inside the span
   was then normalized and counted as a citation (`` `refs[1] `` / `` `refs[^1] ``, exit 0). Now the
   paragraph runs on through indented lines (see **Paragraphs**).
3. **C2 (reported by the requester).** `raw_bodies_equal` compared the body lines joined by `\n`, which
   loses the final line ending. So `b'Body.\n'` and `b'Body.'` were reported equal. Now it compares the exact
   bytes of the reported body segments.
