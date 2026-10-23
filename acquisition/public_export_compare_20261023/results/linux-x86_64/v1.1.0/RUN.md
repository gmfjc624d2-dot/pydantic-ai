# Run record 1.1.0 (Linux only; operation `public-export-comparison-20261023-01`)

- Date: 2026-10-23 (UTC). Host: Linux x86_64 cloud container. **Not a macOS result.**
- Repository and branch: `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1`.
- Code: commit `1f13d341a9e43c107b161e56aed0deb6dca9c823`, run from a clean detached worktree of that commit.
  `export_compare.py` SHA-256 `fc73ebbeb6757be9911a7f95fab552676e00f44cc5d9e06fa39c1c520409e038`.
- Builds on 1.0.1 (code `4ed30a0ed684dfa5e32b9d91ae2f556c1af64498`, record `../v1.0.1/RUN.md`). It adds the
  explicitly selected layout pair `bracketed-html`; the default layout is unchanged.
- Interpreters: `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` (CPython 3.9.25)
  and `/usr/bin/python3` (CPython 3.13.16). Nothing was installed; no network was used.

Commands, from `acquisition/public_export_compare_20261023/` in the worktree, for each interpreter `$PY`
and `v` in {3.9, 3.13}:

```bash
$PY -m unittest discover -s tests -v                              > v1.1.0/python$v/unittest.log
$PY tests/mutation_check.py                                       > v1.1.0/python$v/mutation_check.log
$PY tests/run_cases.py v1.1.0/python$v                            > v1.1.0/python$v/run_cases.log
$PY tests/check_recorded_outputs.py results/linux-x86_64 1.0.0         > v1.1.0/python$v/check_recorded_outputs.log
$PY tests/check_recorded_outputs.py results/linux-x86_64/v1.0.1 1.0.1 >> v1.1.0/python$v/check_recorded_outputs.log
```

`relocation.log` holds both README fresh-directory commands, run once per interpreter. Each directory held
only `export_compare.py`, `LICENSE` and the inputs that the command writes:
- the default layout;
- the isolated `bracketed-html` check, which writes the requester's three synthetic files byte for byte.

## Results

| | CPython 3.9.25 | CPython 3.13.16 |
|---|---|---|
| unit tests | 24 / 24 OK | 24 / 24 OK |
| mutation check | 12 / 12 mutations rejected, each listing the tests that caught it | same |
| CLI runs (4 positive pairs, 35 default cases, 22 `bracketed-html` cases, 9 regression pairs) | 70: exit status as expected in all, stderr empty in all | same |
| exit statuses | 0: 11, 1: 26, 2: 33 | same |
| default layout unchanged | 38 / 38 recorded 1.0.0 runs and 47 / 47 recorded 1.0.1 runs byte-identical apart from `"version"` | same |
| isolated `bracketed-html` sample | `exit 0`; then `1.1.0 False True [1] [1, 2] [2] 1 1 1 2 NOT_ESTABLISHED NOT_ESTABLISHED`; then `exit 2 boundary_swallows_answer` for body start 9 | same |
| default-layout relocation | exit 0, then exit 1 after a one-word edit (`'from' -> 'for'`) | same |

All 70 CLI stdout documents were byte-identical between the two interpreters.

The isolated line reads, in order:
- the tool version;
- `raw_bodies_equal`, then `normalized_bodies_equal`;
- the ids the body cites, then all listed or defined ids, then the hidden-marker ids;
- request-ID counts in the plain body, the Markdown question, the Markdown body and the whole Markdown
  document;
- the semantic judgment and the producer authenticity.

The `bracketed-html` cases (`python3.*/cases.md`) are:
- **Differences, exit 1:** a removed negation; a changed inline code value; a URL changed only in an uncited
  entry (`all_entries_url_map_equal` false, `url_map_equal` true); C1, rows in a code span inside the body.
- **Agreement, exit 0:** C2, raw bodies equal only when their bytes are.
- **Rejections, exit 2, with the code each gives:**

  | Variation | Code |
  |---|---|
  | complete question differs in a word | `question_mismatch` |
  | complete question differs only in whitespace | `question_mismatch` |
  | supplied question incomplete | `boundary_swallows_answer` |
  | supplied question lacks its final line feed | `invalid_option` |
  | body start that swallows answer text | `boundary_swallows_answer` |
  | body start that cuts the question | `boundary_cuts_question` |
  | body start missing | `invalid_option` |
  | text in the hidden span | `unsupported_hidden_content` |
  | hidden span in the body | `unsupported_html` |
  | hidden span appended to the logo line | `unsupported_prelude_line` |
  | logo style changed | `unsupported_prelude_line` |
  | undefined hidden id | `undefined_hidden_marker` |
  | repeated separator | `repeated_separator` |
  | ornament missing | `unsupported_trailer_line` |
  | ornament repeated in the body | `unsupported_html` |
  | `N.` entries | `unsupported_bibliography_line` |
  | the same shape under the default layout | `unsupported_bibliography_line` |

Worst-case shapes (`timings.jsonl`, `compare_exports` time, default layout):

| Shape | 3.9.25 | 3.13.16 |
|---|---|---|
| 1,989 lines, all different | 0.044 s | 0.034 s |
| 1,989 lines, mostly one repeated line | 3.29 s | 3.22 s |
| one 220,000-character line | 0.025 s | 0.029 s |
| 60,000 / 50,000 markers on one line | 0.094 s | 0.076 s |
| 20,000 backtick runs | 0.035 s | 0.036 s |

These timings are for this host only.

## Not established here

- **macOS:** not qualified, and the requester's earlier focal macOS observations do not cover 1.1.0.
- **Consumer adoption:** not established. `bracketed-html` fits the one synthetic shape it was given;
  other export variations are rejected, not shown to be supported.
- **Judgments:** semantic judgment and producer authenticity remain `NOT_ESTABLISHED`.
