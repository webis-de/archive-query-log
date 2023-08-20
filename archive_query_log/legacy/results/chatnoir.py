from dataclasses import dataclass
from typing import Pattern, Iterator
from urllib.parse import urljoin

from bs4 import Tag

from archive_query_log.legacy.model import ArchivedSearchResultSnippet, \
    HighlightedText
from archive_query_log.legacy.results.parse import HtmlResultsParser
from archive_query_log.legacy.util.html import clean_html


@dataclass(frozen=True)
class ChatNoirResultsParser(HtmlResultsParser):
    url_pattern: Pattern[str]

    def parse_html(
            self,
            html: Tag,
            timestamp: int,
            serp_url: str,
    ) -> Iterator[ArchivedSearchResultSnippet]:
        results = html.find("section", id="SearchResults")
        if results is None or not isinstance(results, Tag):
            return
        results_iter = results.find_all("article", class_="search-result")
        for index, result in enumerate(results_iter):
            header = result.find("header")
            url: str = header.find("a", class_="link")["href"]
            url = urljoin(serp_url, url)
            title = HighlightedText(clean_html(header.find("h2")))
            # Remove header. Only the snippet will be left.
            header.decompose()
            snippet = HighlightedText(clean_html(result))
            yield ArchivedSearchResultSnippet(
                rank=index + 1,
                url=url,
                timestamp=timestamp,
                title=title,
                snippet=snippet if len(snippet) > 0 else None,
            )
