from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sequence, NamedTuple
from urllib.parse import parse_qsl, unquote, quote

from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedQueryUrl, \
    ArchivedUrl, PageParser, QueryParser, OffsetParser, Service
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

    def parse(self, input_path: Path, output_path: Path) -> None:
        if output_path.exists() and not self.overwrite:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
        output_schema = ArchivedQueryUrl.schema()
        # noinspection PyTypeChecker
        with output_path.open("wb") as file, \
                GzipFile(fileobj=file, mode="wb") as gzip_file, \
                TextIOWrapper(gzip_file) as text_file:
            for archived_serp_url in archived_serp_urls:
                text_file.write(output_schema.dumps(archived_serp_url))
                text_file.write("\n")

    def _parse_single(
            self,
            archived_url: ArchivedUrl
    ) -> ArchivedQueryUrl | None:
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
            assert domain is not None
            assert len(domain_paths) == 1
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
