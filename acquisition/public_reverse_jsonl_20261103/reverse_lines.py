"""Read the lines of a UTF-8 text file from the last to the first. Standard library only; Python >= 3.9.

    with ReverseLineReader(path) as reader:
        for line in reader:            # RawLine objects, newest (last) line first
            ...line.text()...          # == the str that open(path, encoding='utf-8', errors='replace',
                                       #    newline=None) yields for that line, '\\n' terminator included

The lines are those of Python's text mode with universal newlines: "\\r\\n", "\\r" and "\\n" end a line, and
nothing else does (not U+2028, U+2029, VT, FF, U+0085, ...). Each line's raw bytes and raw terminator are kept;
RawLine.text() normalizes the terminator to "\\n" and decodes with errors='replace', as text mode does.

Only the extent fixed when the reader is opened, bytes [0, end), is read; each byte at most once, from the end,
and only as far back as the lines consumed so far need. A line is held whole in memory, so memory grows with
the longest line read unless max_line_bytes is set. See CONTRACT.md for the exact guarantees and limits, in
particular what concurrent appends, truncation, rewrites and path replacement do.
"""

from __future__ import annotations

import io
import json
import os
import stat
from typing import Any, Iterator, List, NamedTuple, Optional, Tuple, Union

__all__ = [
    'ExtentChangedError',
    'JsonRecord',
    'LineTooLongError',
    'MalformedJsonLineError',
    'RawLine',
    'ReverseLineReader',
    'reverse_json_records',
    'reverse_text_lines',
]

VERSION = '1.0.0'
DEFAULT_CHUNK_SIZE = 65_536
CR, LF = 0x0D, 0x0A


class ExtentChangedError(OSError):
    """The file no longer holds the bytes of the extent the reader was opened with (for example, truncated)."""


class LineTooLongError(ValueError):
    """A line's content is longer than max_line_bytes; nothing of that line is returned."""


class MalformedJsonLineError(ValueError):
    """reverse_json_records(malformed='raise') met a line that is not one JSON value."""

    def __init__(self, line: RawLine, error: str) -> None:
        super().__init__(f'line at byte {line.start} is not one JSON value: {error}')
        self.line = line
        self.error = error


class RawLine(NamedTuple):
    """One line of the extent: its byte offset, its content bytes and its raw terminator, all unchanged."""

    start: int  # byte offset of the first content byte
    content: bytes  # the line without its terminator
    terminator: bytes  # b'\r\n', b'\r', b'\n', or b'' for an unterminated last line of the extent

    @property
    def end(self) -> int:
        """Byte offset just past the terminator."""
        return self.start + len(self.content) + len(self.terminator)

    def text(self) -> str:
        """The line as text mode reads it: content decoded with errors='replace', any terminator as '\\n'."""
        return _decode(self.content) + ('\n' if self.terminator else '')

    def utf8_valid(self) -> bool:
        """Whether the content is valid UTF-8, that is, whether text() replaced nothing."""
        try:
            self.content.decode('utf-8', 'strict')
        except UnicodeDecodeError:
            return False
        return True


def _decode(content: bytes) -> str:
    # A line's bytes can be decoded on their own: CR and LF are ASCII, so they never fall inside a UTF-8 sequence
    # or inside the invalid run that one U+FFFD replaces, and the decoder's replacements never cross them.
    return content.decode('utf-8', 'replace')


