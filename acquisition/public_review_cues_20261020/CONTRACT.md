# Contract: `review_cues` 1.1.0 (schema `review-cues/1`, ruleset `review-cues-lexicon` 1.0.0)

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
- CLI: `python3 review_cues/review_cues.py [--rules PATH] < request.json > response.json`.
  Request: a UTF-8 JSON object with exactly `text` (string) and `language` (`"es"`, `"en"` or
  `"es+en"`). Response: UTF-8 JSON. Exit status 0 with a result, 2 with `{"schema", "error": {"code",
  "message"}}`.
- Request limits (CLI only; checked in this order, each before any parsing):
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
| `invalid_arguments` | CLI arguments other than `--rules PATH` |

The empty string is valid input (no matches).

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

- Output of `find_cues` for any input: unchanged except `tool.version` (`1.1.0`) and therefore
  `configuration_sha256`. The lexicon, matching, offsets, notes, observations, notice and the
  `configuration` object are unchanged byte for byte; the overlap relation and its order are the same.
- CLI: two new rejections, `request_too_large` and `json_too_deep`. No valid request is affected.
  Invalid requests that 1.0.0 rejected with another code are reported as `json_too_deep` when nested
  more than 64 levels deep. Requests that made 1.0.0 crash now get a structured rejection: unbounded
  reads, and deep nesting (`RecursionError`).
- Not changed: `--rules PATH` parsing, which can still raise raw Python exceptions on a malformed rule
  file and does not reject an empty phrase (with one, the search never terminates).
