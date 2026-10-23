# Export comparison aid (`public-export-comparison-20261023-01`)

A small, standard-library-only (CPython ≥ 3.9), MIT-licensed function and CLI. It compares a plain-text copy
and a Markdown export of one research answer and reports these as separate fields:
- raw equality;
- body equality under a narrow, named normalization policy, with every remaining difference;
- cited-URL agreement;
- uncited entries;
- question presence;
- request-ID presence.

It is a deterministic textual aid, not a semantic-equivalence judge or a Markdown framework.
`semantic_judgment` and `producer_authenticity` are always `NOT_ESTABLISHED`, and a clean result claims
nothing about authenticity, question identity, truth or completeness of evidence. Contract:
[`CONTRACT.md`](CONTRACT.md).

## Identity and recovery

| | |
|---|---|
| Operation | `public-export-comparison-20261023-01` |
| Repository / branch | `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1` (public research fork) |
| Base commit | `ed6e9b152beeb3a6a9f1c2f419fda940318ca554`: the tip of the earlier, completed review-cue work, unchanged |
| Scope | only `acquisition/public_export_compare_20261023/`; earlier acquisitions are not touched |
| Result commits | 1.0.0: code `4cdf0017b1e10c229e39057b497e80e9606f6cfc`, report and `results/` `4d35b65f82ca9795adbe2df9d58026879836b61c` |
| | 1.0.1 (correction): code `4ed30a0ed684dfa5e32b9d91ae2f556c1af64498`; this report and `results/linux-x86_64/v1.0.1/` in the commit after it (its ID is given in the hand-off message and by `git log`) |

**Interruption (2026-10-23).** The first read-only environment listing of this operation kept showing as
running in the requester's view and was stopped by the requester. That listing was `ls`, `python3 -VV`,
`which`, `uv python list --only-installed`, an `ls` of the session scratch directory, and `git config`. The
output shown had been partial. Before anything was repeated, the state was re-checked with read-only,
time-bounded commands:
- the branch was `claude/sweet-carson-tjohp1` at `ed6e9b1`, identical to `origin`, with a clean tree;
- `acquisition/public_export_compare_20261023/` did not exist yet;
- no `uv` or `python` process was running;
- `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` reported 3.9.25 (Unicode
  13.0.0) and `/usr/bin/python3` reported 3.13.16 (Unicode 15.1.0).

The broad `uv` listing was not run again. The interruption caused no file or git change.

## Corrections (1.0.1)

**Who found what.** After 1.0.0 was pushed, the requester reported two counterexamples to its contract. They
reproduced both themselves on macOS arm64 with CPython 3.9.6, in a fresh directory holding only
`export_compare.py` and `LICENSE`. Both reproduce byte for byte on Linux with CPython 3.9.25 and 3.13.16. A
third defect of the same kind was found here while reproducing the first.

| | Input (plain / Markdown) | 1.0.0 | 1.0.1 |
|---|---|---|---|
| C1 (requester) | ``Value `x \| y⏎--- \| ---⏎z` stays.`` / the same with `---\|---` | exit 0, `normalized_bodies_equal` true, `table_separator_rows` 1/1 | exit 1, the delimiter rows differ, 0/0 |
| C2 (requester) | `b'Body.\nSources\n'` / `b'Body.'` | exit 0, `raw_bodies_equal` **true** | exit 0, `raw_bodies_equal` false, `normalized_bodies_equal` true |
| sibling (found here) | ``See `refs[1]⏎    more` here.`` / the `[^1]` form | exit 0, id 1 counted as cited | exit 1, nothing cited |

**Causes.**
- **C1:** `_Body._paragraph` normalized delimiter rows in a second pass over the joined paragraph lines, and
  that pass ignored the protected spans that the inline pass respected.
- **Sibling:** a paragraph ended at an indented line. So a code span opened before the indented line and
  closed after it was never matched, and the marker inside it was normalized and cited.
- **C2:** `raw_bodies_equal` compared `'\n'.join(lines)`, which loses the final line ending of a segment.

**Fixes** (`4ed30a0`; contract 1.0.1, section "Corrections from 1.0.0").
- **One set of protected spans per paragraph.** It holds the code spans, the URLs and the indented lines,
  and binds every rule, the table rule included.
- **Narrowed table rule.** A delimiter row is normalized only if the line break before its header row, the
  line break before the delimiter row, and the delimiter row itself are all unprotected.
