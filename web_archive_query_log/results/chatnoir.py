from dataclasses import dataclass
from typing import Pattern, Iterator

from bs4 import Tag

from web_archive_query_log.model import ArchivedSearchResultSnippet, \
    HighlightedText
from web_archive_query_log.results.parse import HtmlResultsParser
from web_archive_query_log.util.html import clean_html


@dataclass(frozen=True)
class ChatNoirResultsParser(HtmlResultsParser):
    url_pattern: Pattern[str]

    def parse_html(
            self,
            html: Tag,
            timestamp: int,
    ) -> Iterator[ArchivedSearchResultSnippet]:
        results = html.find("section", id="SearchResults")
        if results is None:
            return
        results_iter = results.find_all("article", class_="search-result")
        for index, result in enumerate(results_iter):
            header: Tag = result.find("header")
            url = header.find("a", class_="link")["href"]
            title = clean_html(header.find("h2"))
            # Remove header. Only the snippet will be left.
            header.decompose()
            snippet = clean_html(result)
            if len(snippet) == 0:
                snippet = None
            yield ArchivedSearchResultSnippet(
                rank=index + 1,
                url=url,
                timestamp=timestamp,
                title=HighlightedText(title),
                snippet=HighlightedText(snippet),
            )
