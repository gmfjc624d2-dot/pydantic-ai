# Run record (Linux only; operation `public-reverse-jsonl-20261103-01`)

## Identity

- **Date and host:** 2026-11-03 (UTC), Linux x86_64 cloud container (`Linux-6.18.44-fc-v230-x86_64-with-glibc2.39`).
  **Not a macOS result.**
- **Repository and branch:** `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1`.
- **Code:** commit `5756e959cb03ab9a7681c18ef3aa180f364f1b76`, run from a clean detached worktree of that
  commit. `reverse_lines.py` SHA-256 is `6ee5107635c4f5a511f75e8753affb7ed7ea01e7fd260732e02acf727ac7e858`.
- **Interpreters** (`python3.*/interpreter.txt`). Both are CPython; no other implementation was run:
  - CPython 3.9.25, `/root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9` (Clang 21.1.4);
  - CPython 3.13.16, `/usr/bin/python3` (GCC 13.3.0).
- **Installation and network:**
  - Nothing was installed.
  - The only network access was the hash-checked download of the `file_read_backwards` 3.2.0 sdist, made by
    `evaluation/fetch_candidate.py` (`fetch_candidate.log`).

## Commands

From `acquisition/public_reverse_jsonl_20261103/` in the worktree, for each interpreter `$PY` and `v` in
{3.9, 3.13}, with `TMPDIR` set to a session scratch directory:

```bash
$PY -I evaluation/fetch_candidate.py "$SCRATCH/frb_run"          # once, with CPython 3.13.16
$PY -m unittest discover -s tests -v          > results/linux-x86_64/python$v/unittest.log
$PY tests/mutation_check.py                   > results/linux-x86_64/python$v/mutation_check.log
$PY bench/measure.py results/linux-x86_64/python$v/bench.jsonl > results/linux-x86_64/python$v/bench.log
$PY -I evaluation/file_read_backwards_eval.py "$SCRATCH/frb_run/file_read_backwards-3.2.0" \
    results/linux-x86_64/python$v/candidate_file_read_backwards.json > results/linux-x86_64/python$v/candidate_file_read_backwards.log
```

`relocation.log` rehearses the README's copied-directory (macOS) commands on Linux with CPython 3.9.25: the
unit tests and the mutation check run from a fresh copy. It shows that the commands work. It is not a macOS
result.

## Results

| | CPython 3.9.25 | CPython 3.13.16 |
|---|---|---|
| unit tests | 18 / 18 OK | 18 / 18 OK |
| mutation check | 11 / 11 source mutations rejected | same |
| early stop: newest "ok" streak in a 34,066,282-byte file of 332,768 records | streak 5,000; 524,288 bytes read in 8 reads; 0.020 s | streak 5,000; 524,288 bytes read in 8 reads; 0.015 s |
| the same streak by a forward full scan | 5,000; all 34,066,282 bytes; 0.46 s | 5,000; 0.59 s |
| the same streak from a fixed 64 KiB tail | **639** (silently short) | **639** |
| full reverse pass versus the forward reference, reversed | equal (SHA-256 `345fc1001bb65408…`, 332,768 lines); 0.55 s versus 0.21 s | equal; 0.41 s versus 0.11 s |
| peak traced memory, full pass: reverse versus forward list | 133,432 versus 53,312,256 bytes | 133,902 versus 50,650,328 bytes |
| one 16,777,152-byte line, no limit | peak traced memory 33,654,997 bytes | 33,655,633 bytes |
| the same with `max_line_bytes` = 1 MiB | `LineTooLongError` after 1,114,112 bytes read | same |
| 8 MiB of only LF / CRLF / CR | 8,388,608 / 4,194,304 / 8,388,608 lines in 9.50 / 5.38 / 8.73 s; peak about 133 KB | in 7.81 / 3.76 / 7.78 s; peak about 134 KB |

