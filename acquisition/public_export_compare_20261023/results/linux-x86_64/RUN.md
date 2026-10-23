# Run record (Linux only; operation `public-export-comparison-20261023-01`)

> **Correction, added with 1.0.1 (2026-10-23).** The data below is unchanged.
>
> - **Reported defects.** The requester reported two counterexamples to the 1.0.0 contract. They observed
>   both on macOS arm64 with CPython 3.9.6, in a fresh directory holding only the module and `LICENSE`.
>   Both are reproduced here on Linux.
>   - **C1:** table-like rows inside a multi-line code span were normalized, so two different code spans
>     were reported equal (exit 0).
>   - **C2:** `raw_bodies_equal` was true for body segments that differ only in the final line ending.
> - **Sibling defect.** A third defect of the same kind was found here: a code span that crosses an
>   indented line.
> - **Effect on this record.** None of the 38 runs below used such inputs. 1.0.1 reproduces all 38 stdout
>   documents byte for byte, apart from the version.
> - **What was wrong.** The 1.0.0 claims that code is never normalized, and that `raw_bodies_equal`
>   compares the body segments, were wrong in general, though not for these runs.
>
> The failures, the fix and the 1.0.1 results are in [`v1.0.1/RUN.md`](v1.0.1/RUN.md).

- Date: 2026-10-23 (UTC). Host: Linux x86_64 cloud container. **Not a macOS result.**
- Repository and branch: `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1`. Base
  `ed6e9b152beeb3a6a9f1c2f419fda940318ca554`.
- Code: commit `4cdf0017b1e10c229e39057b497e80e9606f6cfc`, clean checkout. `export_compare.py` SHA-256
  `27179b6f310b8dc4fbf4933e4accfeb147b5ee33d39fe23ee7c6050a06ea9cb3`.
- Interpreters: `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` (CPython 3.9.25)
  and `/usr/bin/python3` (CPython 3.13.16). Nothing was installed; no network was used.
- Commands, from `acquisition/public_export_compare_20261023/`, for each interpreter `$PY` and `v` in
  {3.9, 3.13}:

  ```bash
  $PY -m unittest discover -s tests -v        > results/linux-x86_64/python$v/unittest.log
  $PY tests/mutation_check.py                 > results/linux-x86_64/python$v/mutation_check.log
  $PY tests/run_cases.py results/linux-x86_64/python$v > results/linux-x86_64/python$v/run_cases.log
  ```

  The relocation commands are in `../../README.md`; their transcript is in `relocation.log`.

## Results

| | CPython 3.9.25 | CPython 3.13.16 |
|---|---|---|
| unit tests | 18 / 18 OK | 18 / 18 OK |
| mutation check | 5 / 5 mutations rejected | 5 / 5 mutations rejected |
| CLI runs (3 positive pairs + 35 cases) | 38: exit status as expected in all, stderr empty in all | same |
| exit statuses | 0: 5, 1: 17, 2: 16 | same |
| fresh-directory relocation | exit 0, then exit 1 after a one-word edit (`'from' -> 'for'`) | same |

All 38 CLI stdout documents were byte-identical between the two interpreters (`stdout_sha256` in
`python3.*/cases.jsonl`).

**Timings of worst-case shapes** (`python3.*/timings.jsonl`; one process each, 120 s timeout,
`compare_exports` time):

| Shape | Inputs (plain / Markdown bytes) | 3.9.25 | 3.13.16 | Output bytes |
|---|---|---|---|---|
| 1,989 lines, all different | 221,701 / 227,657 | 0.056 s | 0.030 s | 744,687 |
| 1,989 lines, mostly one repeated line, sparse changes | 27,935 / 29,874 | 3.56 s | 3.60 s | 43,536 |
| one 220,000-character line, one character differs | 220,045 / 220,035 | 0.027 s | 0.025 s | 447,121 |
| 60,000 / 50,000 markers on one line | 180,041 / 200,030 | 0.100 s | 0.096 s | 1,327,112 |
| 20,000 backtick runs | 180,038 / 200,027 | 0.037 s | 0.038 s | 429,601 |

The repeated-line shape is the slow one: difflib with `autojunk=False` is close to quadratic when most lines
are equal to each other. The 2,000-line input limit bounds it. These timings describe this host only and
are not guarantees.

## Files

- `python3.{9,13}/unittest.log`, `mutation_check.log`, `run_cases.log`;
- `cases.jsonl`, with one row per CLI run: exit status, expected exit status, stdout and stderr byte counts,
  stdout SHA-256, and key fields or the error code;
- `cases.md`, the readable account of each run;
- `positive_{full,minimal,id_in_body}.json`, the complete results;
- `timings.jsonl`;
- `relocation.log`.