- **Paragraphs** run on through indented lines, as in CommonMark, and those lines stay literal.
- **Raw equality.** `raw_bodies_equal` is the equality of the exact bytes of the two reported `body`
  segments.

No field, rule text, policy ID or rejection changed. Legitimate tables still normalize, including tables
with a code span inside a header cell or after a closed span. The 38 recorded 1.0.0 runs give byte-identical
stdout apart from the version (`tests/check_1_0_0_outputs.py`).

**Which 1.0.0 statements were wrong.**
- Two statements were wrong in general, though not for any of the 38 recorded runs:
  - "Code (fenced or indented), inline code spans and URLs are never touched";
  - "`raw_bodies_equal` (body segments before normalization)".
- The 1.0.0 results below and in `results/linux-x86_64/RUN.md` are kept as recorded. That file now opens
  with a correction note.

**Evidence of the old failures.** `results/linux-x86_64/v1.0.1/` holds:
- `reproduction_1.0.0.log`, made before the fix;
- `regressions_on_1.0.0.log`;
- `suite_on_1.0.0.log`, in which only the new `Corrections` tests fail.

**Not shown by this repair.** It does not show that any other export layout is supported, nor that the
narrow layouts fit a given consumer. That remains a separate question.

## Design

**Explicit boundaries and a strict recognizer, rather than heuristic extraction.** Each export is split
into segments that partition the raw bytes exactly (`preamble`/`body`/`sources` and
`prelude`/`body`/`definitions`, each with a line range, byte range and SHA-256). The split follows a
recognizer for exactly two layouts:
- plain: a body, one line that is exactly `Sources`, then `N. title URL` entries;
- Markdown: an optional logo line, an optional single `# question` heading, a body, then trailing
  `[^N]: URL` definitions, optionally inside `<span style="display:none">`.

Anything else is rejected with a code and line numbers, never guessed:
- two `Sources` lines;
- `Sources:` as the heading;
- a second `# ` heading;
- a definition in the middle of the body;
- an unclosed span or fence;
- CR line endings, a BOM, invalid UTF-8 or oversized input.

When the recognizer is ambiguous, the caller passes exact 1-based line numbers, which are validated (for
example, `--plain-sources-line` must point at a `Sources` line outside code).

**Narrow policy.** Only four things are normalized, and only in the two bodies:
- the citation-marker syntax (`[N]` and `[^N]` both become `⟦cite N⟧`);
- `\#` escapes in the Markdown body;
- the formatting of the table delimiter row;
- runs of blank lines.

Code (fenced or indented), inline code spans and URLs are never touched. Everything else is compared
exactly: negations, numbers, Unicode, paragraph separation, line order, table data rows and URLs (no case
folding, query or slash normalization). Requesting a broader rule (`unicode_nfkc`, `case_fold`,
`url_normalization`, `ignore_line_order` and seven more) is refused as `unsafe_normalization`, with a reason
and counterexample.

**Separate fields.** `raw_documents_equal`, `raw_bodies_equal`, `normalized_bodies_equal`,
`citations.url_map_equal` (cited ids) and `all_entries_url_map_equal` (every listed or defined entry) are
separate. So are `plain_listed_not_cited`, `markdown_defined_not_referenced` (with `hidden`), titles kept
from the plain export, and the warning that the Markdown export carries no titles. The `question` field and
the `request_id` field are separate too: the request ID is counted literally in every exact region,
whether or not a question was found, and `semantic_judgment` / `producer_authenticity` are separate again.

**Rejected design, kept with its counterexamples** (`naive_equal` in `tests/test_export_compare.py`). It
cut each export at its first line mentioning "sources" or its first `[^N]:` line, rewrote every `[^N]` and
`\#` anywhere, and collapsed whitespace. It agrees on the clean pair, but it also reports these as equal:
- a citation marker rewritten inside a code block (`print(refs[1])` → `print(refs[^1])`);
- an escape removed from indented code;
- two paragraphs joined into one;
- a changed citation URL (`#read` → `#write`);
- a body that loses its condition sentence after a `Sources of error` subheading, because both exports are
  silently cut there.

This tool reports each of these as a difference.

## Files