class ReverseLineReader:
    """Iterate the lines of bytes [0, end) of a regular file, last line first, as RawLine objects.

    `end` defaults to the file size when the reader is opened. The file is opened once, unbuffered, and read
    with explicit seeks and reads; `bytes_read` and `read_calls` count them. One iteration per reader.
    """

    def __init__(
        self,
        path: Union[str, os.PathLike[str]],
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        end: Optional[int] = None,
        max_line_bytes: Optional[int] = None,
    ) -> None:
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size < 1:
            raise ValueError('chunk_size must be a positive int')
        if max_line_bytes is not None and (not isinstance(max_line_bytes, int) or max_line_bytes < 0):
            raise ValueError('max_line_bytes must be None or a non-negative int')
        # O_NONBLOCK only so that opening a FIFO cannot block; it is rejected below as not a regular file.
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NONBLOCK', 0))
        try:
            self.stat = os.fstat(fd)
            if not stat.S_ISREG(self.stat.st_mode):
                raise ValueError(f'{path!r} is not a regular file')
            if end is None:
                end = self.stat.st_size
            elif not isinstance(end, int) or isinstance(end, bool) or not 0 <= end <= self.stat.st_size:
                raise ValueError(f'end must be an int from 0 to the file size {self.stat.st_size}')
            self._file: io.FileIO = open(fd, 'rb', buffering=0)  # noqa: SIM115 (closed by close())
        except BaseException:
            os.close(fd)
            raise
        self.path = path
        self.extent = end
        self.chunk_size = chunk_size
        self.max_line_bytes = max_line_bytes
        self.bytes_read = 0
        self.read_calls = 0
        self._started = False

    def __enter__(self) -> ReverseLineReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._file.close()

    def __iter__(self) -> Iterator[RawLine]:
        if self._started:
            raise RuntimeError('a ReverseLineReader can be iterated only once')
        self._started = True
        return self._lines()

    def observed_changes(self) -> List[str]:
        """Changes visible now through fstat of the open file and stat of the path; [] if none.

        A heuristic, not a snapshot check: it cannot see an in-place rewrite that keeps size and mtime, or any
        change made and undone between two looks. See CONTRACT.md.
        """
        now = os.fstat(self._file.fileno())
        changes: List[str] = []
        if now.st_size < self.extent:
            changes.append(f'file is now {now.st_size} bytes, shorter than the extent {self.extent}')
        elif now.st_size > self.stat.st_size:
            changes.append(f'file grew from {self.stat.st_size} to {now.st_size} bytes (bytes past the extent)')
        if now.st_mtime_ns != self.stat.st_mtime_ns:
            changes.append('file modification time changed')
        try:
            current = os.stat(self.path)
        except FileNotFoundError:
            changes.append('the path no longer exists')
        else:
            if (current.st_dev, current.st_ino) != (now.st_dev, now.st_ino):
                changes.append('the path now names a different file')
        return changes

    def _read(self, start: int, stop: int) -> bytes:
        """Exactly bytes [start, stop) of the file, or ExtentChangedError; I/O errors propagate unchanged."""
        self._file.seek(start)
        pieces: List[bytes] = []
        remaining = stop - start
        while remaining:
            piece = self._file.read(remaining)
            self.read_calls += 1
            if not piece:
                raise ExtentChangedError(
                    f'{self.path!r}: expected bytes {start}-{stop} of the {self.extent}-byte extent, but the file '
                    f'ended at byte {stop - remaining}; it was truncated or replaced in place while being read'
                )
            self.bytes_read += len(piece)
            pieces.append(piece)
            remaining -= len(piece)
        return b''.join(pieces)

    def _lines(self) -> Iterator[RawLine]:
        """The lines of the extent, last first. Each byte is read once, and only when a line needs it."""
        chunk_size, limit = self.chunk_size, self.max_line_bytes
        pos = self.extent  # bytes [pos, extent) have been read
        term = b''  # the current line's terminator; b'' until one is found at the very end
        content_end = pos  # where the current line's content ends (its terminator starts)
        parts: List[bytes] = []  # the current line's content read so far, rightmost piece first
        size = 0  # total length of parts
        pending_lf = False  # bytes[pos] is an LF whose preceding byte (a possible CR) has not been read yet

        def take(piece: bytes) -> None:
            nonlocal size
            if piece:
                parts.append(piece)
                size += len(piece)
                if limit is not None and size > limit:
                    raise LineTooLongError(
                        f'the line whose content ends at byte {content_end} has more than {limit} bytes '
                        '(max_line_bytes)'
                    )

        def finish(start: int, next_term: bytes) -> Iterator[RawLine]:
            # The current line starts at `start` and is yielded, if any; the line before it ends with `next_term`.
            nonlocal term, content_end, parts, size
            content = parts[0] if len(parts) == 1 else b''.join(reversed(parts))
            line = RawLine(start, content, term)
            term, content_end, parts, size = next_term, start - len(next_term), [], 0
            if line.content or line.terminator:  # no phantom empty line after a final line end
                yield line

        while pos > 0:
            start = max(0, pos - chunk_size)
            chunk = self._read(start, pos)
            hi = len(chunk)  # chunk[:hi] is still to be scanned
            if pending_lf:
                pending_lf, crlf = False, chunk[-1] == CR
                hi -= 1 if crlf else 0
                yield from finish(pos + 1, b'\r\n' if crlf else b'\n')
            lf, cr = chunk.rfind(b'\n', 0, hi), chunk.rfind(b'\r', 0, hi)
            while True:
                i = lf if lf > cr else cr
                if i < 0:
                    take(chunk[:hi])
                    break
                take(chunk[i + 1 : hi])
                line_end = _line_end_at(chunk, i, start)
                if line_end is None:
                    pending_lf = True  # is it the second half of a CRLF? the next chunk's last byte says
                    break
                hi = line_end[1]
                yield from finish(start + i + 1, line_end[0])
                if lf >= hi:
                    lf = chunk.rfind(b'\n', 0, hi)
                if cr >= hi:
                    cr = chunk.rfind(b'\r', 0, hi)
            pos = start
        yield from finish(0, b'')


