from dataclasses import dataclass
from typing import Iterable

from internet_archive_query_log.parse import QueryParser, SerpParser


@dataclass(frozen=True)
class Source:
    url_prefix: str
    query_parser: QueryParser
    serp_parsers: Iterable[SerpParser]