| Path | Contents |
|---|---|
| `export_compare.py` | the module and CLI (the only runtime file) |
| `LICENSE` | MIT, copied from the repository root |
| `CONTRACT.md` | interfaces, layouts, policy, result fields, limits, rejection codes |
| `fixtures/` | synthetic example.org pairs: `full_*` (logo, question with request ID, table, code with literal markers, escaped `#`, hidden definitions), `minimal_*`, `id_in_body_*` (`public-example-1` in the copied body without a question); `cases.py` (35 single-edit adversarial cases, 9 exact-byte `REGRESSIONS` pairs added in 1.0.1, and `describe()`) |
| `tests/test_export_compare.py` | unit tests, including CLI subprocesses, the rejected design and the 1.0.1 `Corrections` |
| `tests/mutation_check.py` | each of 8 broken variants (3 of them the 1.0.0 behaviours) must fail the tests; lists the failing tests |
| `tests/run_cases.py` | runs every pair, case and regression pair through the real CLI, and times worst-case shapes |
| `tests/check_1_0_0_outputs.py` | checks that the module reproduces the recorded 1.0.0 outputs apart from the version |
| `results/linux-x86_64/` | 1.0.0 raw outputs and `RUN.md`; `v1.0.1/` with the 1.0.0 failures and the 1.0.1 results (Linux only) |

## Commands

From `acquisition/public_export_compare_20261023/` with any CPython ≥ 3.9 and no installation:

```bash
python3 -m unittest discover -s tests -v
python3 tests/mutation_check.py
python3 tests/run_cases.py "$(mktemp -d)"
python3 export_compare.py --plain fixtures/full_plain.txt --markdown fixtures/full_markdown.md \
  --question-file fixtures/full_question.txt --request-id req-20261023-0001
```

**Fresh directory, required files only, existing Python, no checkout on the path:**

```bash
SRC=acquisition/public_export_compare_20261023          # in a checkout of the result commit
DEST="$(mktemp -d)"
cp "$SRC/export_compare.py" "$SRC/LICENSE" "$DEST/"
printf '%s\n' 'Run only if the source is verified[1]. Do not infer permission from a successful read[2].' '' \
  'Sources' '1. Guide https://example.org/guide' '2. Model https://example.org/model' > "$DEST/plain.txt"
printf '%s\n' 'Run only if the source is verified[^1]. Do not infer permission from a successful read[^2].' '' \
  '[^1]: https://example.org/guide' '[^2]: https://example.org/model' > "$DEST/export.md"
cd "$DEST" && ls && python3 -I export_compare.py --plain plain.txt --markdown export.md > result.json; echo "exit $?"
python3 -I -c 'import json; r = json.load(open("result.json"))["results"]; print(r["normalized_bodies_equal"], r["citations"]["url_map_equal"], r["semantic_judgment"], r["producer_authenticity"])'
```

Expected: `exit 0`, then `True True NOT_ESTABLISHED NOT_ESTABLISHED`.

## Results 1.0.1 (Linux x86_64 only; clean worktree of `4ed30a0`)

Full record: [`results/linux-x86_64/v1.0.1/RUN.md`](results/linux-x86_64/v1.0.1/RUN.md).
- **Tests:** on CPython 3.9.25 and 3.13.16, 21 / 21 tests pass and 8 / 8 mutations are rejected.
- **CLI:** all 47 runs gave their expected exit status with empty stderr: 3 positive pairs, 35 single-edit
  cases and 9 regression pairs (0: 9, 1: 22, 2: 16). Their stdout was byte-identical between the two
  interpreters.
- **1.0.0 outputs:** all 38 are reproduced byte for byte apart from the version.
- **Relocation:** the fresh-directory commands below gave `exit 0`, then `exit 1` with `'from' -> 'for'`.

## Results 1.0.0 (Linux x86_64 only; clean checkout of `4cdf001`; see Corrections above)

Full record: [`results/linux-x86_64/RUN.md`](results/linux-x86_64/RUN.md).
- **Tests:** on CPython 3.9.25 and 3.13.16, 18 / 18 tests pass and 5 / 5 mutations are rejected.
- **CLI:** all 38 runs (3 positive pairs and 35 single-edit cases) gave their expected exit status
  (0: 5, 1: 17, 2: 16) with empty stderr. Their stdout was byte-identical between the two interpreters.
- **Relocation:** the fresh-directory commands above gave `exit 0` and then, after a one-word edit,
  `exit 1` with `'from' -> 'for'`.

What a reader sees (from `results/linux-x86_64/python3.13/cases.md`):