def _line_end_at(chunk: bytes, i: int, start: int) -> Optional[Tuple[bytes, int]]:
    """The line end whose last byte is chunk[i] (a CR or LF) and the index where it begins, or None for an LF
    at the start of a chunk that does not start the file: whether a CR precedes it is not known yet."""
    if chunk[i] == CR:
        return b'\r', i  # a CR followed by an LF was already taken as a CRLF from the LF side
    if i > 0:
        return (b'\r\n', i - 1) if chunk[i - 1] == CR else (b'\n', i)
    if start == 0:
        return b'\n', 0  # an LF at offset 0 has no byte before it
    return None


def reverse_text_lines(path: Union[str, os.PathLike[str]], **options: Any) -> Iterator[str]:
    """The str lines of open(path, encoding='utf-8', errors='replace', newline=None), last first.

    The file is closed when the generator finishes or is closed; options are those of ReverseLineReader.
    """
    with ReverseLineReader(path, **options) as reader:
        for line in reader:
            yield line.text()


class JsonRecord(NamedTuple):
    """A line and its parsed JSON value, or, under malformed='report', the parse error instead."""

    line: RawLine
    value: Any = None
    error: Optional[str] = None


def reverse_json_records(lines: Iterator[RawLine], *, malformed: str) -> Iterator[JsonRecord]:
    """Parse each line's text() with json.loads, last line first. The caller must choose a policy:

    - malformed='raise': stop with MalformedJsonLineError at the first line that is not one JSON value;
    - malformed='report': yield it as JsonRecord(line, error=...) and continue.

    Blank lines and an unterminated, partly written last line are malformed like any other. Decoding replaced
    invalid UTF-8 with U+FFFD before parsing; RawLine.utf8_valid() tells which lines that touched.
    """
    if malformed not in ('raise', 'report'):
        raise ValueError("malformed must be 'raise' or 'report'")
    for line in lines:
        try:
            value = json.loads(line.text())
        except json.JSONDecodeError as e:
            if malformed == 'raise':
                raise MalformedJsonLineError(line, str(e)) from None
            yield JsonRecord(line, error=str(e))
        else:
            yield JsonRecord(line, value)
