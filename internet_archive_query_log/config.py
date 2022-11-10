from dataclasses import dataclass
from typing import Iterable

from internet_archive_query_log.parse import QueryParser


@dataclass(frozen=True)
class QuerySource:
    url_prefix: str
    parser: QueryParser


@dataclass(frozen=True)
class Config:
    query_sources: Iterable[QuerySource]
