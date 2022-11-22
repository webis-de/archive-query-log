from pathlib import Path
from typing import Iterable

from web_archive_query_log.model import ArchivedUrl


def read_urls(path: Path) -> Iterable[ArchivedUrl]:
    schema = ArchivedUrl.schema()
    with path.open("rt") as file:
        return [
            schema.loads(line)
            for line in file
        ]
