from dataclasses import dataclass
from typing import Pattern, Iterator

from bs4 import Tag

from web_archive_query_log.model import ArchivedSerpResult
from web_archive_query_log.results.parse import HtmlResultsParser
from web_archive_query_log.util.html import clean_html


@dataclass(frozen=True)
class BingResultsParser(HtmlResultsParser):
    url_pattern: Pattern[str]

    def parse_html(self, html: Tag) -> Iterator[ArchivedSerpResult]:
        results = html.find("ol", id="b_results")
        if results is None:
            return
        for result in results.find_all("li", class_="b_algo"):
            title = result.find("h2")
            caption = result.find("p")
            yield ArchivedSerpResult(
                url=title.find("a").attrs["href"],
                title=clean_html(title),
                snippet=clean_html(caption) if caption is not None else ""
            )
