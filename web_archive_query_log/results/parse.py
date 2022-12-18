from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sequence, Iterator, Pattern, NamedTuple
from urllib.parse import quote

from bleach import clean
from bs4 import Tag, BeautifulSoup
from tqdm.auto import tqdm

from web_archive_query_log.download.iterable import ArchivedRawSerps
from web_archive_query_log.model import ArchivedRawSerp, ArchivedSerpResult, \
    ResultsParser, InterpretedQueryParser, ArchivedParsedSerp, Service


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

class _CdxPage(NamedTuple):
    input_path: Path
    output_path: Path

@dataclass(frozen=True)
class ArchivedParsedSerpParser:
    results_parsers: Sequence[ResultsParser]
    result_query_parsers: Sequence[InterpretedQueryParser]
    verbose: bool = False

    def parse(self, input_path: Path, output_path: Path) -> None:
        archived_serp_contents = ArchivedRawSerps(input_path)
        if self.verbose:
            archived_serp_contents = tqdm(
                archived_serp_contents,
                desc="Parse SERP WARC records",
                unit="record",
            )
        archived_serps = (
            self._parse_single(archived_serp_content)
            for archived_serp_content in archived_serp_contents
        )
        archived_serps = (
            archived_serp
            for archived_serp in archived_serps
            if archived_serp is not None
        )
        output_schema = ArchivedParsedSerp.schema()
        # noinspection PyTypeChecker
        with output_path.open("wb") as file, \
                GzipFile(fileobj=file, mode="wb") as gzip_file, \
                TextIOWrapper(gzip_file) as text_file:
            for archived_serp_url in archived_serps:
                text_file.write(output_schema.dumps(archived_serp_url))
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
        for parser in self.result_query_parsers:
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
        output_format_path = data_directory / "archived-pasred-serps"

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
