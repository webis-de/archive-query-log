from dataclasses import dataclass
from gzip import GzipFile
from pathlib import Path
from typing import Sequence, NamedTuple, Pattern, Iterable
from urllib.parse import parse_qsl, unquote, quote

from tqdm.auto import tqdm

from archive_query_log.legacy.model import ArchivedQueryUrl, \
    ArchivedUrl, PageParser, QueryParser, OffsetParser, Service
from archive_query_log.legacy.urls.iterable import ArchivedUrls
from archive_query_log.legacy.util.text import text_io_wrapper


@dataclass(frozen=True)
class QueryParameterQueryParser(QueryParser):
    url_pattern: Pattern[str]
    parameter: str

    def parse(self, url: ArchivedUrl) -> str | None:
        if self.url_pattern.search(url.url) is None:
            return None
        for key, value in parse_qsl(url.split_url.query):
            if key == self.parameter:
                return value.strip()
        return None


@dataclass(frozen=True)
class FragmentParameterQueryParser(QueryParser):
    url_pattern: Pattern[str]
    parameter: str

    def parse(self, url: ArchivedUrl) -> str | None:
        if self.url_pattern.search(url.url) is None:
            return None
        for key, value in parse_qsl(url.split_url.fragment):
            if key == self.parameter:
                return value.strip()
        return None


@dataclass(frozen=True)
class PathSegmentQueryParser(QueryParser):
    url_pattern: Pattern[str]
    segment: int
    delimiter: str = "/"
    remove_patterns: Sequence[Pattern[str]] = tuple()
    space_patterns: Sequence[Pattern[str]] = tuple()

    def parse(self, url: ArchivedUrl) -> str | None:
        if self.url_pattern.search(url.url) is None:
            return None
        path = url.split_url.path
        path_segments = path.split(self.delimiter)
        if len(path_segments) <= self.segment:
            return None
        path_segment = path_segments[self.segment]
        for pattern in self.remove_patterns:
            path_segment = pattern.sub("", path_segment)
        if len(self.space_patterns) > 0:
            for pattern in self.space_patterns:
                path_segment = pattern.sub(" ", path_segment)
            path_segment = path_segment.replace("  ", " ")
        return unquote(path_segment).strip()


@dataclass(frozen=True)
class FragmentSegmentQueryParser(QueryParser):
    url_pattern: Pattern[str]
    segment: int
    delimiter: str = "/"
    remove_patterns: Sequence[Pattern[str]] = tuple()
    space_patterns: Sequence[Pattern[str]] = tuple()

    def parse(self, url: ArchivedUrl) -> str | None:
        if self.url_pattern.search(url.url) is None:
            return None
        path = url.split_url.fragment
        path_segments = path.split(self.delimiter)
        if len(path_segments) <= self.segment:
            return None
        path_segment = path_segments[self.segment]
        for pattern in self.remove_patterns:
            path_segment = pattern.sub("", path_segment)
        if len(self.space_patterns) > 0:
            for pattern in self.space_patterns:
                path_segment = pattern.sub(" ", path_segment)
            path_segment = path_segment.replace("  ", " ")
        return unquote(path_segment).strip()


@dataclass(frozen=True)
class QueryParameterPageOffsetParser(PageParser, OffsetParser):
    url_pattern: Pattern[str]
    parameter: str

    def parse(self, url: ArchivedUrl) -> int | None:
        if self.url_pattern.search(url.url) is None:
            return None
        for key, value in parse_qsl(url.split_url.query):
            if key == self.parameter and value.isdigit():
                return int(value)
        return None


@dataclass(frozen=True)
class FragmentParameterPageOffsetParser(PageParser, OffsetParser):
    url_pattern: Pattern[str]
    parameter: str

    def parse(self, url: ArchivedUrl) -> int | None:
        if self.url_pattern.search(url.url) is None:
            return None
        for key, value in parse_qsl(url.split_url.fragment):
            if key == self.parameter and value.isdigit():
                return int(value)
        return None


