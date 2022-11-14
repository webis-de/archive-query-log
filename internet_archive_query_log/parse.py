from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, Optional, Sequence, Iterator
from urllib.parse import SplitResult, parse_qsl, unquote, urlsplit

from bleach import clean
from bs4 import BeautifulSoup, Tag

from internet_archive_query_log.model import SearchResult, ArchivedSerpUrl


class QueryParser(ABC):
    @abstractmethod
    def parse_query(self, url: SplitResult) -> Optional[str]:
        ...


@final
@dataclass(frozen=True)
class QueryParameter(QueryParser):
    key: str

    def parse_query(self, url: SplitResult) -> Optional[str]:
        for key, value in parse_qsl(url.query):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class FragmentParameter(QueryParser):
    key: str

    def parse_query(self, url: SplitResult) -> Optional[str]:
        for key, value in parse_qsl(url.fragment):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class PathSuffix(QueryParser):
    prefix: str
    single_segment: bool = False

    def parse_query(self, url: SplitResult) -> Optional[str]:
        if not url.path.startswith(self.prefix):
            return None
        path = url.path.removeprefix(self.prefix)
        if self.single_segment and "/" in path:
            path, _ = path.split("/", maxsplit=1)
        return unquote(path)


class SerpParser(ABC):
    @abstractmethod
    def parse_serp(
            self,
            content: bytes,
            encoding: str | None
    ) -> Sequence[SearchResult]:
        ...

    def can_parse(self, query: ArchivedSerpUrl) -> bool:
        return True


class BingSerpParser(SerpParser):

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
            encoding: str | None
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

    def parse_serp(
            self,
            content: bytes,
            encoding: str | None
    ) -> Sequence[SearchResult]:
        return list(self._parse_serp_iter(content, encoding))

    def can_parse(self, query: ArchivedSerpUrl) -> bool:
        # bing.*/*
        domain_parts = urlsplit(query.url).netloc.split(".")
        return "bing" in domain_parts

