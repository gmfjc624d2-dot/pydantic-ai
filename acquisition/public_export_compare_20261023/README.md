# Export comparison aid (`public-export-comparison-20261023-01`)

A small, standard-library-only (CPython ≥ 3.9), MIT-licensed function and CLI. It compares a plain-text copy
and a Markdown export of one research answer and reports these as separate fields:
- raw equality;
- body equality under a narrow, named normalization policy, with every remaining difference;
- cited-URL agreement;
- uncited entries;
- question presence;
- request-ID presence.

Two layout pairs are recognized: `numbered`, the default, and `bracketed-html` since 1.1.0, which must be
selected explicitly. It is a deterministic textual aid, not a semantic-equivalence judge or a Markdown
framework.
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
| | 1.0.1 (correction): code `4ed30a0ed684dfa5e32b9d91ae2f556c1af64498`, report and `results/linux-x86_64/v1.0.1/` `545c79db5d018351f7ba0d2269a8f139c0fb3ddf` |
| | 1.1.0 (`bracketed-html` layout): code `1f13d341a9e43c107b161e56aed0deb6dca9c823`, report and `results/linux-x86_64/v1.1.0/` `8a5d69476ddaa2bc8f18f93218671c8ddcbaf950` |
| | 1.2.0 (final empty line in `bracketed-html`): code `f3aca4e62eddda13e3b81eca20d8f70f53b5ec31`; this report and `results/linux-x86_64/v1.2.0/` in the commit after it (its ID is given in the hand-off message and by `git log`) |

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
stdout apart from the version (`tests/check_1_0_0_outputs.py` at `4ed30a0`; `tests/check_recorded_outputs.py` since
1.1.0).

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

## Layout extension `bracketed-html` (1.1.0)

**Why it exists.** The requester's consumer receives one export shape that the default recognizer
rejects, correctly. That rejection was not a bug. 1.1.0 adds that shape as one more layout pair, selected
only with `layout='bracketed-html'` (`--layout bracketed-html`). The synthetic sample is
`fixtures/bracketed_html_*`, and the contract is the "Layout pair `bracketed-html`" section of
[`CONTRACT.md`](CONTRACT.md).

**Contract delta, in short.**
- **Plain export:** `[N] title URL` sources after `Sources`.
- **Markdown export,** in this order:
  - the exact `<img … style="height:64px;margin-right:32px"/>` logo line;
  - a `# `-framed question, possibly several paragraphs, which must equal the supplied complete question
    byte for byte, final `\n` included;
  - the body, starting at an explicit `markdown_body_start`;
  - a `display:none` span that holds footnote markers only;
  - the exact `⁂` ornament line;
  - the footnote definitions.
- **Segments and separators.** Every line outside the bodies is a named segment with its own hash. Every
  separator is required and is exactly one empty line, except at most one optional empty line between two
  definitions.
- **What is rejected:**
  - mismatches, swallowed answer text and a cut question (each with its own code);
  - repeated or whitespace-only separators;
  - any other logo, span or ornament form;
  - text inside the span;
  - a span or ornament inside the body.
- **Hidden markers** are reported separately and are never body citations.
- **Every listed or defined entry is compared** (`entries_url_map`). Exit 0 in this mode also requires
  `all_entries_url_map_equal`.
- **Question and request ID.** Question presence per document is reported apart from the supplied text.
  Request IDs are counted literally per segment.
- **Default layout.** Its output is unchanged.

**Where the existing recognizer conflicted, and how it was resolved within this mode, without a new
abstraction:**
- **Question file.** The default CLI drops one trailing `\n` from `--question-file`. This mode needs the
  question's exact bytes, final `\n` included, so here the file is used as it is.
- **Question field.** The default `results.question.plain.source` says `supplied` when only the caller
  supplied a question. This mode reports document presence (`region`, `literal_occurrences`) separately from
  `supplied`, so its `results.question` has its own shape. Consumers tell the pairs apart by
  `layouts.*.layout`.
- **Exit status.** The default exit status covers only cited ids. Here the hidden span refers to uncited
  entries, so a changed uncited URL also gives exit 1.

The rest reuses the repaired 1.0.1 comparator unchanged: segments, body comparison, protection and policy.
Two parallel recognizer functions were added beside the default ones. A wider parser was not needed.

**Not established.** Consumer adoption is not established, and macOS is not qualified. The mode accepts the
given shape and rejects every variation tested. That does not show that the consumer's real exports always
take this shape.

## Final empty line in `bracketed-html` (1.2.0)

