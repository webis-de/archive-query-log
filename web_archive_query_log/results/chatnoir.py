from dataclasses import dataclass
from typing import Pattern, Iterator

from bs4 import Tag

from web_archive_query_log.model import ArchivedSerpResult
from web_archive_query_log.results.parse import HtmlResultsParser, \
    HtmlInterpretedQueryParser
from web_archive_query_log.util.html import clean_html


@dataclass(frozen=True)
class ChatNoirResultsParser(HtmlResultsParser):
    url_pattern: Pattern[str]

    def parse_html(self, html: Tag) -> Iterator[ArchivedSerpResult]:
        results = html.find("section", id="SearchResults")
        if results is None:
            return
        for result in results.find_all("article", class_="search-result"):
            header: Tag = result.find("header")
            url = header.find("a", class_="link")["href"]
            title = clean_html(header.find("h2"), "em")
            # Remove header. Only the snippet will be left.
            header.decompose()
            snippet = clean_html(result, "em")
            yield ArchivedSerpResult(url, title, snippet)


@dataclass(frozen=True)
class ChatNoirInterpretedQueryParser(HtmlInterpretedQueryParser):
    url_pattern: Pattern[str]

    def parse_html(self, html: Tag) -> str | None:
        search_field = html.find("input", id="SearchInput")
        if search_field is None:
            return None
        return search_field.attrs["value"]