Measurement notes:
- **Timing.** Times are from untraced runs. Peak memory is tracemalloc's peak in a second, traced run. These
  numbers describe this host only.
- **Subprocess peaks.** `ru_maxrss` per scenario subprocess is in `bench.jsonl`; on Linux it is in KiB.

**`file_read_backwards` 3.2.0, evaluated with the same reference** (`candidate_file_read_backwards.json`; the
same on both interpreters):
- **Contents.** For the 269 valid-UTF-8 documents in the corpus, at chunk sizes 1, 2, 3, 5 and 8192, line
  contents were equal in 1,345 / 1,345 runs. For the invalid-UTF-8 documents, all 16,430 runs raised
  `UnicodeDecodeError`. The package has no `errors='replace'` option.
- **Line ends.** `b'a'`, `b'a\n'`, `b'a\r\n'` and `b'a\r'` all give `['a']`. An unterminated, partly written
  last line cannot be told from a complete one.
- **Long lines** (time in seconds, chunk size 8,192 for both):

  | Line length | `file_read_backwards` (3.9 / 3.13) | `reverse_lines` (3.9 / 3.13) |
  |---|---|---|
  | 0.25 MiB | 0.0044 / 0.0025 | 0.0003 / 0.0003 |
  | 4 MiB | 1.15 / 0.71 | 0.0055 / 0.0068 |

  The candidate's time roughly quadruples with each doubling, because it re-concatenates and re-scans its
  buffer.
- **Truncation.** The file was truncated from 10,000 to 100 bytes after the first line had been read:
  - `file_read_backwards` returned 17 lines without any error, ending with lines from the truncated file;
  - `reverse_lines` raised `ExtentChangedError` after 6 lines.
- **Read bytes for 10 lines** (Linux `/proc/self/io` `rchar`): 8,316 for both. That includes about 130 bytes
  of reading `/proc/self/io` itself. `reverse_lines` counted 8,192.

## Raw observations and failures along the way

- **Text-mode probe.** `observations/probe_text_mode.py` and its log were run before any code was written. On
  21 edge cases, Python's text mode and the candidate rule agreed on both interpreters: split the raw bytes at
  CRLF|CR|LF, decode each piece on its own, add `'\n'` to terminated pieces.
- **First test run: 7 errors and failures.** All were mistakes in the tests, not in the module:
  - opening a directory raises `ValueError` ("not a regular file"), not `OSError`;
  - `iter()` was called twice on one reader;
  - the offset check did not allow for an empty file;
  - one expected list was miscounted: `b'\n\r\n\r\n\r'` has 4 lines, not 5;
  - the in-place-rewrite test read the old bytes before the rewrite. It now uses chunk size 1 and observes the
    mixed line `'AAAa\n'`.
- **First mutation run.** "CR position not rescanned" made the module yield empty lines forever. Because some
  tests used plain `list(reader)`, it was caught only by the 300 s subprocess timeout. Every test now bounds
  what it collects, and the mutation fails quickly.
- **First benchmark.** Frozen dataclasses for `RawLine` and timing under tracemalloc made 8 MiB of line ends
  take 45–73 s. `RawLine` became a `NamedTuple`, and timing is now done without tracing.
- **Candidate download.** The first download used `pip download --no-binary :all:`, which ran the package's
  `setup.py` to prepare metadata. The recorded evaluation instead uses `evaluation/fetch_candidate.py`, which
  only downloads, checks the SHA-256 and unpacks. The two unpacks were identical.
- **Fetcher warning.** On CPython 3.13.16 the fetcher prints a `DeprecationWarning`, because `extractall` is
  called without `filter=` (`fetch_candidate.log`). Members are validated before extraction.

## Not established here

- **macOS:** not run.
- **Other environments:** PyPy, other CPython versions, Windows, and network or FUSE filesystems.
- **Concurrency and correctness:** safe concurrent use, and semantic correctness of any data, are not
  established. Hashes and green tests do not show them.
