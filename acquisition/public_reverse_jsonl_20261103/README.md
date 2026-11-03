# Reverse JSON Lines reader (`public-reverse-jsonl-20261103-01`)

A small, standard-library-only (CPython ≥ 3.9), MIT-licensed module, `reverse_lines.py`. It reads an
append-only UTF-8 JSON Lines file from the newest line to the oldest. It stops when the caller's predicate
stops it, and it reads only the bytes that the lines consumed need. Contract: [`CONTRACT.md`](CONTRACT.md).

## Identity

| | |
|---|---|
| Operation | `public-reverse-jsonl-20261103-01`, a new and independent task |
| Repository and branch | `gmfjc624d2-dot/pydantic-ai`, `claude/sweet-carson-tjohp1` (public research fork) |
| Base commit | `cff32132bed68aeea55544ad663ff4cbced15e03`, the finished `public-export-comparison-20261023-01`, unchanged |
| Scope | only `acquisition/public_reverse_jsonl_20261103/`; no library code and no earlier acquisition is touched |
| Code commit | `5756e959cb03ab9a7681c18ef3aa180f364f1b76`, with `reverse_lines.py` SHA-256 `6ee5107635c4f5a511f75e8753affb7ed7ea01e7fd260732e02acf727ac7e858` |
| Results commit | this report and `results/` are in the commit after it; its ID is given in the hand-off message and by `git log` |

## The question, answered

**Can reverse iteration reproduce the logical lines of
`open(path, encoding='utf-8', errors='replace', newline=None)` in reverse order, on a fixed regular-file
extent?**

Yes, under the stated conditions, and with evidence rather than proof.

- **Why line ends are safe.** CR (0x0D) and LF (0x0A) are ASCII. In UTF-8 they never occur inside a character,
  and they always end an invalid run. So the raw bytes can be split at CRLF, CR or LF from the end, and each
  line can be decoded on its own with `errors='replace'`. The result is the same characters text mode
  produces.
- **What is delimited.** CR, LF and CRLF delimit; U+2028, U+2029, VT, FF and U+0085 do not.
- **Edge lines.** No empty line is invented after a final line end, and an initial empty line is kept.
- **Terminators.** They are **both preserved and normalized**: `RawLine.terminator` keeps the raw bytes, and
  `RawLine.text()` turns any terminator into `'\n'`, as text mode does. An unterminated last line has
  `terminator == b''`, so a record still being appended can be recognized.
- **Conditions.**
  - The bytes `[0, end)` must not change while they are read. There is no atomic snapshot; see CONTRACT.md for
    appends, truncation, in-place rewrites and path replacement.
  - Memory grows with the longest line read, unless `max_line_bytes` makes that an explicit error.
  - Failures raise; they never end the iteration as if it had completed.
- **Evidence.** All of it was gathered on Linux with CPython 3.9.25 and 3.13.16, against the forward text-mode
  reference:
  - every string of up to 4 bytes over CR, LF, `a`, E2, 82 and AC, at chunk sizes 1 to 5;
  - 2,000 random documents with a fixed seed;
  - every prefix extent of a test document;
  - 20 named cases;
  - SHA-256 equality over a 34 MB file;
  - 11 source mutations, each of which the tests reject.

**Is a maintained public implementation sufficient?** Not for this contract. I tested `file_read_backwards`
3.2.0, the latest release (PyPI, 2025-04-21, MIT, upstream `https://github.com/RobinNil/file_read_backwards`),
against the same reference:
- **Where it works:** its line contents are right for every valid-UTF-8 document tested.
- **Where it falls short:**
  - every document with invalid UTF-8 raises `UnicodeDecodeError`;
  - it drops line ends, so `a` and `a\n` cannot be told apart;
  - it is quadratic on long lines (0.7–1.2 s for one 4 MiB line, against 0.006 s here);
  - when the file was truncated while it was being read, it returned 17 lines with no error.

It remains reasonable for short, valid-UTF-8 lines when neither line-end information nor detection of
changes is needed.

Identity of what was tested:
- the sdist `file_read_backwards-3.2.0.tar.gz`, SHA-256
  `5478d305ebaeaae8fe3c6585a24dfc3262170224450acc9321398f0d26cdd109`, which matches PyPI's digest;
- the module files' hashes, which are in `results/linux-x86_64/python3.*/candidate_file_read_backwards.json`.

The git revision behind the sdist was not checked. The package was never installed and is not vendored here.

## Using it

```python
import reverse_lines as rl

with rl.ReverseLineReader('events.jsonl') as reader:           # extent = file size now
    streak = 0
    for record in rl.reverse_json_records(iter(reader), malformed='report'):
        if record.error is not None:                            # explicit policy: decide, do not skip silently
            if record.line.terminator == b'':                   # a partly written newest record
                continue
            raise ValueError(f'bad record at byte {record.line.start}: {record.error}')
        if record.value.get('status') != 'ok':
            break
        streak += 1
    print(streak, 'records;', reader.bytes_read, 'of', reader.extent, 'bytes read')
```

