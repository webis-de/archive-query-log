from abc import abstractmethod, ABC
from dataclasses import dataclass
from gzip import GzipFile
from pathlib import Path
from typing import Sequence, NamedTuple, Iterator, Pattern, Iterable
from urllib.parse import quote, urljoin

from bs4 import Tag, BeautifulSoup
from tqdm.auto import tqdm

from archive_query_log.legacy.download.iterable import ArchivedRawSerps
from archive_query_log.legacy.model import ArchivedRawSerp, \
    ArchivedSearchResultSnippet, ResultsParser, InterpretedQueryParser, \
    ArchivedParsedSerp, Service, HighlightedText
from archive_query_log.legacy.util.html import clean_html
from archive_query_log.legacy.util.text import text_io_wrapper


class HtmlResultsParser(ResultsParser, ABC):
    url_pattern: Pattern[str]

    @abstractmethod
    def parse_html(
            self,
            html: Tag,
            timestamp: int,
            serp_url: str,
    ) -> Iterator[ArchivedSearchResultSnippet]:
        ...

    def parse(
            self,
            raw_serp: ArchivedRawSerp,
    ) -> Sequence[ArchivedSearchResultSnippet] | None:
        if self.url_pattern.search(raw_serp.url) is None:
            return None
        html = BeautifulSoup(
            raw_serp.content,
            "html.parser",
            from_encoding=raw_serp.encoding
        )
        results = tuple(self.parse_html(
            html,
            raw_serp.timestamp,
            raw_serp.url,
        ))
        return results if len(results) > 0 else None


@dataclass(frozen=True)
class HtmlSelectorResultsParser(HtmlResultsParser):
    url_pattern: Pattern[str]
    results_selector: str
    url_selector: str
    url_attribute: str
    title_selector: str
    snippet_selector: str | None

    def parse_html(
            self,
            html: Tag,
            timestamp: int,
            serp_url: str,
    ) -> Iterator[ArchivedSearchResultSnippet]:
        for index, result in enumerate(html.select(self.results_selector)):
            url_tag: Tag | None
            if self.url_selector == ":--self":
                url_tag = result
            else:
                url_tag = result.select_one(self.url_selector)
            if url_tag is None:
                continue
            if self.url_attribute not in url_tag.attrs:
                continue
            url = url_tag.attrs[self.url_attribute]
            if url is None:
                continue
            url = urljoin(serp_url, url)

            title_tag: Tag | None
            if self.title_selector == ":--self":
                title_tag = result
            else:
                title_tag = result.select_one(self.title_selector)
            if title_tag is None:
                continue
            title = HighlightedText(clean_html(title_tag))
            if len(title) == 0:
                continue

            snippet = None
            if self.snippet_selector is not None:
                if self.snippet_selector == ":--self":
                    snippet_tags = [result]
                else:
                    snippet_tags = result.select(self.snippet_selector)
                if snippet_tags is not None and snippet_tags:
                    for snippet_candidate_tag in snippet_tags:
                        snippet_candidate = HighlightedText(
                            clean_html(snippet_candidate_tag)
                        )

                        if (len(snippet_candidate) > 0 and
                                (not snippet or
                                 len(snippet_candidate) > len(snippet))):
                            snippet = snippet_candidate

            yield ArchivedSearchResultSnippet(
                rank=index + 1,
                url=url,
                timestamp=timestamp,
                title=title,
                snippet=snippet,
            )


class HtmlInterpretedQueryParser(InterpretedQueryParser, ABC):
    url_pattern: Pattern[str]

    @abstractmethod
    def parse_html(self, html: Tag) -> str | None:
        ...

    def parse(
            self,
            raw_serp: ArchivedRawSerp,
    ) -> str | None:
        if self.url_pattern.search(raw_serp.url) is None:
            return None
        html = BeautifulSoup(
            raw_serp.content,
            "html.parser",
            from_encoding=raw_serp.encoding
        )
        return self.parse_html(html)


@dataclass(frozen=True)
class HtmlSelectorInterpretedQueryParser(HtmlInterpretedQueryParser):
    url_pattern: Pattern[str]
    query_selector: str
    query_attribute: str
    query_text: bool = False

    def parse_html(self, html: Tag) -> str | None:
        search_field = html.select_one(self.query_selector)
        if search_field is None:
            return None
        if self.query_text:
            interpreted_query = search_field.text
            if interpreted_query is not None and len(interpreted_query) > 0:
                return interpreted_query
        if (self.query_attribute is not None and
                self.query_attribute in search_field.attrs):
            interpreted_query = search_field.attrs[self.query_attribute]
            if interpreted_query is not None and len(interpreted_query) > 0:
                return interpreted_query
        return None


