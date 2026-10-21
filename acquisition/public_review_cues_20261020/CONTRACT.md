# Contract: `review_cues` 1.2.0 (schema `review-cues/1`, ruleset `review-cues-lexicon` 1.0.0)

## Purpose and non-goals

Marks **lexical candidates** for six review topics — `condition`, `exception`, `negation`,
`uncertainty`, `attribution`, `obligation` — in Spanish and English text, for a human preparing
source-grounded notes. A highlight means "a configured phrase occurs here". The tool never infers
scope, the identity of a speaker or source, entailment, semantic completeness, permission, or an
acceptance verdict. **An empty highlight list means no configured cue matched, not that the text has
no relevant qualification.** The lexicon is small and makes no coverage claim.

## Interfaces

- Function: `find_cues(text: str, language: str, ruleset: Ruleset | None = None) -> dict`
  (pure: no I/O except reading the default rule file once; same input → same output).
- Function: `render_cues(text, language, ruleset=None, max_output_bytes=None) -> bytes`: exactly the
  bytes the CLI writes for a successful request, optionally within a byte budget (see
  [Output byte budget](#output-byte-budget-opt-in-120)).
- CLI: `python3 review_cues/review_cues.py [--rules PATH] [--max-output-bytes N] < request.json > response.json`
  (each option at most once, any order). Request: a UTF-8 JSON object with exactly `text` (string) and
  `language` (`"es"`, `"en"` or `"es+en"`). Response: UTF-8 JSON on stdout. Exit status 0 with a result,
  2 with `{"schema", "error": {"code", "message", ...}}`; the one exception is an unusable
  `--max-output-bytes` value (below).
- Request limits (CLI only; order: byte limit, UTF-8 decoding, nesting limit, then JSON parsing):
  - **At most `MAX_REQUEST_BYTES` = 1,265,536 bytes** (12 × 100,000 + 65,536). Twelve bytes is the
    longest JSON spelling of one code point (an escaped surrogate pair such as `\ud83d\udccc`), so every
    text within the code-point limit fits in any spelling, with 64 KiB left for keys, the language value
    and whitespace. Standard input is read in chunks of at most 64 KiB and never beyond limit + 1 bytes;
    a larger request is rejected (`request_too_large`) without reading the rest, so a producer still
    writing may see a broken pipe.
  - **At most `MAX_JSON_NESTING` = 64 levels of `[`/`{` nesting**, counted outside JSON strings (an
    unterminated string runs to the end of the input). A valid request nests one level. Deeper input is
    rejected (`json_too_deep`) because Python's `json` module raises `RecursionError` at a depth that
    depends on the interpreter and the call stack (run as a script, 1.0.0 exited with status 1 and a
    traceback from 994 levels on CPython 3.9.25 and from 9,999 levels on 3.13.16; a 2,201-byte array
    nested 1,100 levels deep was reported on CPython 3.9.6). Because nesting is checked before parsing,
    malformed input nested more than 64 levels deep is reported as `json_too_deep`, not `invalid_json`.
  - **JSON integers of more than `MAX_INT_DIGITS` = 640 digits are never passed to `int()`**; they are
    kept as an exact `decimal.Decimal` (linear time), which, like any number, no field accepts. This
    avoids both the `ValueError` of interpreters that limit integer string conversion and the quadratic
    conversion of interpreters that do not (see "Changes from 1.0.0").
- Standard library only; Python ≥ 3.9 (tested on CPython 3.9.25 and 3.13.16, Linux only).

## Input validation (explicit rejection, never repair)

| Code | Condition |
|---|---|
| `text_not_string` | `text` is not a `str` (includes bytes, numbers, `null`, lists, booleans) |
| `invalid_language` | `language` not exactly one of `es`, `en`, `es+en` (case-sensitive) |
| `text_too_long` | more than 100,000 code points (part of the configuration) |
| `text_not_utf8_encodable` | the string contains a lone surrogate (e.g. JSON `"\ud800"`) |
| `request_too_large` | CLI input is longer than 1,265,536 bytes (nothing is decoded or parsed) |
| `stdin_not_utf8` | CLI input bytes are not valid UTF-8 |
| `json_too_deep` | CLI input nests `[`/`{` more than 64 levels outside strings (checked before parsing) |
| `invalid_json` | not parseable JSON, including empty input and a leading UTF-8 BOM |
| `invalid_json_constant` | `NaN`, `Infinity`, `-Infinity` |
| `duplicate_key` | a JSON object repeats a key |
| `request_not_object` | the JSON value is not an object |
| `missing_field` / `unknown_field` | fields other than exactly `text` and `language` |
| `invalid_arguments` | CLI arguments other than `--rules PATH` and `--max-output-bytes N`, each at most once |
| `invalid_output_budget` | the budget is not an integer from 512 to 999,999,999,999,999 (CLI: also not written exactly as `[1-9][0-9]{0,14}`); on the CLI written to stderr, not stdout |
| `output_too_large` | the complete output would exceed the requested budget; extra fields `max_output_bytes` and `output_bytes_at_least` |

The empty string is valid input (no matches).

## Output byte budget (opt-in, 1.2.0)

- **What is counted.** `render_cues()` returns, and the CLI writes, `json.dumps(result, ensure_ascii=False,
  indent=2)` encoded as UTF-8 (no BOM) followed by one LF (`0x0A`). The budget bounds the length of that
  byte string, final newline included. It counts bytes, not code points (`ú` is 2 bytes, `📌` is 4).
  Under a valid CLI budget, every byte written to stdout, result or rejection, is within the budget.
  stderr is not counted.
- **Default unchanged.** Without a budget, `find_cues()` and the CLI behave as in 1.1.1 (same bytes apart
  from the tool version and `configuration_sha256`).
- **If it fits, the same bytes.** When the complete output is at most N bytes, it is returned
  byte-identical to the unbudgeted output. The budget is not recorded in the result and does not change
  `configuration_sha256`.
- **If it does not fit, `output_too_large`, never part of a result.** The error object carries
  `max_output_bytes` (N) and `output_bytes_at_least`, a lower bound of the complete size (> N; values
  above 10¹⁵ are reported as 10¹⁵). It is not the exact size and says nothing about how many matches
  exist, because the tool stops as soon as it can prove the output cannot fit.
- **How it stops early.** A lower bound L of the rendered size is checked three times:
  1. while matching: L = the compact JSON size of the result without matches, plus 1 for the newline,
     plus 305 bytes per match found so far (`_MATCH_FLOOR_BYTES`, the compact size of the smallest
     possible match object);
  2. after matching, before any overlap list is built: L grows by 1 byte per overlap reference (2 per
     overlapping pair), counted by bisection without building lists;
  3. while rendering: the exact UTF-8 size of each piece produced by the `json` module's own encoder
     (`JSONEncoder(ensure_ascii=False, indent=2).iterencode`, which yields the same text as `json.dumps`),
     plus the newline; rendering stops at the first piece that crosses N.

  L never exceeds the true size: compact JSON (separators `, ` and `: `) is never longer than the
  indented rendering of the same object; every match has the template's keys with values at least as
  long (strings ≥ `""`, offsets ≥ 0, lists ≥ `[]`, the same `basis`); each overlap index has at least
  one digit. So a complete output that fits is never rejected (tested at N−1, N and N+1 on 202 inputs).
- **Budget validation.** For `render_cues()`, the budget must be an `int`, not a `bool`, from
  `MIN_OUTPUT_BYTES` = 512 to `MAX_OUTPUT_BYTES` = 999,999,999,999,999; otherwise `invalid_output_budget`.
  On the CLI, `N` must be ASCII digits matching `[1-9][0-9]{0,14}` (no sign, spaces, underscores, leading
  zeros, exponent or decimal point) and at least 512. A rejected value is never echoed, however long.
- **Budget too small or unusable (CLI).** A `--max-output-bytes` value that is malformed or below 512
  (the size that every rejection envelope written under a budget fits in) is the one case where **nothing
  is written to stdout**. The `invalid_output_budget` envelope goes to stderr (one JSON object and
  `\n`) and the exit status is 2. Stdout therefore never exceeds a requested budget, even one too small
  for an error envelope.
- **Rejections under a valid budget** are written to stdout as usual. If an envelope would exceed N,
  its message is replaced by `message omitted: the complete error does not fit max_output_bytes` and its
  code is kept. Only messages that echo request content can be long: `invalid_language`,
  `duplicate_key` and `unknown_field`. Every envelope with that message, and every `output_too_large`
  envelope, fits in 512 bytes (tested for every code; the largest, `output_too_large` with 15- and
  16-digit numbers, is 322 bytes).
- **Smallest result.** The empty text renders to 2,352 bytes (`"language": "en"`), so budgets below
  about 2.4 KB can only produce rejections.
- **Completeness.** A complete output means every configured cue match and every overlap reference is
  present; it is not semantic completeness (see "Purpose and non-goals").

## Output

Top level: `schema`, `tool` {name, version}, `ruleset` {id, version, `file_sha256` of the rule file
bytes, `canonical_sha256` of its canonical JSON}, `configuration` {language, rule languages applied,
limit, **Unicode database version of the running Python**, matching policy text},
`configuration_sha256` (SHA-256 of canonical JSON of schema, tool version, ruleset canonical hash and
configuration), `input` {`sha256` of the exact UTF-8 bytes, `codepoints`, `utf8_bytes`},
`match_count`, `matches`, `notice`.

Each match: `text` (the exact original substring), `start`/`end` (half-open Python code-point
indices), `byte_start`/`byte_end` (half-open UTF-8 byte indices), `review_topics` (candidate topics;
order carries no meaning), `rule_id`, `rule_language`, `phrase` (as listed in the rules),
`matched_forms` (`as_listed`/`NFC`/`NFD`), `uncertainty` {`basis`, `rule_notes` (ambiguities of the
rule), `observations` (facts about this substring: letter case, line breaks, non-space whitespace,
decomposed spelling, Unicode case equivalence)}, `overlaps` (ascending indices of every other match
`o` with `o.start < end` and `start < o.end`).
Invariants (tested): `text == input[start:end] == utf8[byte_start:byte_end].decode()`; matches sorted
by (start, end, rule_id); overlap lists are symmetric and equal a brute-force all-pairs check.

Overlap computation (1.1.0): since matches are sorted by start, the later matches meeting match `i`
are exactly those from `i + 1` up to the first start ≥ `end_i`, found by bisection; each pair is also
recorded on the later match. Cost is O(m log m + p) for m matches and p overlapping pairs; disjoint
matches are never compared pairwise. p is half the total length of all `overlaps` lists, so it is
bounded by the output itself.

## Documented matching behavior

| Topic | Behavior |
|---|---|
| Source coordinates | The input is never normalized, trimmed, re-encoded or newline-converted. Offsets and substrings refer to the exact input. |
| Offsets | Code points as in Python `str` indexing — not UTF-16 code units (JavaScript), not grapheme clusters. An emoji such as 👨‍👩‍👧 is 5 code points and 18 UTF-8 bytes. |
| Token boundaries | After a match: the next code point must not be alphanumeric, `_` or a combining mark (a mark would modify the cue's last letter: decomposed `sí` does **not** match `si`). Before a match: skipping any combining marks, the previous code point must not be alphanumeric or `_` (so `áunless` and decomposed `áunless` do not match, while emoji, variation selectors, ZWJ, skin-tone modifiers, punctuation, BOM and whitespace do not block). Digits count as alphanumeric (`2if` does not match). |
| Suffix rule | `n't` / `n’t` must follow an alphanumeric host (`isn't`, `can’t`); a bare `n't` does not match. The host auxiliary is not reported by that rule. |
| Multiword cues | Words are separated by one or more code points matched by Python `re` `\s`: space, TAB, CR, LF, CRLF, NBSP and other Unicode spaces. The returned substring keeps the original separator (`provided\r\nthat`). Zero-width space, hyphens, underscores and no separator do not match. |
| Case | Case-insensitive through Python `re.IGNORECASE` (simple case folding). Besides ordinary case, this treats dotted `İ`, dotless `ı` and long `ſ` as equivalent to `i`/`s` (`nı` matches `ni`, `ſi` matches `si`); such matches carry an observation. `May` (month) matches `may`. Letter case is reported, never used to decide. |
| Composed / decomposed | Each phrase is searched as listed, as NFC and as NFD; `matched_forms` says which. Fully composed or fully decomposed spellings match; partially decomposed text and compatibility characters (full-width letters, ligatures) do not. |
| Emoji before a cue | Does not block the match (`📌According to`, `❤️unless`). Byte offsets then differ from code-point offsets. |
| CRLF | Counted as two code points and two bytes; never stripped; may appear inside multiword cue substrings. |
| Overlaps | Every match of every rule is reported, including nested ones (`Only if` and `if`; `except for` and `except`) and identical spans from both languages under `es+en` (`no`). They reference each other in `overlaps`. No match is suppressed. |
| Language | Only rules of the selected language(s) are applied; there is no language detection. |
| Unicode version | Character properties come from the running Python's Unicode database (13.0.0 on 3.9.25, 15.1.0 on 3.13.16); it is part of `configuration` and hence of `configuration_sha256`, which therefore differs between Python versions even when all matches agree. |

## Identity and reproducibility

The rule file `review_cues/rules_v1.json` is data; its byte hash and canonical hash are returned with
every result. Any change to rules, tool version, language selection, limit or Unicode database
version changes `configuration_sha256`.

## Changes from 1.0.0

- Output of `find_cues` for any input: unchanged except `tool.version` (`1.1.0`, then `1.1.1`, then
  `1.2.0`) and therefore `configuration_sha256`. The lexicon, matching, offsets, notes, observations, notice and the
  `configuration` object are unchanged byte for byte; the overlap relation and its order are the same.
- CLI (1.1.0): two new rejections, `request_too_large` and `json_too_deep`. Requests valid under 1.0.0
  that fit the new bounds (at most 1,265,536 bytes; a valid request nests one level, so the depth bound
  never applies to one) get the same result. **Not every request 1.0.0 accepted is still accepted**:
  JSON allows unlimited insignificant whitespace, so a valid request larger than 1,265,536 bytes is now
  rejected as `request_too_large`, by design. Such a request carries more than 65,421 bytes of
  whitespace: the longest spelling of everything else (100,000 escaped surrogate pairs, fully escaped
  keys and language value, structure) is 1,200,115 bytes. Invalid requests that 1.0.0 rejected with another code
  are reported as `json_too_deep` when nested more than 64 levels deep. Requests that made 1.0.0 crash
  now get a structured rejection: unbounded reads, and deep nesting (`RecursionError`).
- CLI (1.1.1): JSON integers with more than `MAX_INT_DIGITS` = 640 digits (sign excluded) are parsed as
  an exact `decimal.Decimal`, never with `int()`. CPython versions that limit integer string conversion
  (4,300 digits by default; 640 is the lowest configurable limit) made `json.loads` raise `ValueError`
  for longer literals: 1.0.0 and 1.1.0 then exited with status 1 and a traceback (5,000 digits; seen on
  3.9.25 and 3.13.16 here, reported on 3.12.14). Versions without the limit (e.g. 3.9.6) convert such
  literals in quadratic time. No field accepts a number, so these requests now get the code any number
  gets in that position (`text_not_string`, `invalid_language`, `unknown_field`, `duplicate_key`,
  `request_not_object`) on every interpreter. Integers of 640 digits or fewer, floats, constants and
  duplicate keys behave exactly as before, messages included; for longer integers the message names the
  type `Decimal`. No interpreter setting is changed.
- 1.2.0: opt-in output byte budget (`render_cues(max_output_bytes=...)`, `--max-output-bytes N`), new
  codes `invalid_output_budget` and `output_too_large`, `CueInputError.details`, and `main(stderr=...)`.
  Without a budget, CLI stdout is byte-identical to 1.1.1 apart from the tool version and
  `configuration_sha256`: 59 of 60 checked requests (all 48 fixture items, plus success and rejection
  cases). The one exception is the `invalid_arguments` message, whose usage text now names the new option.
- Not changed: `--rules PATH` parsing, which can still raise raw Python exceptions on a malformed rule
  file and does not reject an empty phrase (with one, the search never terminates).
