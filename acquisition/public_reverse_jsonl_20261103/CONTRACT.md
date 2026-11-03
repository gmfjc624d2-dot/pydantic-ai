# Contract: `reverse_lines` 1.0.0

## Purpose and non-goals

`reverse_lines` reads the lines of an append-only UTF-8 text file (such as JSON Lines) from the last line to
the first. It stops as soon as the caller stops, and reads only as far back as the lines consumed need. It is
one module in the standard library only, for CPython ≥ 3.9.

It is **not** an index, a database, a daemon, a "follow" mode, a lock or a snapshot mechanism. It does not
judge whether the lines are semantically correct, and it does not make concurrent writers safe.

## Interface

| Name | What it is |
|---|---|
| `ReverseLineReader(path, *, chunk_size=65536, end=None, max_line_bytes=None)` | Opens `path` once and fixes the **extent** `[0, end)`. `end` defaults to the size from `fstat` at opening. Iterating it (once only) yields `RawLine` objects, last line first. Attributes: `extent`, `stat` (the `fstat` at opening), `bytes_read`, `read_calls`, and `observed_changes()`. Use it as a context manager to close the file. |
| `RawLine(start, content, terminator)` | One line, unchanged. `start` is its byte offset. `content` is its bytes without the terminator. `terminator` is `b'\r\n'`, `b'\r'`, `b'\n'`, or `b''` for an unterminated last line. `end` is the offset after the terminator. |
| `RawLine.text()` | `content` decoded as UTF-8 with `errors='replace'`, plus `'\n'` if the line has any terminator. |
| `RawLine.utf8_valid()` | Whether `content` is valid UTF-8, that is, whether `text()` replaced anything. |
| `reverse_text_lines(path, **options)` | A generator of `text()` strings that closes the file when it finishes or is closed. |
| `reverse_json_records(lines, *, malformed)` | Parses each line's `text()` with `json.loads`. The policy is required. |
| `ExtentChangedError(OSError)`, `LineTooLongError(ValueError)`, `MalformedJsonLineError(ValueError)` | Explicit failures; see below. |

Arguments are checked:
- `chunk_size` must be a positive `int`.
- `end` must be an `int` from 0 to the file size.
- `max_line_bytes` must be `None` or an `int` ≥ 0.
- Only regular files are accepted. A directory or FIFO raises `ValueError`; a FIFO is opened non-blocking so
  that the check cannot hang.

## The equivalence claim

Take a regular file whose bytes `[0, end)` do not change while it is read, and let `P` be a file holding
exactly those bytes. Then the following two expressions are equal:

```python
[line.text() for line in ReverseLineReader(path, end=end)]
list(reversed(list(open(P, encoding='utf-8', errors='replace', newline=None))))
```

Also, `b''.join(l.content + l.terminator for l in reversed(lines))` is exactly the extent's bytes, and the
offsets are contiguous.

**Why this holds.**
- **Line boundaries.** In text mode with `newline=None`, `\r\n` and a lone `\r` become `\n`, and lines end
  after each `\n`. In UTF-8 the bytes `0x0D` and `0x0A` occur only as those characters: lead bytes are ≥ 0xC2
  and continuation bytes are 0x80–0xBF. So splitting the raw bytes at CRLF, CR or LF, with CRLF taken as one
  line end, gives the same boundaries. Reading backwards, an LF is half of a CRLF exactly when the byte before
  it is CR, and that rule needs no context further back.
- **Decoding.** With `errors='replace'`, CPython's UTF-8 decoder replaces each maximal invalid subsequence
  with one U+FFFD. An ASCII byte always ends such a subsequence. So decoding each line on its own gives the
  same characters as decoding the whole stream.

**Line ends.**
- Only CR, LF and CRLF end a line. U+2028, U+2029, VT, FF, FS, GS, RS and U+0085 do not.
- No empty line is invented after a final line end.
- An initial empty line is kept.
- A UTF-8 BOM stays in the text as U+FEFF, because the encoding is `utf-8`, not `utf-8-sig`.

**How it was tested.** These are tests on CPython 3.9.25 and 3.13.16 on Linux, not a proof for every input,
Python implementation or platform:
- every byte string of up to 4 bytes over `CR`, `LF`, `a`, `E2`, `82` and `AC`, at chunk sizes 1 to 5, so that
  every CRLF and every UTF-8 sequence falls across every possible chunk split;
- 2,000 random documents (seed 20261103) mixing line ends, valid and invalid UTF-8, BOMs, NUL and
  non-delimiting separators;
- every prefix extent of an 80-token document;
- 20 named cases whose expected values are written out;
- SHA-256 equality over all 332,768 lines of a 34 MB synthetic file.

