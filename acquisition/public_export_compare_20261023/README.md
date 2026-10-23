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
| Result commits | recorded in `results/linux-x86_64/RUN.md` and below once pushed |

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
| `fixtures/` | synthetic example.org pairs: `full_*` (logo, question with request ID, table, code with literal markers, escaped `#`, hidden definitions), `minimal_*`, `id_in_body_*` (`public-example-1` in the copied body without a question); `cases.py` (35 single-edit adversarial cases and `describe()`) |
| `tests/test_export_compare.py` | unit tests, including CLI subprocesses and the rejected design |
| `tests/mutation_check.py` | each of 5 broken variants must fail the tests |
| `tests/run_cases.py` | runs every pair and case through the real CLI, and times worst-case shapes |
| `results/linux-x86_64/` | raw outputs and `RUN.md` (Linux only) |

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

## Results

Linux x86_64 only. Raw outputs and the run record are in `results/linux-x86_64/`; the summary is added with
them.

## Residual limits

- **Two layouts only.**
  - A plain copy that renders tables as tab-separated text, drops code fences, or uses
    `[1] Title - URL` or `Sources:` is rejected or differs; it is never accepted by guessing.
  - A Markdown answer that itself starts with a `# ` heading is read as having that heading as its
    question, so the comparison reports it as a body difference. Pass `--markdown-body-start 1` to include
    it in the body.
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
- **Platform:** macOS is not qualified; the commands above are the handoff.