**Requester's report (their observation, not a run here).**
- **Fixture:** 1.1.0 accepted the exact public `bracketed_html` fixture in a fresh directory on macOS with
  CPython 3.9.6 (exit 0).
- **Consumer original:** 1.1.0 rejected it with `unsupported_trailer_line`. It has one extra empty line after
  its final footnote definition. This was an unsupported variation, not a false agreement.
- **Reproducer:** fully public; it is `fixtures/bracketed_html_markdown.md` with exactly `b'\n'` appended.
  The consumer export was neither requested nor transmitted.

**Change.**
- **Accepted:** only in `bracketed-html`, the Markdown file may end with zero or one exactly empty line after
  the final definition.
- **Reporting:** when that line is present it is its own segment, `separator_after_definitions` (for the
  reproducer: line 22, bytes 412–413). It is not part of `definitions` or its `separator_lines`, and it
  gets its own request-ID count.
- **No rewriting:** nothing is stripped or rewritten.
- **Still rejected:**
  - two or more final blank lines: `repeated_separator`;
  - a final line of spaces or tabs: `unsupported_separator`;
  - trailing text: `unsupported_trailer_line`.
- **Unchanged:**
  - the plain bibliography, for which there is no evidence;
  - every other separator check, and the question, body and hidden-marker checks;
  - the public API and the default layout.
- **Recorded outputs:** all 1.0.0, 1.0.1 and 1.1.0 outputs are reproduced byte for byte apart from the
  version.
- **Kept evidence:** the 1.1.0 rejection of the reproducer is kept in
  `results/linux-x86_64/v1.2.0/final_empty_line.log`.

**Coverage.**
- **Five cases:** the reproducer, two final empty lines, a space line, a tab line and trailing text.
- **One test** shows that the added byte is in exactly one segment. Everything else, including URL maps,
  literal ID counts, warnings and the `NOT_ESTABLISHED` fields, equals the result for the unchanged fixture.
- **Four mutations** must each fail the tests: the 1.1.0 rejection, over-acceptance of trailing blank lines,
  the line counted twice, and the line counted nowhere.

**Requester's earlier macOS observations (attribution only).** With 1.0.1 on CPython 3.9.6, in a fresh
directory, they report:
- 21 unit tests passed and 8 mutations were detected;
- 38 old-output comparisons matched;
- the C1/C2 repairs held on the focal cases.