## Line ends: preserved and normalized

Both are available:
- `RawLine.terminator` keeps the raw bytes.
- `RawLine.text()` normalizes to `'\n'`, exactly as text mode does.

`terminator == b''` happens only for the last line of the extent, and means the extent ends inside a line.
For an append-only file this may be a write still in progress. The reader reports it; the caller decides
what it means.

## Reading, time and memory

- **Reads.** The file is opened unbuffered and read with explicit `seek` and `read` calls, in chunks from the
  end. Short reads are completed by reading again. Each byte of the extent is read at most once; a full pass
  reads exactly `extent` bytes.
- **Laziness.** A line is yielded as soon as its start is known. That needs the line end before it: 1 byte,
  or 2 for a CRLF. Once the line starting at offset `a` has been yielded,
  `bytes_read ≤ (extent − a) + chunk_size + 1`, which is tested at chunk sizes 1, 16 and 4096. Stopping
  iteration stops reading.
- **Time.** A full pass is linear in the extent. Each chunk is searched once for CR and once for LF, and each
  line's pieces are joined once. Measured on this host (CPython 3.9.25 and 3.13.16): 3.8–9.5 s for 8 MiB of
  nothing but line ends, about 1 µs per line. That is pure-Python per-line overhead; forward text mode is
  faster per line.
- **Memory.** Memory is O(`chunk_size` + the current line), **not constant**.
  - A line is held whole: its pieces, then the joined bytes, and the decoded `str` if `text()` is called.
  - Measured on this host: a 16 MiB line peaked at 33.7 MB of Python allocations.
  - `max_line_bytes` bounds this: it raises `LineTooLongError` as soon as the content seen exceeds the limit,
    before reading the rest of the line. With a 1 MiB limit and 64 KiB chunks this happened after
    1,114,112 bytes had been read.
  - There is no truncating mode that would return part of a line.

## Failures are explicit

- **I/O errors.** An `OSError` from the operating system propagates unchanged.
- **Truncation.** If a read reaches the end of the file before the extent is exhausted, `ExtentChangedError`
  is raised.
- **No silent partial results.** Iteration never ends normally after a failure. Lines already yielded were
  read correctly, but a scan that raised is incomplete, and the caller must treat it so.
- **Line limit.** `LineTooLongError` returns nothing of the offending line.

## Extent and concurrent changes (limits)

There is **no atomic snapshot**. The extent is fixed at opening, but its bytes are read over time.

| Change during or after opening | Effect |
|---|---|
| Appends after `end` (append-only writers) | Not seen. The result is that of the extent. `observed_changes()` reports growth. A record being written when the reader opened can appear as an unterminated last line. |
| Truncation below a part not yet read | `ExtentChangedError` on that read. |
| Truncation of only the part already read | Not seen by reading. The lines come from the bytes as read, which may no longer exist. `observed_changes()` reports the shorter size. |
| Truncate and then rewrite or re-grow | Not detectable by reading; `observed_changes()` may report a changed size or mtime. |
| In-place rewrite inside the extent | Not detected. A line can mix old and new bytes; a test shows `'AAAa'` from `aaaa` rewritten as `AAAA`. |
| The path replaced (rename over it) | The open file descriptor keeps reading the original file. `observed_changes()` reports that the path names a different file. Tested on Linux only. |

`observed_changes()` is a heuristic based on `fstat` and `stat`. It cannot see a rewrite that keeps size and
mtime, a change undone between two looks, or changes within mtime granularity. Consistent snapshots need
something outside this module, such as a filesystem snapshot, or a copy taken under the writer's own lock.

## JSON records: an explicit parse policy

`reverse_json_records(lines, malformed=...)` has no default policy:
- `malformed='raise'` stops at the first line that is not one JSON value, with `MalformedJsonLineError`
  (`.line`, `.error`).
- `malformed='report'` yields `JsonRecord(line, error=...)` and continues.

There is no skip policy. Callers that want to skip filter the `report` stream themselves.

What counts as malformed:
- Blank lines, and an unterminated, partly written last line, are malformed like any other bad line.
- Invalid UTF-8 has already become U+FFFD before parsing; `RawLine.utf8_valid()` shows which lines it affected.

`json.loads` semantics apply: `NaN` and `Infinity` are accepted, and the last of duplicate keys wins. The byte
iterator itself never parses JSON.

## Not established

- Correctness on PyPy or other implementations, and on Python versions other than 3.9.25 and 3.13.16.
- Behaviour on macOS or Windows (not run here), on network or FUSE filesystems, or with non-POSIX rename
  semantics.
- Whether the data is semantically correct, and whether any concurrent use is safe.
