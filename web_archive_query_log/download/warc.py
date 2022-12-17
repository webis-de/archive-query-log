from dataclasses import dataclass
from io import BytesIO
from itertools import count
from pathlib import Path
from tempfile import TemporaryFile
from typing import Sequence, NamedTuple

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from asyncio_pool import AioPool
from tqdm.auto import tqdm
from warcio import WARCWriter, StatusAndHeaders

from web_archive_query_log.model import ArchivedUrl, Service
from web_archive_query_log.queries.iterable import ArchivedQueryUrls
from web_archive_query_log.util.archive_http import archive_http_client
from web_archive_query_log.util.iterable import SizedIterable


class _CdxPage(NamedTuple):
    input_path: Path
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

    def _is_url_downloaded(
            self,
            download_path: Path,
            archived_url: ArchivedUrl,
    ) -> bool:
        url = archived_url.raw_archive_url
        with self._lock_path(download_path).open("rt") as file:
            return any(
                line.strip() == url
                for line in file
            )

    def _set_url_downloaded(
            self,
            download_path: Path,
            archived_url: ArchivedUrl,
    ):
        url = archived_url.raw_archive_url
        with self._lock_path(download_path).open("at") as file:
            file.write(f"{url}\n")

    def _next_available_file_path(
            self,
            download_path: Path,
            buffer_size: int,
    ) -> Path:
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

    async def download(
            self,
            download_path: Path,
            archived_urls: SizedIterable[ArchivedUrl],
    ) -> None:
        """
        Download WARC files for archived URLs from the Web Archive.
        """
        self._check_download_path(download_path)

        archived_urls = [
            archived_url
            for archived_url in archived_urls
            if not self._is_url_downloaded(download_path, archived_url)
        ]
        if len(archived_urls) == 0:
            return

        progress = None
        if self.verbose:
            progress = tqdm(
                total=len(archived_urls),
                desc="Download archived URLs",
                unit="URL",
            )

        async with archive_http_client(limit=100) as client:
            pool = AioPool(size=100)  # avoid creating too many tasks at once

            async def download_single(archived_url: ArchivedUrl):
                return await self._download_single(
                    download_path,
                    client,
                    archived_url,
                    progress,
                )

            responses = await pool.map(download_single, archived_urls)
        error_urls: set[ArchivedUrl] = {
            archived_url
            for archived_url, response in zip(archived_urls, responses)
            if response is None
        }
        if len(error_urls) > 0:
            if len(error_urls) > 10:
                raise RuntimeError(
                    f"Some downloads did not succeed: "
                    f"{len(error_urls)} in total"
                )
            else:
                raise RuntimeError(
                    f"Some downloads did not succeed: "
                    f"{', '.join(url.raw_archive_url for url in error_urls)}"
                )

    async def _download_single(
            self,
            download_path: Path,
            client: RetryClient,
            archived_url: ArchivedUrl,
            progress: tqdm | None = None,
    ) -> bool:
        if self._is_url_downloaded(download_path, archived_url):
            if progress is not None:
                progress.update()
            return True
        url = archived_url.raw_archive_url
        url_headers = {
            "Archived-URL": archived_url.schema().dumps(archived_url),
        }
        try:
            async with client.get(url) as response:
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
                    response_record = writer.create_warc_record(
                        uri=str(response.url),
                        record_type="response",
                        http_headers=StatusAndHeaders(
                            statusline=" ".join((
                                protocol,
                                str(response.status),
                                response.reason,
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
                        download_path,
                        tmp_size,
                    )
                    with file_path.open("ab") as file:
                        tmp = tmp_file.read()
                        if not len(tmp) == tmp_size:
                            raise RuntimeError("Invalid buffer size.")
                        file.write(tmp)
                    self._set_url_downloaded(download_path, archived_url)
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
    ) -> Sequence[_CdxPage]:
        """
        List all items that need to be downloaded.
        """
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
                        path.name.endswith(prefix)
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

    async def download_service(
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
                desc="Download archived SERP contents",
                unit="page",
            )

        for page in pages:
            archived_urls = ArchivedQueryUrls(page.input_path)
            await self.download(page.output_path, archived_urls)