@dataclass(frozen=True)
class PathSegmentPageOffsetParser(PageParser, OffsetParser):
    url_pattern: Pattern[str]
    segment: int
    delimiter: str = "/"
    remove_patterns: Sequence[Pattern[str]] = tuple()

    def parse(self, url: ArchivedUrl) -> int | None:
        if self.url_pattern.search(url.url) is None:
            return None
        path = url.split_url.path
        path_segments = path.split(self.delimiter)
        if len(path_segments) <= self.segment:
            return None
        path_segment = path_segments[self.segment]
        for pattern in self.remove_patterns:
            path_segment = pattern.sub("", path_segment)
        return int(path_segment)


@dataclass(frozen=True)
class FragmentSegmentPageOffsetParser(PageParser, OffsetParser):
    url_pattern: Pattern[str]
    segment: int
    delimiter: str = "/"
    remove_patterns: Sequence[Pattern[str]] = tuple()

    def parse(self, url: ArchivedUrl) -> int | None:
        if self.url_pattern.search(url.url) is None:
            return None
        path = url.split_url.fragment
        path_segments = path.split(self.delimiter)
        if len(path_segments) <= self.segment:
            return None
        path_segment = path_segments[self.segment]
        for pattern in self.remove_patterns:
            path_segment = pattern.sub("", path_segment)
        return int(path_segment)


class _CdxPage(NamedTuple):
    input_path: Path
    output_path: Path


@dataclass(frozen=True)
class ArchivedQueryUrlParser:
    query_parsers: Sequence[QueryParser]
    page_parsers: Sequence[PageParser]
    offset_parsers: Sequence[OffsetParser]
    overwrite: bool = False
    verbose: bool = False

    def parse(
            self,
            input_path: Path,
            output_path: Path,
            focused: bool = False,
    ) -> None:
        if output_path.exists() and not self.overwrite:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        archived_urls: Iterable[ArchivedUrl] = ArchivedUrls(input_path)
        if self.verbose:
            # noinspection PyTypeChecker
            archived_urls = tqdm(
                archived_urls,
                desc="Parse SERP URLs",
                unit="URL",
            )
        archived_serp_urls_nullable = (
            self._parse_single(archived_url, focused)
            for archived_url in archived_urls
        )
        archived_serp_urls = (
            archived_serp_url
            for archived_serp_url in archived_serp_urls_nullable
            if archived_serp_url is not None
        )
        output_schema = ArchivedQueryUrl.schema()
        with (output_path.open("wb") as file,
              GzipFile(fileobj=file, mode="wb") as gzip_file,
              text_io_wrapper(gzip_file) as text_file):
            for archived_serp_url in archived_serp_urls:
                text_file.write(output_schema.dumps(archived_serp_url))
                text_file.write("\n")

    def _parse_single(
            self,
            archived_url: ArchivedUrl,
            focused: bool,
    ) -> ArchivedQueryUrl | None:
        query: str | None = None
        for query_parser in self.query_parsers:
            query = query_parser.parse(archived_url)
            if query is not None:
                break

        if query is None:
            return None

        page: int | None = None
        for page_parser in self.page_parsers:
            page = page_parser.parse(archived_url)
            if page is not None:
                break

        if focused and page is not None and page != 0:
            return None

        offset: int | None = None
        for offset_parser in self.offset_parsers:
            offset = offset_parser.parse(archived_url)
            if offset is not None:
                break

        if focused and offset is not None and offset != 0:
            return None

        return ArchivedQueryUrl(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            query=query,
            page=page,
            offset=offset,
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
        input_format_path = data_directory / "archived-urls"
        output_format_path = data_directory / "archived-query-urls"

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
            if domain is None:
                raise RuntimeError(
                    "Domain must be specified when page is specified.")
            if len(domain_paths) < 1:
                raise RuntimeError(
                    "There must be exactly one domain path.")
            cdx_page_paths = [domain_paths[0] / f"{cdx_page:010}.jsonl.gz"]
        else:
            cdx_page_paths = [
                path
                for domain_path in domain_paths
                for path in domain_path.iterdir()
                if (
                        path.is_file() and
                        len(path.name.removesuffix(".jsonl.gz")) == 10 and
                        path.name.removesuffix(".jsonl.gz").isdigit()
                )
            ]

        return [
            _CdxPage(
                input_path=cdx_page_path,
                output_path=output_format_path / cdx_page_path.relative_to(
                    input_format_path
                ),
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
            self.parse(page.input_path, page.output_path, focused)
