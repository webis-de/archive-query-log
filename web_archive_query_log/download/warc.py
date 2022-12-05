from asyncio import gather, ensure_future, sleep
from dataclasses import dataclass
from functools import cached_property
from io import BytesIO
from itertools import count
from math import log10
from pathlib import Path
from random import random
from tempfile import TemporaryFile

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from tqdm.auto import tqdm
from warcio import WARCWriter, StatusAndHeaders

from web_archive_query_log.model import ArchivedUrl
from web_archive_query_log.util.archive_http import archive_http_client
from web_archive_query_log.util.iterable import SizedIterable


@dataclass(frozen=True)
class WebArchiveWarcDownloader:
    """
    Download WARC files for archived URLs from the Web Archive.

    The downloader will retry requests with a backoff and will continue
    downloading URLs even if some URLs fail.
    """

    archived_urls: SizedIterable[ArchivedUrl]
    """
    The archived URLs to download.
    """

    download_path: Path
    """
    Path to the directory in which the downloaded HTML files should be stored.
    """

    max_file_size: int = 1_000_000_000  # 1GB
    """
    Maximum number of bytes to write to a single WARC file.
    """

    gzip: bool = True
    """
    Enable GZIP compression when writing WARC files or not.
    """

    def __post_init__(self):
        self._check_download_path()

    def _check_download_path(self):
        self.download_path.mkdir(exist_ok=True)
        if not self.download_path.is_dir():
            raise ValueError(
                f"Download path must be a directory: {self.download_path}"
            )

    @cached_property
    def _lock_path(self) -> Path:
        path = self.download_path / ".lock"
        path.touch(exist_ok=True)
        return path

    def _is_url_downloaded(self, archived_url: ArchivedUrl) -> bool:
        url = archived_url.raw_archive_url
        with self._lock_path.open("rt") as file:
            return any(
                line.strip() == url
                for line in file
            )

    def _set_url_downloaded(self, archived_url: ArchivedUrl):
        url = archived_url.raw_archive_url
        with self._lock_path.open("at") as file:
            file.write(f"{url}\n")

    def _next_available_file_path(self, buffer_size: int) -> Path:
        for index in count():
            if index > 1000 and log10(index) == 1:
                print(f"Warning: Download file lookup is at {index}.")
            name = f"{index:05}.warc.gz"
            path = self.download_path / name
            if not path.exists():
                path.touch()
                return path
            else:
                file_size = path.stat().st_size
                if file_size + buffer_size <= self.max_file_size:
                    return path

    async def download(self) -> None:
        """
        Download WARC files for archived URLs from the Web Archive.
        """
        progress = tqdm(
            total=len(self.archived_urls),
            desc="Download archived URLs",
            unit="URL",
        )
        async with archive_http_client(limit=10) as client:
            responses = await gather(*(
                ensure_future(self._download_single_progress(
                    archived_url=archived_url,
                    client=client,
                    progress=progress,
                ))
                for archived_url in self.archived_urls
            ))
        error_urls: set[ArchivedUrl] = {
            archived_url
            for archived_url, response in zip(self.archived_urls, responses)
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
            archived_url: ArchivedUrl,
            client: RetryClient,
    ) -> bool:
        if self._is_url_downloaded(archived_url):
            return True
        url = archived_url.raw_archive_url
        await sleep(1.0 * random())
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
                            statusline=f"{response.request_info.method} {response.request_info.url.path} {protocol}",
                            headers=response.request_info.headers,
                            protocol=protocol,
                        )
                    )
                    writer.write_record(request_record)
                    response_record = writer.create_warc_record(
                        uri=str(response.url),
                        record_type="response",
                        http_headers=StatusAndHeaders(
                            statusline=f"{protocol} {response.status} {response.reason}",
                            headers=response.headers,
                            protocol=protocol
                        ),
                        payload=BytesIO(await response.content.read()),
                        length=response.content_length,
                    )
                    writer.write_record(response_record)
                    tmp_file.flush()
                    tmp_size = tmp_file.tell()
                    tmp_file.seek(0)
                    file_path = self._next_available_file_path(tmp_size)
                    with file_path.open("ab") as file:
                        tmp = tmp_file.read()
                        if not len(tmp) == tmp_size:
                            raise RuntimeError("Invalid buffer size.")
                        file.write(tmp)
                    self._set_url_downloaded(archived_url)
                    return True
        except ClientResponseError:
            return False
        except BaseException as e:
            raise e

    async def _download_single_progress(
            self,
            archived_url: ArchivedUrl,
            client: RetryClient,
            progress: tqdm,
    ) -> bool:
        res = await self._download_single(archived_url, client)
        progress.update(1)
        return res
