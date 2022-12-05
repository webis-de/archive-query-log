from typing import Sequence, Protocol, runtime_checkable

from web_archive_query_log.model import ArchivedUrl, SearchResult, \
    ArchivedSerpContent


@runtime_checkable
class PageNumberParser(Protocol):
    def parse_page_number(self, url: ArchivedUrl) -> int | None:
        ...


@runtime_checkable
class QueryParser(Protocol):
    def parse_query(self, url: ArchivedUrl) -> str | None:
        ...


@runtime_checkable
class SearchResultsParser(Protocol):
    def parse_search_results(
            self,
            content: ArchivedSerpContent,
    ) -> Sequence[SearchResult] | None:
        ...
