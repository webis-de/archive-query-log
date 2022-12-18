from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sequence, Iterator, Pattern

from bleach import clean
from bs4 import Tag, BeautifulSoup
from tqdm.auto import tqdm

from web_archive_query_log.download.iterable import ArchivedRawSerps
from web_archive_query_log.model import ArchivedRawSerp, ArchivedSerpResult, \
    ResultsParser, InterpretedQueryParser, ArchivedParsedSerp


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
