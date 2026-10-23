# Run record 1.2.0 (Linux only; operation `public-export-comparison-20261023-01`)

- Date: 2026-10-23 (UTC). Host: Linux x86_64 cloud container. **Not a macOS result.**
- Repository and branch: `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1`.
- Code: commit `f3aca4e62eddda13e3b81eca20d8f70f53b5ec31`, run from a clean detached worktree of that commit.
  `export_compare.py` SHA-256 `ee58d96b7445c1cfdc144924e10b12b90d6735f16a896c8053f23c390ed77b8e`.
- Builds on 1.1.0: code `1f13d341a9e43c107b161e56aed0deb6dca9c823`, report
  `8a5d69476ddaa2bc8f18f93218671c8ddcbaf950`, record `../v1.1.0/RUN.md`. The only change is in the
  `bracketed-html` Markdown trailer: one exactly empty final line after the final definition is accepted as
  its own segment, `separator_after_definitions`.
- Interpreters: `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` (CPython 3.9.25)
  and `/usr/bin/python3` (CPython 3.13.16). Nothing was installed; no network was used.

## Why (requester's report)

The requester ran 1.1.0 on macOS with CPython 3.9.6 in a fresh directory:
- **Public fixture:** accepted (exit 0).
- **Consumer original:** rejected with `unsupported_trailer_line`. It has one extra empty line after its
  final footnote definition. The original was neither requested nor transmitted.

The public reproducer is `fixtures/bracketed_html_markdown.md` with exactly `b'\n'` appended. The plain
fixture, the question fixture and body start 7 are unchanged.

## The 1.1.0 rejection, kept

`final_empty_line.log` (script: `final_line_via_cli.py`) runs the public fixtures with each of six suffixes
appended to the Markdown: `''`, `'\n'`, `'\n\n'`, `' \n'`, `'\t\n'` and `'\nEnd.\n'`. Each run is in a
fresh directory holding only the module, `LICENSE` and the three inputs, on both interpreters.

| Suffix | 1.1.0 (`1f13d34`) | 1.2.0 (`f3aca4e`) |
|---|---|---|
| none | exit 0 | exit 0, identical fields |
| `\n` (the reproducer) | exit 2 `unsupported_trailer_line` | exit 0; `separator_after_definitions` = line 22, bytes 412–413 |
| `\n\n` | exit 2 `unsupported_trailer_line` | exit 2 `repeated_separator` |
| ` \n` (space) | exit 2 `unsupported_trailer_line` | exit 2 `unsupported_separator` |
| `\t\n` (tab) | exit 2 `unsupported_trailer_line` | exit 2 `unsupported_separator` |
| `\nEnd.\n` | exit 2 `unsupported_trailer_line` | exit 2 `unsupported_trailer_line` |

For the reproducer, 1.2.0 reports the same fields as for the unchanged fixture:
- `raw_bodies_equal` false and `normalized_bodies_equal` true;
- cited ids `[1]`; entries `[1, 2]`, both equal; hidden markers `[2]`;
- request-ID counts 1 (plain body), 1 (Markdown question), 1 (Markdown body) and 2 (Markdown document);
- semantic judgment and producer authenticity `NOT_ESTABLISHED`.

## Results

Commands, from `acquisition/public_export_compare_20261023/` in the worktree, for each interpreter `$PY`
and `v` in {3.9, 3.13}:

```bash
$PY -m unittest discover -s tests -v                              > v1.2.0/python$v/unittest.log
$PY tests/mutation_check.py                                       > v1.2.0/python$v/mutation_check.log
$PY tests/run_cases.py v1.2.0/python$v                            > v1.2.0/python$v/run_cases.log
$PY tests/check_recorded_outputs.py results/linux-x86_64 1.0.0         > v1.2.0/python$v/check_recorded_outputs.log
$PY tests/check_recorded_outputs.py results/linux-x86_64/v1.0.1 1.0.1 >> v1.2.0/python$v/check_recorded_outputs.log
$PY tests/check_recorded_outputs.py results/linux-x86_64/v1.1.0 1.1.0 >> v1.2.0/python$v/check_recorded_outputs.log
```

| | CPython 3.9.25 | CPython 3.13.16 |
|---|---|---|
| unit tests | 25 / 25 OK | 25 / 25 OK |
| mutation check | 16 / 16 rejected; the 4 new ones restore the 1.1.0 rejection, over-accept trailing blank lines, count the final line twice, or count it nowhere | same |
| CLI runs (4 positive pairs, 35 default cases, 27 `bracketed-html` cases, 9 regression pairs) | 75: exit status as expected in all, stderr empty in all | same |
| exit statuses | 0: 12, 1: 26, 2: 37 | same |
| recorded outputs reproduced apart from `"version"` | 1.0.0: 38 / 38; 1.0.1: 47 / 47; 1.1.0: 70 / 70 | same |
| isolated `bracketed-html` check (`relocation.log`) | as 1.1.0, then `exit 0` with `separator_after_definitions` at line 22, bytes 412–413, then `exit 2 repeated_separator` after a second empty line | same |
| default-layout relocation (`relocation.log`) | exit 0, then exit 1 after a one-word edit | same |

All 75 CLI stdout documents were byte-identical between the two interpreters.

**What the mutations show.**
- **Exactly once:** `test_final_empty_line_is_one_separate_segment` catches the "counted twice" and
  "counted nowhere" mutations. That test requires two things:
  - every other segment, comparison field, warning and literal ID count to equal those of the unchanged
    fixture;
  - the added byte to be in exactly one segment of its own.
- **Over-acceptance:** the two-empty-lines, space and tab cases catch the over-accepting mutation.

Worst-case shapes (`timings.jsonl`, default layout): 0.025–0.10 s, except 1,989 mostly repeated lines, which
took 3.96 s (3.9.25) and 3.71 s (3.13.16). These timings are for this host only.

## Requester observations (attribution only)

The requester reports these runs, made on macOS with CPython 3.9.6 in a fresh directory:
- 1.0.1: 21 unit tests passed, 8 mutations detected, 38 old-output comparisons matched, and the C1/C2
  repairs held on the focal cases.
- 1.1.0: the public fixture was accepted.

These are their observations; nothing here was run on macOS.

## Not established here

- **macOS:** 1.2.0 is not qualified on macOS.
- **Consumer exports:** not every consumer export is shown to be accepted. Only this one variation is
  added, and other variations are still rejected.
- **Plain bibliography:** unchanged, because there is no evidence for changing it.
- **Judgments:** semantic judgment and producer authenticity remain `NOT_ESTABLISHED`.
