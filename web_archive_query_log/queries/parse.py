from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, Optional
from urllib.parse import parse_qsl, unquote

from web_archive_query_log.model import ArchivedSerpUrl, \
    ArchivedUrl


class QueryParser(ABC):

    def parse(self, url: ArchivedUrl) -> ArchivedSerpUrl | None:
        query = self._parse_query(url)
        if query is None:
            return None
        return ArchivedSerpUrl(
            url=url.url,
            timestamp=url.timestamp,
            query=query,
        )

    @abstractmethod
    def _parse_query(self, url: ArchivedUrl) -> str | None:
        ...


@final
@dataclass(frozen=True)
class QueryParameter(QueryParser):
    key: str

    def _parse_query(self, url: ArchivedUrl) -> str | None:
        # We cannot use map access syntax here, as ``parse_qsl``
        # returns a list of tuples.
        for key, value in parse_qsl(url.split_url.query):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class FragmentParameter(QueryParser):
    key: str

    def _parse_query(self, url: ArchivedUrl) -> Optional[str]:
        # We cannot use map access syntax here, as ``parse_qsl``
        # returns a list of tuples.
        for key, value in parse_qsl(url.split_url.fragment):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class PathSuffix(QueryParser):
    prefix: str
    single_segment: bool = False

    def _parse_query(self, url: ArchivedUrl) -> Optional[str]:
        path = url.split_url.path
        if not path.startswith(self.prefix):
            return None
        path = path.removeprefix(self.prefix)
        if self.single_segment and "/" in path:
            path, _ = path.split("/", maxsplit=1)
        return unquote(path)


