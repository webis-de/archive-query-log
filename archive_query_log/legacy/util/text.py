from io import IOBase, TextIOWrapper
from typing import IO, Iterator

_LINE_COUNT_BUFFER_SIZE = 1024 * 1024


def _chunks(reader: IO[bytes] | IOBase) -> Iterator[bytes]:
    buffer = reader.read(_LINE_COUNT_BUFFER_SIZE)
    while buffer:
        yield buffer
        buffer = reader.read(_LINE_COUNT_BUFFER_SIZE)


def count_lines(file: IO[bytes] | IOBase) -> int:
    return sum(buffer.count(b"\n") for buffer in _chunks(file))


def text_io_wrapper(file: IO[bytes] | IOBase) -> IO[str]:
    return TextIOWrapper(file)  # type: ignore
