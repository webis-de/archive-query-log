from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, Optional, Sequence, Iterator
from urllib.parse import parse_qsl, unquote

from bleach import clean
from bs4 import BeautifulSoup, Tag

from web_archive_query_log.model import SearchResult, ArchivedSerpUrl, \
    ArchivedUrl, ArchivedSerpContent, ArchivedSerp


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


class BingSearchResultsParser(SearchResultsParser):

    @staticmethod
    def _clean_html(tag: Tag) -> str:
        return clean(
            tag.decode_contents(),
            tags=["strong"],
            attributes=[],
            protocols=[],
            strip=True,
            strip_comments=True,
        ).strip()

    def _parse_serp_iter(
            self,
            content: bytes,
            encoding: str,
    ) -> Iterator[SearchResult]:
        soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
        results: Tag = soup.find("ol", id="b_results")
        if results is None:
            return
        result: Tag
        for result in results.find_all("li", class_="b_algo"):
            title: Tag = result.find("h2")
            caption: Tag | None = result.find("p")
            yield SearchResult(
                url=title.find("a").attrs["href"],
                title=self._clean_html(title),
                snippet=(
                    self._clean_html(caption)
                    if caption is not None else ""
                )
            )

    def _parse_results(
            self,
            content: ArchivedSerpContent,
    ) -> Sequence[SearchResult] | None:
        domain_parts = content.split_url.netloc.split(".")
        if "bing" not in domain_parts:
            # bing.*/*
            return None
        return list(self._parse_serp_iter(content.content, content.encoding))
