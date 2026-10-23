# Contract: `export_compare` 1.0.0 (schema `export-compare/1`, policy `export-compare-body-policy/1`)

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
  plain_sources_line=None, markdown_body_start=None, markdown_definitions_start=None, rules=None) -> dict`.
  It is pure and raises `CompareError` (`code`, `message`, `details`) for rejected input.
- `python3 export_compare.py --plain FILE --markdown FILE [--question TEXT | --question-file FILE]
  [--request-id ID] [--plain-body-start N] [--plain-sources-line N] [--markdown-body-start N]
  [--markdown-definitions-start N] [--rules R1,R2]`.
  - It writes one UTF-8 JSON document and a final `\n` to stdout. Nothing goes to stderr.
  - Exit status 0: normalized bodies equal, the same ids cited, every cited id's URL equal, and no
    undefined citation.
  - Exit status 1: any of those differ; the document lists what differs.
  - Exit status 2: rejected, with `{"schema", "error": {"code", "message", ...}}`.
  - A question file loses one trailing `\n`, if present; nothing else is changed.
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

## Normalization policy `export-compare-body-policy/1` (bodies only)

| Rule | Effect |
|---|---|
| `citation_markers` | `[N]` in the plain body and `[^N]` not followed by `:` in the Markdown body (N 1–9999, no leading zero, not after a backslash; the plain form not followed by `(`) both become `⟦cite N⟧`. Detection of cited ids does not depend on this rule being enabled. |
| `escaped_hash` | `\#` becomes `#` in the Markdown body. |
| `table_separator_rows` | The delimiter row directly under a header row with the same cell count becomes `\|---\|` form, keeping alignment colons. Header and data rows are unchanged. |
| `blank_lines` | Whitespace-only lines count as blank; each run of blank lines becomes one empty line; blank lines at the start and end of a body are dropped. Paragraph separation (blank versus none) is kept. |

No rule is applied to code, to inline code spans (matching backtick runs, also across the lines of one
paragraph), to URLs (`http(s)://` up to whitespace), or to anything outside the bodies. Everything else is
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
  - **Equality:** `raw_documents_equal`, `raw_bodies_equal` (body segments before normalization), and
    `normalized_bodies_equal`.
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
