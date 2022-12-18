from dataclasses import dataclass
from typing import Pattern, Iterator, Sequence

from bleach import clean
from bs4 import Tag, BeautifulSoup

from web_archive_query_log.model import ResultsParser, ArchivedSerpResult, \
    ArchivedRawSerp


@dataclass(frozen=True)
class BingResultsParser(ResultsParser):
    url_pattern: Pattern[str]

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
    ) -> Iterator[ArchivedSerpResult]:
        soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
        results: Tag = soup.find("ol", id="b_results")
        if results is None:
            return
        result: Tag
        for result in results.find_all("li", class_="b_algo"):
            title: Tag = result.find("h2")
            caption: Tag | None = result.find("p")
            yield ArchivedSerpResult(
                url=title.find("a").attrs["href"],
                title=self._clean_html(title),
                snippet=(
                    self._clean_html(caption)
                    if caption is not None else ""
                )
            )

    def _parse_results(
            self,
            content: ArchivedRawSerp,
    ) -> Sequence[ArchivedSerpResult] | None:
        if self.url_pattern.search(content.url) is None:
            return None
        domain_parts = content.split_url.netloc.split(".")
        if "bing" not in domain_parts:
            # bing.*/*
            return None
        return list(self._parse_serp_iter(content.content, content.encoding))
