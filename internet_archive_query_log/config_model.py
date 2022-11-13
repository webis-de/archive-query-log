from dataclasses import dataclass

from internet_archive_query_log.parse import QueryParser


@dataclass(frozen=True)
class QuerySource:
    url_prefix: str
    parser: QueryParser

