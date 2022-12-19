from abc import abstractmethod, ABC
from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sequence, NamedTuple, Iterator, Pattern
from urllib.parse import quote

from bs4 import Tag, BeautifulSoup
from tqdm.auto import tqdm

from web_archive_query_log.download.iterable import ArchivedRawSerps
from web_archive_query_log.model import ArchivedRawSerp, ArchivedSerpResult, \
    ResultsParser, InterpretedQueryParser, ArchivedParsedSerp, Service


class HtmlResultsParser(ResultsParser, ABC):
    url_pattern: Pattern[str] = ...

    @abstractmethod
    def parse_html(self, html: Tag) -> Iterator[ArchivedSerpResult]:
        ...

    def parse(
            self,
            raw_serp: ArchivedRawSerp,
    ) -> Sequence[ArchivedSerpResult] | None:
        if self.url_pattern.search(raw_serp.url) is None:
            return None
        html = BeautifulSoup(
            raw_serp.content,
            "html.parser",
            from_encoding=raw_serp.encoding
        )
        results = tuple(self.parse_html(html))
        return results if len(results) > 0 else None


class HtmlInterpretedQueryParser(InterpretedQueryParser, ABC):
    url_pattern: Pattern[str] = ...

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
        archived_serp_contents = ArchivedRawSerps(input_path)
        if self.verbose:
            archived_serp_contents = tqdm(
                archived_serp_contents,
                desc="Parse SERP WARC records",
                unit="record",
            )
        archived_parsed_serps = (
            self._parse_single(archived_serp_content)
            for archived_serp_content in archived_serp_contents
        )
        archived_parsed_serps = (
            archived_serp
            for archived_serp in archived_parsed_serps
            if archived_serp is not None
        )
        output_schema = ArchivedParsedSerp.schema()
        # noinspection PyTypeChecker
        with output_path.open("wb") as file, \
                GzipFile(fileobj=file, mode="wb") as gzip_file, \
                TextIOWrapper(gzip_file) as text_file:
            for archived_parsed_serp in archived_parsed_serps:
                text_file.write(output_schema.dumps(archived_parsed_serp))
                text_file.write("\n")

    def _parse_single(
            self,
            archived_serp_content: ArchivedRawSerp
    ) -> ArchivedParsedSerp | None:
        results: Sequence[ArchivedSerpResult] | None = None
        for parser in self.results_parsers:
            results = parser.parse(archived_serp_content)
            if results is not None:
                break

        if results is None:
            return None

        interpreted_query: str | None = None
        for parser in self.interpreted_query_parsers:
            interpreted_query = parser.parse(archived_serp_content)
            if interpreted_query is not None:
                break

        return ArchivedParsedSerp(
            url=archived_serp_content.url,
            timestamp=archived_serp_content.timestamp,
            query=archived_serp_content.query,
            page=archived_serp_content.page,
            offset=archived_serp_content.offset,
            interpreted_query=interpreted_query,
            results=results,
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
            assert domain is not None
            assert len(domain_paths) == 1
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
        pages = self._service_pages(
            data_directory=data_directory,
            focused=focused,
            service=service,
            domain=domain,
            cdx_page=cdx_page,
        )

        if len(pages) == 0:
            return

        if len(pages) > 1:
            pages = tqdm(
                pages,
                desc="Parse archived SERP URLs",
                unit="page",
            )

        for page in pages:
            self.parse(page.input_path, page.output_path)