Here the caller chose to skip only the unterminated last line; that is their decision, not the module's.
`reverse_text_lines(path)` yields plain strings. `max_line_bytes=` bounds memory. `observed_changes()` reports
size, mtime and path changes seen afterwards; it is a heuristic, not a snapshot check.

## Files

| Path | Contents |
|---|---|
| `reverse_lines.py` | the module; the only runtime file |
| `LICENSE` | MIT, copied from the repository root |
| `CONTRACT.md` | interface, the equivalence claim and its evidence, line ends, cost, failures, snapshot limits, JSON policy |
| `tests/test_reverse_lines.py` | unittest suite against the forward reference: known, exhaustive, random, prefix, early-stop, failure, snapshot and JSON cases |
| `tests/mutation_check.py` | 11 source edits to a copy of the module; each must fail the suite |
| `bench/measure.py` | large synthetic scenarios: early stop, fixed-tail comparison, full equivalence, a 16 MiB line, dense line ends |
| `evaluation/fetch_candidate.py` | downloads the `file_read_backwards` 3.2.0 sdist, checks its SHA-256 and unpacks it, without executing it |
| `evaluation/file_read_backwards_eval.py` | the differential evaluation of that package |
| `results/linux-x86_64/` | `RUN.md`, raw logs and JSON for both interpreters, and the text-mode probe from before any code was written |

**Provenance.**
- All code and data here were written for this task; every input is synthetic and generated by the scripts.
- No private source or data was used, and no third-party code is included.
- `LICENSE` is the repository's MIT license.

## Linux results

The full record is in [`results/linux-x86_64/RUN.md`](results/linux-x86_64/RUN.md); it covers clean worktree
`5756e95` on CPython 3.9.25 and 3.13.16.

- **Tests:** 18 / 18 tests pass, and 11 / 11 mutations are rejected.
- **Early stop:**
  - The newest streak of 5,000 "ok" records in a 34,066,282-byte file was found after reading 524,288 bytes,
    in 8 reads, in 0.015–0.020 s.
  - A forward full scan needs every byte and took 0.46–0.59 s.
  - A fixed 64 KiB tail reports **639**, silently shortening the streak.
- **Full reverse pass:** the same lines as the reversed forward reference (identical SHA-256, 332,768 lines),
  with about 134 KB peak traced memory, against about 51 MB for the forward list.
- **Long line:** a 16 MiB line needed about 33.7 MB. With `max_line_bytes` = 1 MiB it failed after reading
  1,114,112 bytes.

## macOS qualification (not done here)

The Linux tests above say nothing about macOS. In a checkout of `5756e95` on the Mac, copy the needed files to
an independent directory and run them with the system Python (3.9.6 or any CPython ≥ 3.9). Only the standard
library is needed.

```bash
SRC=acquisition/public_reverse_jsonl_20261103              # in a checkout of 5756e959cb03ab9a7681c18ef3aa180f364f1b76
DEST="$(mktemp -d)/reverse" && mkdir -p "$DEST"
cp -R "$SRC/reverse_lines.py" "$SRC/LICENSE" "$SRC/tests" "$SRC/bench" "$SRC/evaluation" "$DEST/"
cd "$DEST" && /usr/bin/python3 -VV && shasum -a 256 reverse_lines.py
/usr/bin/python3 -m unittest discover -s tests -v 2>&1 | tail -3
/usr/bin/python3 tests/mutation_check.py
/usr/bin/python3 bench/measure.py bench.jsonl               # needs about 40 MB of temporary disk space
# optional, downloads from PyPI:
/usr/bin/python3 -I evaluation/fetch_candidate.py candidate \
  && /usr/bin/python3 -I evaluation/file_read_backwards_eval.py candidate/file_read_backwards-3.2.0 candidate.json
```

Expected:
- the SHA-256 `6ee5107635c4…`;
- `Ran 18 tests` … `OK`;
- every mutation `rejected`;
- in `bench.jsonl`:
  - streak 5,000 with `bytes_read` 524,288 and a fixed-tail streak of 639;
  - `"equal": true`, with SHA-256 `345fc1001bb65408…`;
  - `LineTooLongError` with `bytes_read_at_failure` 1,114,112;
- the candidate evaluation should give the same outcomes as on Linux.

Known differences on macOS:
- `ru_maxrss` is reported in bytes, not KiB;
- the `/proc/self/io` measurement reports "not measured";
- temporary files are under `/var/folders`;
- timings will differ.

A failing or different result there is a macOS finding to record, not to be explained away.

## Limits (see CONTRACT.md)

- **Snapshot:** there is no atomic snapshot. An in-place rewrite inside the extent is not detected and can mix
  old and new bytes. Truncating a part already read, or truncating and re-growing the file, is invisible to
  reads.
- **Memory:** not constant. A line is held whole: about twice its size in bytes, plus its decoded text.
- **Speed:** pure Python, at about 1 µs per line. A full reverse pass is slower than reading forward; the gain
  is in stopping early.
- **What was tested:** only CPython 3.9.25 and 3.13.16 on Linux. Not tested: PyPy, Windows, and network or
  FUSE filesystems.
- **JSON:** `json.loads` semantics apply (it accepts `NaN`; the last of duplicate keys wins). Whether the
  records are semantically correct, and whether concurrent use is safe, are not established.
