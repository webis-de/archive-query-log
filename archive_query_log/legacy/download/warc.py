from dataclasses import dataclass
from io import BytesIO
from itertools import count, groupby, chain
from pathlib import Path
from random import Random
from tempfile import TemporaryFile
from typing import Sequence, NamedTuple, Iterable
from urllib.parse import quote, parse_qsl

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from asyncio_pool import AioPool
from tqdm.auto import tqdm
from warcio import WARCWriter, StatusAndHeaders

from archive_query_log.legacy.model import ArchivedUrl, Service, \
    ArchivedQueryUrl
from archive_query_log.legacy.queries.iterable import ArchivedQueryUrls
from archive_query_log.legacy.serps.iterable import ArchivedParsedSerps
from archive_query_log.legacy.util.archive_http import archive_http_client


class _CdxPage(NamedTuple):
    input_path: Path
    output_path: Path


class _CdxUrl(NamedTuple):
    archived_url: ArchivedUrl
    output_path: Path


@dataclass(frozen=True)
class WebArchiveWarcDownloader:
    """
    Download WARC files for archived URLs from the Web Archive.

    The downloader will retry requests with a backoff and will continue
    downloading URLs even if some URLs fail.
    """

    max_file_size: int = 1_000_000_000  # 1GB
    """
    Maximum number of bytes to write to a single WARC file.
    """
    verbose: bool = False

    @staticmethod
    def _check_download_path(download_path: Path):
        download_path.mkdir(parents=True, exist_ok=True)
        if not download_path.is_dir():
            raise ValueError(
                f"Download path must be a directory: {download_path}"
            )

    @staticmethod
    def _lock_path(download_path: Path) -> Path:
        path = download_path / ".lock"
        path.touch(exist_ok=True)
        return path

    def _is_url_downloaded(self, url: _CdxUrl) -> bool:
        if not url.output_path.exists():
            return False
        archive_url = url.archived_url.raw_archive_url
        with self._lock_path(url.output_path).open("rt") as file:
            return any(
                line.strip() == archive_url
                for line in file
            )

    def _set_url_downloaded(self, url: _CdxUrl):
        archive_url = url.archived_url.raw_archive_url
        with self._lock_path(url.output_path).open("at") as file:
            file.write(f"{archive_url}\n")

    def _next_available_file_path(
            self,
            download_path: Path,
            buffer_size: int,
    ) -> Path:
        WebArchiveWarcDownloader._check_download_path(download_path)
        for index in count():
            name = f"{index:010}.warc.gz"
            path = download_path / name
            if not path.exists():
                path.touch()
                return path
            else:
                file_size = path.stat().st_size
                if file_size + buffer_size <= self.max_file_size:
                    return path
        raise RuntimeError("All available file paths are filled.")

    async def _download(
            self,
            urls: Iterable[_CdxUrl],
    ) -> None:
        """
        Download WARC files for archived URLs from the Web Archive.
        """

        urls = [
            url
            for url in urls
            if not self._is_url_downloaded(url)
        ]
        if len(urls) == 0:
            return

        progress = None
        if self.verbose:
            progress = tqdm(
                total=len(urls),
                desc="Download archived URLs",
                unit="URL",
            )

        async with archive_http_client(limit=100) as client:
            pool = AioPool(size=100)  # avoid creating too many tasks at once

            async def download_single(url: _CdxUrl):
                return await self._download_single(client, url, progress)

            await pool.map(download_single, urls)

    async def download(
            self,
            download_path: Path,
            archived_urls: Iterable[ArchivedUrl],
    ) -> None:
        """
        Download WARC files for archived URLs from the Web Archive.
        """
        await self._download([
            _CdxUrl(url, download_path)
            for url in archived_urls
        ])

    async def _download_single(
            self,
            client: RetryClient,
            url: _CdxUrl,
            progress: tqdm | None = None,
    ) -> bool:
        if self._is_url_downloaded(url):
            if progress is not None:
                progress.update()
            return True
        archive_url = url.archived_url.raw_archive_url
        url_headers = {
            "Archived-URL": url.archived_url.schema().dumps(url.archived_url),
        }
        try:
            async with client.get(archive_url) as response:
                response.raise_for_status()
                with TemporaryFile() as tmp_file:
                    writer = WARCWriter(tmp_file, gzip=True)
                    # noinspection PyProtectedMember
                    version = client._client.version
                    protocol = f"HTTP/{version[0]}.{version[1]}"
                    request_record = writer.create_warc_record(
                        uri=str(response.request_info.url),
                        record_type="request",
                        http_headers=StatusAndHeaders(
                            statusline=" ".join((
                                response.request_info.method,
                                response.request_info.url.path,
                                protocol,
                            )),
                            headers=response.request_info.headers,
                            protocol=protocol,
                        ),
                        warc_headers_dict={**url_headers},
                    )
                    writer.write_record(request_record)

                    protocol = f"HTTP/{response.version}"
                    reason = str(response.reason)
                    response_record = writer.create_warc_record(
                        uri=str(response.url),
                        record_type="response",
                        http_headers=StatusAndHeaders(
                            statusline=" ".join((
                                protocol,
                                str(response.status),
                                reason,
                            )),
                            headers=response.headers,
                            protocol=protocol
                        ),
                        payload=BytesIO(await response.content.read()),
                        length=response.content_length,
                        warc_headers_dict={**url_headers},
                    )
                    writer.write_record(response_record)
                    tmp_file.flush()
                    tmp_size = tmp_file.tell()
                    tmp_file.seek(0)
                    file_path = self._next_available_file_path(
                        url.output_path,
                        tmp_size,
                    )
                    with file_path.open("ab") as file:
                        tmp = tmp_file.read()
                        if not len(tmp) == tmp_size:
                            raise RuntimeError("Invalid buffer size.")
                        file.write(tmp)
                    self._set_url_downloaded(url)
                    return True
        except ClientResponseError:
            return False
        except BaseException as e:
            raise e
        finally:
            if progress is not None:
                progress.update()

    def _service_pages(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None,
            cdx_page: int | None,
            snippets: bool = False,
    ) -> Sequence[_CdxPage]:
        """
        List all items that need to be downloaded.
        """
        if snippets:
            input_format_path = data_directory / "archived-parsed-serps"
            output_format_path = data_directory / "archived-raw-search-results"
        else:
            input_format_path = data_directory / "archived-query-urls"
            output_format_path = data_directory / "archived-raw-serps"

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

        pages = (
            _CdxPage(
                input_path=cdx_page_path,
                output_path=output_format_path / cdx_page_path.relative_to(
                    input_format_path
                ).with_name(cdx_page_path.name.removesuffix(".jsonl.gz")),
            )
            for cdx_page_path in cdx_page_paths
        )
        return [page for page in pages if page.input_path.exists()]

    @staticmethod
    def _canonical_url(urls: Iterable[_CdxUrl]) -> _CdxUrl:
        """
        First URL, sorted by URL query string length, then by URL length,
        then by URL.
        """
        urls = sorted(
            urls,
            key=lambda url: url.archived_url.url
        )
        urls = sorted(
            urls,
            key=lambda url: len(url.archived_url.url)
        )
        urls = sorted(
            urls,
            key=lambda url: len(parse_qsl(url.archived_url.split_url.query))
        )
        return urls[0]

    @staticmethod
    def _deduplicate_urls(
            urls: Iterable[_CdxUrl],
            snippets: bool,
    ) -> list[_CdxUrl]:
        if snippets:
            return list(urls)
        if not all(
            isinstance(url.archived_url, ArchivedQueryUrl)
            for url in urls
        ):
            return list(urls)
        urls = sorted(
            urls,
            key=lambda url: (
                url.archived_url.query
                if isinstance(url.archived_url, ArchivedQueryUrl) else "")
        )
        grouped_query_urls = groupby(
            urls,
            key=lambda url: (
                url.archived_url.query
                if isinstance(url.archived_url, ArchivedQueryUrl) else "")
        )
        return [
            WebArchiveWarcDownloader._canonical_url(urls)
            for query, urls in grouped_query_urls
        ]

    @staticmethod
    def _page_urls(
            page: _CdxPage,
            focused: bool,
            snippets: bool,
    ) -> Iterable[_CdxUrl]:
        urls: Iterable[_CdxUrl]
        if snippets:
            urls = (
                _CdxUrl(url, page.output_path)
                for serp in ArchivedParsedSerps(page.input_path)
                for url in serp.results
            )
        else:
            urls = (
                _CdxUrl(url, page.output_path)
                for url in ArchivedQueryUrls(page.input_path)
            )
        if focused:
            urls = WebArchiveWarcDownloader._deduplicate_urls(urls, snippets)
        return urls

    async def download_service(
            self,
            data_directory: Path,
            focused: bool,
            service: Service,
            domain: str | None = None,
            cdx_page: int | None = None,
            snippets: bool = False,
    ):
        pages_list: Sequence[_CdxPage] = self._service_pages(
            data_directory=data_directory,
            focused=focused,
            service=service,
            domain=domain,
            cdx_page=cdx_page,
            snippets=snippets,
        )

        if len(pages_list) == 0:
            return

        pages: Iterable[_CdxPage] = pages_list
        if focused:
            # noinspection PyTypeChecker
            pages = tqdm(
                pages,
                desc="Deduplicate query URLs",
                unit="page",
            )

        cdx_urls: Sequence[_CdxUrl] = list(chain.from_iterable(
            self._page_urls(page, focused, snippets)
            for page in pages
        ))

        if focused:
            archived_urls_list = self._deduplicate_urls(
                cdx_urls, snippets)
            sample_size = min(len(cdx_urls), 75_000)
            random = Random(0)  # nosec: B311
            cdx_urls = random.sample(archived_urls_list, sample_size)

        await self._download(cdx_urls)