These are their observations, not macOS runs made here, and they do not qualify 1.2.0.

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
| `fixtures/` | synthetic example.org pairs: `full_*` (logo, question with request ID, table, code with literal markers, escaped `#`, hidden definitions), `minimal_*`, `id_in_body_*` (`public-example-1` in the copied body without a question), `bracketed_html_*` (the requester's 1.1.0 sample: plain, Markdown and complete question, byte for byte); `cases.py` (35 single-edit default cases, 27 `FRAMED_CASES` for `bracketed-html`, 9 exact-byte `REGRESSIONS` pairs from 1.0.1, `write_cli_inputs()` and `describe()`) |
| `tests/test_export_compare.py` | unit tests, including CLI subprocesses, the rejected design, the 1.0.1 `Corrections` and `BracketedHtmlLayout` |
| `tests/mutation_check.py` | each of 16 broken variants must fail the tests (3 restore 1.0.0 behaviours, 4 loosen `bracketed-html`, 4 mishandle the 1.2.0 final empty line); lists the failing tests |
| `tests/run_cases.py` | runs every pair, case and regression pair through the real CLI, and times worst-case shapes |
| `tests/check_recorded_outputs.py` | checks that the module reproduces a recorded run set (1.0.0, 1.0.1 or 1.1.0) apart from the version; it replaces 1.0.1's `check_1_0_0_outputs.py` |
| `results/linux-x86_64/` | 1.0.0 raw outputs and `RUN.md`; `v1.0.1/` (the 1.0.0 failures and the 1.0.1 results); `v1.1.0/`; `v1.2.0/` (Linux only) |

## Commands

From `acquisition/public_export_compare_20261023/` with any CPython ≥ 3.9 and no installation:

```bash
python3 -m unittest discover -s tests -v
python3 tests/mutation_check.py
python3 tests/run_cases.py "$(mktemp -d)"
python3 export_compare.py --plain fixtures/full_plain.txt --markdown fixtures/full_markdown.md \
  --question-file fixtures/full_question.txt --request-id req-20261023-0001
python3 export_compare.py --layout bracketed-html --plain fixtures/bracketed_html_plain.txt \
  --markdown fixtures/bracketed_html_markdown.md --question-file fixtures/bracketed_html_question.txt \
  --markdown-body-start 7 --request-id public-layout-2
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

**Isolated `bracketed-html` check** (fresh directory, only `export_compare.py` and `LICENSE`; it writes the
requester's three synthetic files byte for byte, with no checkout on the path):

```bash
SRC=acquisition/public_export_compare_20261023          # in a checkout of the 1.2.0 code commit
DEST="$(mktemp -d)"
cp "$SRC/export_compare.py" "$SRC/LICENSE" "$DEST/" && cd "$DEST" || exit 1
python3 -I - <<'PY'
import hashlib
from pathlib import Path
files = {
    'question.txt': b'Public source comparison. ID: public-layout-2.\n\nCompare the exports; do not infer semantic sufficiency.\n',
    'plain.txt': b'ID: `public-layout-2`.\n\nThe value is not guaranteed.[1]\n\n| Item | Value |\n| --- | --- |\n| A | 2 |\n\n'
    b'Sources\n[1] Guide https://example.org/a\n[2] Extra https://example.org/b\n',
    'markdown.md': '<img src="https://example.org/logo.png" style="height:64px;margin-right:32px"/>\n\n'
    '# Public source comparison. ID: public-layout-2.\n\nCompare the exports; do not infer semantic sufficiency.\n\n'
    'ID: `public-layout-2`.\n\nThe value is not guaranteed.[^1]\n\n| Item | Value |\n|---|---|\n| A | 2 |\n\n'
    '<span style="display:none">[^2]</span>\n\n<div align="center">⁂</div>\n\n'
    '[^1]: https://example.org/a\n\n[^2]: https://example.org/b\n'.encode('utf-8'),
}
for name, data in files.items():
    Path(name).write_bytes(data)
    print(name, hashlib.sha256(data).hexdigest()[:12])
PY
ls
ARGS="--layout bracketed-html --plain plain.txt --markdown markdown.md --question-file question.txt --request-id public-layout-2"
python3 -I export_compare.py $ARGS --markdown-body-start 7 > result.json; echo "exit $?"
python3 -I -c 'import json; r = json.load(open("result.json")); x = r["results"]; c = x["citations"]; o = x["request_id"]["occurrences"]; print(r["tool"]["version"], x["raw_bodies_equal"], x["normalized_bodies_equal"], [e["id"] for e in c["url_map"]], [e["id"] for e in c["entries_url_map"]], c["hidden_markers"]["ids"], o["plain_body"], o["markdown_question"], o["markdown_body"], o["markdown_document"], x["semantic_judgment"], x["producer_authenticity"])'
python3 -I export_compare.py $ARGS --markdown-body-start 9 > rejected.json; echo "exit $? $(python3 -I -c 'import json; print(json.load(open("rejected.json"))["error"]["code"])')"
python3 -I -c 'open("markdown.md", "ab").write(b"\n")'     # the public reproducer: exactly one final empty line
python3 -I export_compare.py $ARGS --markdown-body-start 7 > result2.json; echo "exit $?"
python3 -I -c 'import json; r = json.load(open("result2.json")); x = r["results"]; s = r["layouts"]["markdown"]["segments"]; print(r["tool"]["version"], [(t["name"], t["first_line"], t["byte_start"], t["byte_end"]) for t in s[-2:]], x["normalized_bodies_equal"], [e["id"] for e in x["citations"]["entries_url_map"]], x["request_id"]["occurrences"]["markdown_separator_after_definitions"])'
python3 -I -c 'open("markdown.md", "ab").write(b"\n")'     # a second final empty line stays rejected
python3 -I export_compare.py $ARGS --markdown-body-start 7 > rejected2.json; echo "exit $? $(python3 -I -c 'import json; print(json.load(open("rejected2.json"))["error"]["code"])')"
```

Expected output with 1.2.0:
- the hashes `5e87f555f327`, `fe9fc4f85122` and `c8735a8afe2f`;
- `exit 0`, then `1.2.0 False True [1] [1, 2] [2] 1 1 1 2 NOT_ESTABLISHED NOT_ESTABLISHED`;
- `exit 2 boundary_swallows_answer`;
- after one final empty line is appended: `exit 0`, then
  `1.2.0 [('definitions', 19, 355, 412), ('separator_after_definitions', 22, 412, 413)] True [1, 2] 0`;
- after a second one: `exit 2 repeated_separator`.

With 1.1.0, the first three lines are the same apart from the version, and the appended empty line gives
`exit 2` (`unsupported_trailer_line`).

The first `1.2.0 …` line gives, in order:
- the version;
- raw, then normalized, body equality;
- the cited ids, then all entry ids, then the hidden-marker ids;
- request-ID counts in the plain body, the Markdown question, the Markdown body and the whole Markdown
  document;
- the semantic judgment and the producer authenticity.

## Results 1.2.0 (Linux x86_64 only; clean worktree of `f3aca4e`)

Full record: [`results/linux-x86_64/v1.2.0/RUN.md`](results/linux-x86_64/v1.2.0/RUN.md).
- **Tests:** on CPython 3.9.25 and 3.13.16, 25 / 25 tests pass and 16 / 16 mutations are rejected.
- **CLI:** all 75 runs gave their expected exit status with empty stderr (0: 12, 1: 26, 2: 37). Their stdout
  was byte-identical between the two interpreters.
- **Recorded outputs:** reproduced byte for byte apart from the version: 1.0.0 (38), 1.0.1 (47) and
  1.1.0 (70).
- **Reproducer** (the fixture plus `b'\n'`), in fresh directories:
  - 1.1.0 gives `exit 2` (`unsupported_trailer_line`);
  - 1.2.0 gives `exit 0`, with fields identical to the unchanged fixture plus the separate segment.
  - With 1.2.0, `\n\n`, a space line, a tab line and trailing text give `exit 2`.
- **Isolated check:** the output above, on both interpreters.

## Results 1.1.0 (Linux x86_64 only; clean worktree of `1f13d34`)

Full record: [`results/linux-x86_64/v1.1.0/RUN.md`](results/linux-x86_64/v1.1.0/RUN.md).
- **Tests:** on CPython 3.9.25 and 3.13.16, 24 / 24 tests pass and 12 / 12 mutations are rejected.
- **CLI:** all 70 runs gave their expected exit status with empty stderr (0: 11, 1: 26, 2: 33). Their
  stdout was byte-identical between the two interpreters. The runs are 4 positive pairs, 35 default cases,
  22 `bracketed-html` cases and 9 regression pairs.
- **Default layout unchanged:** all 38 recorded 1.0.0 runs and all 47 recorded 1.0.1 runs are reproduced
  byte for byte, apart from the version.
- **Isolated `bracketed-html` check:** the output above, on both interpreters.

What a reader sees for the sample pair (`results/linux-x86_64/v1.1.0/python3.13/cases.md`):

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

`framed_uncited_entry_url_changed` gives exit 1 with
`[2] listed entry URL differs at character 20: 'b' -> 'c' (not cited; hidden marker)`.

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

Then run:
- `python3 tests/check_recorded_outputs.py results/linux-x86_64 1.0.0`;
- `python3 tests/check_recorded_outputs.py results/linux-x86_64/v1.0.1 1.0.1`;
- `python3 tests/check_recorded_outputs.py results/linux-x86_64/v1.1.0 1.1.0`;
- both fresh-directory commands above: the default one and the isolated `bracketed-html` check.

Expected for 1.2.0:
- 25 tests OK, 16 mutations rejected, and `75 CLI runs; unexpected exit status or stderr output: []`;
- `identical apart from the version: 38`, then `: 47`, then `: 70`;
- the `stdout_sha256` values in `$OUT/cases.jsonl` match `results/linux-x86_64/v1.2.0/python3.*/cases.jsonl`;
- the isolated check prints what is listed above.

The requester's macOS observations do not qualify any version here: C1/C2 on 1.0.0, the 1.0.1 suite, and
the 1.1.0 fixture and consumer runs.

Apple's `/usr/bin/python3` is 3.9.x; any CPython ≥ 3.9 works. Timings will differ.

## Residual limits

- **Two layout pairs only.**
  - A plain copy that renders tables as tab-separated text, drops code fences, or uses `Sources:` is
    rejected or differs; it is never accepted by guessing.
  - `[N] title URL` entries are accepted only with `bracketed-html`. That mode's title is everything
    before the URL, so `[1] Title - URL` has the title `Title -`.
  - `bracketed-html` takes one fixed shape: one logo style, one ornament, one hidden span, and single empty
    separators. Since 1.2.0, one exactly empty final line is also accepted. Real exports that vary in other
    ways are rejected; this needs a contract change, not a looser rule.
  - In `bracketed-html`, a `display:none` opener anywhere on a body text line is rejected, even inside
    inline code (over-rejection).
  - The question's `literal_occurrences` counts the whole question's bytes in each whole document; it
    proves nothing about where or why they occur.
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