```
negation_removed (exit 1)
  normalized bodies equal: False; cited URL map equal: True; semantic judgment: NOT_ESTABLISHED
  body replace (plain 1, markdown 5): ... 'Do not infer permission ...' | ... 'Do infer permission ...'
  changed words: 'not ' -> ''
querystring_changed (exit 1)
  normalized bodies equal: True; cited URL map equal: False
  [1] URL differs at character 41: '1' -> '2'
marker_in_code_rewritten (exit 1)
  body replace (plain 14, markdown 19): plain: 'print(refs[1])' | markdown: 'print(refs[^1])'
unicode_identifier (exit 1)
  changed words: 'source' -> 'sоurce'
title_changed_only_in_plain (exit 0)
  normalized bodies equal: True; cited URL map equal: True; warning source_titles_only_in_plain
ambiguous_sources_boundary (exit 2)
  REJECTED ambiguous_boundary: the plain export has more than one "Sources" line outside code
```

The ID-in-body control (`fixtures/id_in_body_*`, `--request-id public-example-1`) shows that a missing
question does not hide the ID:
- the plain question is `absent` and the Markdown question is a `heading`;
- the ID is still counted in the plain body (`present_in_plain_body: true`, plain document 1) and in the
  Markdown heading and body (Markdown document 2);
- `semantic_judgment` and `producer_authenticity` are `NOT_ESTABLISHED`;
- the exit status is 0, because the bodies and cited URLs agree.

Worst measured time: 3.6 s, for 1,989 mostly identical lines with sparse changes (difflib is near-quadratic
there; the 2,000-line limit bounds it). All other worst-case shapes took 0.03–0.1 s.

**macOS qualification (not done here):** on the Mac, `git fetch` and check out the result commit, then from
`acquisition/public_export_compare_20261023/` run:

```bash
git rev-parse HEAD && python3 -VV && python3 -m unittest discover -s tests -v && python3 tests/mutation_check.py \
  && OUT="$(mktemp -d)" && python3 tests/run_cases.py "$OUT" && echo "outputs in $OUT"
```

Then run `python3 tests/check_1_0_0_outputs.py` and the fresh-directory commands above.

Expected for 1.0.1:
- 21 tests OK, 8 mutations rejected, and `47 CLI runs; unexpected exit status or stderr output: []`;
- `identical apart from the version: 38`;
- the `stdout_sha256` values in `$OUT/cases.jsonl` match `results/linux-x86_64/v1.0.1/python3.*/cases.jsonl`.

Apple's `/usr/bin/python3` is 3.9.x; any CPython ≥ 3.9 works. Timings will differ.

## Residual limits

- **Two layouts only.**
  - A plain copy that renders tables as tab-separated text, drops code fences, or uses
    `[1] Title - URL` or `Sources:` is rejected or differs; it is never accepted by guessing.
  - A Markdown answer that itself starts with a `# ` heading is read as having that heading as its
    question, so the comparison reports it as a body difference. Pass `--markdown-body-start 1` to include
    it in the body.
- **Code spans are matched approximately.**
  - A paragraph here does not separate headings, list items or table rows from the lines next to them, so
    backtick pairing can differ from CommonMark's.
  - GitHub-flavored Markdown finds tables before code spans, so rows that this tool keeps literal inside a
    span (and reports as a difference) may render as a table there.
- **Lines are compared, not paragraphs.** A soft line break inside a paragraph in one export only is a
  difference, though Markdown renders both the same.
- **Over-protection.** A citation marker attached to a URL with no space (`https://example.org/a[1]`) is
  inside the protected URL, so it is compared literally and shows as a difference. Indented list
  continuation lines count as code, so their markers are not normalized either.
- **Request IDs are only searched for, never discovered.** They are found only if the caller gives them,
  and are counted literally (case-sensitive, non-overlapping, no Unicode normalization).
- **Titles are not compared.** Source titles exist only in the plain export, which the report states.
  `all_entries_url_map_equal` covers listed and defined entries, but neither form proves anything about
  evidence.
- **Rejected by design (tested):** CRLF and BOM inputs are rejected rather than converted, and so are
  inputs above 256 KiB or 2,000 lines.
- **Time:** comparing many repeated identical lines is near-quadratic (3.6 s measured at the line limit);
  there is no time limit other than the size limits.
- **Unicode version:**
  - Blank-line detection (`str.strip`), the `\s`/`\S` patterns and word tokenization follow the running
    Python's Unicode database.
  - Unicode 13.0.0 (3.9.25) and 15.1.0 (3.13.16) gave byte-identical outputs in all 38 runs here.
  - A character whose whitespace status differs between Unicode versions could still change a verdict.
- **Platform:** macOS is not qualified; the commands above are the handoff.
