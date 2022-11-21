from abc import ABC, abstractmethod
from typing import Sequence

from web_archive_query_log.model import ArchivedSerpContent, ArchivedSerp, \
    SearchResult


class SearchResultsParser(ABC):
    def parse(self, content: ArchivedSerpContent) -> ArchivedSerp | None:
        results = self._parse_results(content)
        if results is None:
            return None
        return ArchivedSerp(
            url=content.url,
            timestamp=content.timestamp,
            query=content.query,
            results=results,
        )

    @abstractmethod
    def _parse_results(
            self,
            content: ArchivedSerpContent,
    ) -> Sequence[SearchResult] | None:
        ...