class _CdxPage(NamedTuple):
    input_path: Path
    output_path: Path


@dataclass(frozen=True)
class ArchivedParsedSerpParser:
    results_parsers: Sequence[ResultsParser]
    interpreted_query_parsers: Sequence[InterpretedQueryParser]
    overwrite: bool = False
    verbose: bool = False

    def parse(self, input_path: Path, output_path: Path) -> None:
        if output_path.exists() and not self.overwrite:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        archived_serp_contents: Iterable[ArchivedRawSerp] = (
            ArchivedRawSerps(input_path))
        if self.verbose:
            # noinspection PyTypeChecker
            archived_serp_contents = tqdm(
                archived_serp_contents,
                desc="Parse SERP WARC records",
                unit="record",
            )
        archived_parsed_serps_nullable = (
            self.parse_single(archived_serp_content)
            for archived_serp_content in archived_serp_contents
        )
        archived_parsed_serps = (
            archived_serp
            for archived_serp in archived_parsed_serps_nullable
            if archived_serp is not None
        )
        output_schema = ArchivedParsedSerp.schema()
        with output_path.open("wb") as file, \
                GzipFile(fileobj=file, mode="wb") as gzip_file, \
                text_io_wrapper(gzip_file) as text_file:
            for archived_parsed_serp in archived_parsed_serps:
                text_file.write(output_schema.dumps(archived_parsed_serp))
                text_file.write("\n")

    def parse_single(
            self,
            archived_serp_content: ArchivedRawSerp
    ) -> ArchivedParsedSerp | None:
        results: Sequence[ArchivedSearchResultSnippet] | None = None
        for results_parser in self.results_parsers:
            results = results_parser.parse(archived_serp_content)
            if results is not None:
                break

        interpreted_query: str | None = None
        for interpreted_query_parser in self.interpreted_query_parsers:
            interpreted_query = interpreted_query_parser.parse(
                archived_serp_content)
            if interpreted_query is not None:
                break

        if results is None and interpreted_query is None:
            return None

        return ArchivedParsedSerp(
            url=archived_serp_content.url,
            timestamp=archived_serp_content.timestamp,
            query=archived_serp_content.query,
            page=archived_serp_content.page,
            offset=archived_serp_content.offset,
            interpreted_query=interpreted_query,
            results=results if results is not None else [],
        )

    def _service_pages(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None,
            cdx_page: int | None,
    ) -> Sequence[_CdxPage]:
        """
        List all items that need to be downloaded.
        """
        input_format_path = data_directory / "archived-raw-serps"
        output_format_path = data_directory / "archived-parsed-serps"

        service_path = input_format_path / service.name
        if not service_path.exists():
            return []

        if domain is not None:
            domain_paths = [service_path / domain]
        else:
            domain_paths = [
                path
                for path in service_path.iterdir()
                if path.is_dir()
            ]
            if focused:
                domain_paths = [
                    path
                    for path in domain_paths
                    if any(
                        path.name.endswith(quote(prefix, safe=""))
                        for prefix in service.focused_url_prefixes
                    )
                ]

        if cdx_page is not None:
            if domain is None:
                raise RuntimeError(
                    "Domain must be specified when page is specified.")
            if len(domain_paths) < 1:
                raise RuntimeError(
                    "There must be exactly one domain path.")
            cdx_page_paths = [domain_paths[0] / f"{cdx_page:010}"]
        else:
            cdx_page_paths = [
                path
                for domain_path in domain_paths
                for path in domain_path.iterdir()
                if (
                        path.is_dir() and
                        len(path.name) == 10 and
                        path.name.isdigit()
                )
            ]

        return [
            _CdxPage(
                input_path=cdx_page_path,
                output_path=output_format_path / cdx_page_path.relative_to(
                    input_format_path
                ).with_suffix(".jsonl.gz"),
            )
            for cdx_page_path in cdx_page_paths
        ]

    def parse_service(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None = None,
            cdx_page: int | None = None,
    ):
        pages_list: Sequence[_CdxPage] = self._service_pages(
            data_directory=data_directory,
            focused=focused,
            service=service,
            domain=domain,
            cdx_page=cdx_page,
        )

        if len(pages_list) == 0:
            return

        pages: Iterable[_CdxPage] = pages_list
        if len(pages_list) > 1:
            # noinspection PyTypeChecker
            pages = tqdm(
                pages,
                desc="Parse archived SERP URLs",
                unit="page",
            )

        for page in pages:
            self.parse(page.input_path, page.output_path)
