# Run record 1.0.1 (Linux only; operation `public-export-comparison-20261023-01`)

- Date: 2026-10-23 (UTC). Host: Linux x86_64 cloud container. **Not a macOS result.**
- Repository and branch: `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1`.
- Code: commit `4ed30a0ed684dfa5e32b9d91ae2f556c1af64498`, run from a clean detached worktree of that commit.
  `export_compare.py` SHA-256 `bdf94f3e3cb7f65380a2a5de72f1fbda600e41fed864403829bd610d6a24c297`.
- Corrects 1.0.0 (code commit `4cdf0017b1e10c229e39057b497e80e9606f6cfc`, module SHA-256
  `27179b6f310b8dc4fbf4933e4accfeb147b5ee33d39fe23ee7c6050a06ea9cb3`), whose record in `../RUN.md` is kept
  unchanged apart from a correction note.
- Interpreters: `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` (CPython 3.9.25)
  and `/usr/bin/python3` (CPython 3.13.16). Nothing was installed; no network was used.

## The 1.0.0 failures, kept

| File | What it holds |
|---|---|
| `reproduction_1.0.0.log` | The requester's C1 and C2 inputs, byte for byte, through the 1.0.0 CLI on both interpreters, in fresh directories holding only the module, `LICENSE` and the inputs. It was made before any change. |
| `regressions_on_1.0.0.log` | Every 1.0.1 regression pair through the 1.0.0 CLI, the same way (script: `regressions_via_cli.py`). |
| `suite_on_1.0.0.log` | The 1.0.1 test suite against the 1.0.0 module: 9 failures, all in `Corrections`. |

Against 1.0.0 the logs show:
- **C1:** exit 0, `raw_bodies_equal` false, `normalized_bodies_equal` true, `table_separator_rows` 1/1.
  With `--rules citation_markers,escaped_hash,blank_lines`: exit 1, `normalized_bodies_equal` false.
- **C2:** exit 0 and `raw_bodies_equal` true, although the body segments are bytes 0–6
  (`44261ce242e1…`) and 0–5 (`521b25cc4586…`).
- **Sibling, found here:** `` See `refs[1]⏎    more` here. `` against the `[^1]` form gives exit 0, and
  id 1 is counted as cited, although the marker is inside a code span.
- **Two further C1 variants:** a span that opens on the line before the header row, and one that opens in
  the header row, also give exit 0.

These match the requester's macOS observations of C1 and C2. Those observations are theirs, made on
macOS arm64 with CPython 3.9.6; they are not reproduced on macOS here.

## Results 1.0.1

Commands, from `acquisition/public_export_compare_20261023/` in the worktree, for each interpreter `$PY`
and `v` in {3.9, 3.13}:

```bash
$PY -m unittest discover -s tests -v        > v1.0.1/python$v/unittest.log
$PY tests/mutation_check.py                 > v1.0.1/python$v/mutation_check.log
$PY tests/run_cases.py v1.0.1/python$v      > v1.0.1/python$v/run_cases.log
$PY tests/check_1_0_0_outputs.py            > v1.0.1/python$v/check_1_0_0_outputs.log
```

| | CPython 3.9.25 | CPython 3.13.16 |
|---|---|---|
| unit tests | 21 / 21 OK | 21 / 21 OK |
| mutation check | 8 / 8 mutations rejected, including the three 1.0.0 behaviours | same |
| CLI runs (3 positive pairs, 35 cases, 9 regression pairs) | 47: exit status as expected in all, stderr empty in all | same |
| exit statuses | 0: 9, 1: 22, 2: 16 | same |
| 1.0.0 outputs reproduced (`check_1_0_0_outputs.log`) | 38 / 38 byte-identical apart from `"version"` | same |
| regression pairs, fresh directories (`regressions_on_1.0.1.log`) | every exit status as expected | same |
| fresh-directory relocation (`relocation.log`) | exit 0, then exit 1 after a one-word edit (`'from' -> 'for'`) | same |

All 47 CLI stdout documents were byte-identical between the two interpreters.

Worst-case shapes (`timings.jsonl`, `compare_exports` time):

| Shape | 3.9.25 | 3.13.16 |
|---|---|---|
| 1,989 lines, all different | 0.041 s | 0.032 s |
| 1,989 lines, mostly one repeated line | 3.87 s | 3.52 s |
| one 220,000-character line | 0.033 s | 0.027 s |
| 60,000 / 50,000 markers on one line | 0.120 s | 0.103 s |
| 20,000 backtick runs | 0.037 s | 0.043 s |

These timings are for this host only; they are close to the 1.0.0 timings.

## Not established here

- **macOS:** not qualified.
- **Other export layouts:** this repair does not show that any layout beyond the two in `CONTRACT.md` is
  supported, nor that those layouts fit any particular consumer.
- **Judgments:** semantic judgment and producer authenticity remain `NOT_ESTABLISHED`.
