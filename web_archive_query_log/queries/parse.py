from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qsl, unquote

from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedSerpUrl, \
    ArchivedUrl, PageParser, QueryParser, OffsetParser
from web_archive_query_log.urls.iterable import ArchivedUrls


@dataclass(frozen=True)
class QueryParameterQueryParser(QueryParser):
    parameter: str

    def parse(self, url: ArchivedUrl) -> str | None:
        for key, value in parse_qsl(url.split_url.query):
            if key == self.parameter:
                return value
        return None


@dataclass(frozen=True)
class FragmentParameterQueryParser(QueryParser):
    parameter: str

    def parse(self, url: ArchivedUrl) -> str | None:
        for key, value in parse_qsl(url.split_url.fragment):
            if key == self.parameter:
                return value
        return None


@dataclass(frozen=True)
class PathSuffixQueryParser(QueryParser):
    path_prefix: str
    single_segment: bool = False

    def parse(self, url: ArchivedUrl) -> str | None:
        path = url.split_url.path
        if not path.startswith(self.path_prefix):
            return None
        path = path.removeprefix(self.path_prefix)
        if self.single_segment and "/" in path:
            path, _ = path.split("/", maxsplit=1)
        return unquote(path)


@dataclass(frozen=True)
class QueryParameterPageOffsetParser(PageParser, OffsetParser):
    parameter: str

    def parse(self, url: ArchivedUrl) -> int | None:
        for key, value in parse_qsl(url.split_url.query):
            if key == self.parameter and value.isdigit():
                return int(value)
        return None


@dataclass(frozen=True)
class FragmentParameterPageOffsetParser(PageParser, OffsetParser):
    parameter: str

    def parse(self, url: ArchivedUrl) -> int | None:
        for key, value in parse_qsl(url.split_url.fragment):
            if key == self.parameter and value.isdigit():
                return int(value)
        return None


@dataclass(frozen=True)
class ArchivedSerpUrlsParser:
    query_parsers: Sequence[QueryParser]
    page_parsers: Sequence[PageParser]
    offset_parsers: Sequence[OffsetParser]
    verbose: bool = False

    def parse(self, input_path: Path, output_path: Path) -> None:
        archived_urls = ArchivedUrls(input_path)
        if self.verbose:
            archived_urls = tqdm(
                archived_urls,
                desc="Parse SERP URLs",
                unit="URL",
            )
        archived_serp_urls = (
            self._parse_single(archived_url)
            for archived_url in archived_urls
        )
        archived_serp_urls = (
            archived_serp_url
            for archived_serp_url in archived_serp_urls
            if archived_serp_url is not None
        )
        output_schema = ArchivedSerpUrl.schema()
        if output_path.suffix == ".gz":
            # noinspection PyTypeChecker
            with output_path.open("wb") as file, \
                    GzipFile(fileobj=file, mode="wb") as gzip_file, \
                    TextIOWrapper(gzip_file) as text_file:
                for archived_serp_url in archived_serp_urls:
                    text_file.write(output_schema.dumps(archived_serp_url))
                    text_file.write("\n")
        else:
            with output_path.open("wt") as file:
                for archived_serp_url in archived_serp_urls:
                    file.write(output_schema.dumps(archived_serp_url))
                    file.write("\n")

    def _parse_single(
            self,
            archived_url: ArchivedUrl
    ) -> ArchivedSerpUrl | None:
        query: str | None = None
        for parser in self.query_parsers:
            query = parser.parse(archived_url)
            if query is not None:
                break

        if query is None:
            return None

        page: int | None = None
        for parser in self.page_parsers:
            page = parser.parse(archived_url)
            if page is not None:
                break

        offset: int | None = None
        for parser in self.offset_parsers:
            offset = parser.parse(archived_url)
            if offset is not None:
                break

        return ArchivedSerpUrl(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            query=query,
            page=page,
            offset=offset,
        )
