from typing import IO, Iterator

_LINE_COUNT_BUFFER_SIZE = 1024 * 1024


def _chunks(reader: IO[bytes]) -> Iterator[bytes]:
    buffer = reader.read(_LINE_COUNT_BUFFER_SIZE)
    while buffer:
        yield buffer
        buffer = reader.read(_LINE_COUNT_BUFFER_SIZE)


def count_lines(file: IO[bytes]) -> int:
    return sum(buffer.count(b"\n") for buffer in _chunks(file))
