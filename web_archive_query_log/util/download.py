from asyncio import ensure_future, gather, sleep
from contextlib import asynccontextmanager
from pathlib import Path
from random import random
from typing import Iterable, Mapping

from aiohttp import TCPConnector, ClientSession, ClientTimeout, \
    ClientResponseError, ClientConnectorError, ServerTimeoutError, \
    ClientPayloadError
from aiohttp_retry import RetryClient, JitterRetry
from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedUrl

_IO_CHUNK_SIZE = 64 * 1000 * 1000  # 64MB


class WebArchiveRawDownloader:

    @asynccontextmanager
    async def _session(self) -> ClientSession:
        # The Wayback Machine doesn't seem to support more than 20
        # parallel connections from the same IP.
        connector = TCPConnector(
            limit=100,
            limit_per_host=20,
        )
        # Graceful timeout as the Wayback Machine is sometimes very slow.
        timeout = ClientTimeout(
            total=10 * 60,
            connect=5 * 60,
        )
        async with ClientSession(
                connector=connector,
                timeout=timeout,
        ) as session:
            yield session

    @asynccontextmanager
    async def _client(self) -> RetryClient:
        retry_options = JitterRetry(
            attempts=10,
            start_timeout=1,  # 1 second
            max_timeout=5 * 60,  # 3 minutes
            statuses={502, 503, 504},  # server errors
            exceptions={
                ClientConnectorError,
                ServerTimeoutError,
                ClientPayloadError,
            },
        )
        async with self._session() as session:
            retry_client = RetryClient(
                client_session=session,
                retry_options=retry_options,
            )
            yield retry_client

    async def download(
            self,
            download_directory_path: Path,
            archived_urls: Iterable[ArchivedUrl],
    ) -> Mapping[ArchivedUrl, Path]:
        """
        Download the original HTML of a collection of archived URLs
        from the Internet Archive's Wayback Machine and
        return the paths to the individual downloaded files.

        The downloader will retry requests with a backoff and will continue
        downloading URLs even if some URLs fail.

        :param download_directory_path: Path to the directory in which the
         downloaded HTML files should be stored.
        :param archived_urls: The archived URLs to download.
        :return: A mapping of the successfully downloaded URLs to their
         corresponding download file paths. Failed downloads will not appear
         in the mapping.
        """
        archived_urls = list(archived_urls)
        progress = tqdm(
            total=len(archived_urls),
            desc="Download archived URLs",
            unit="URL",
        )
        async with self._client() as client:
            responses = await gather(*(
                ensure_future(self._download_single_progress(
                    download_directory_path,
                    archived_url,
                    client,
                    progress,
                ))
                for archived_url in archived_urls
            ))
        return {
            archived_url: response
            for archived_url, response in zip(archived_urls, responses)
            if response is not None
        }

    async def download_single(
            self,
            download_directory_path: Path,
            archived_url: ArchivedUrl,
    ) -> Path | None:
        """
        Download the original HTML of a single archived URL
        from the Internet Archive's Wayback Machine and
        return the path to the downloaded file.

        The downloader will retry requests with a backoff.

        :param download_directory_path: Path to the directory in which the
         downloaded HTML file should be stored.
        :param archived_url: The archived URL to download.
        :return: The download file path if the request was successful,
         and None otherwise.
        """
        async with self._client() as client:
            return await self._download_single(
                download_directory_path,
                archived_url,
                client,
            )

    @staticmethod
    async def _download_single(
            download_directory_path: Path,
            archived_url: ArchivedUrl,
            client: RetryClient,
    ) -> Path | None:
        file_name = f"{archived_url.url_domain}_{archived_url.url_md5}" \
                    f"_{archived_url.timestamp}.html"
        file_path = download_directory_path / file_name
        if file_path.exists():
            return file_path
        try:
            async with client.get(archived_url.raw_archive_url) as response:
                with file_path.open("wb") as file:
                    async for chunk in response.content.iter_chunked(
                            _IO_CHUNK_SIZE
                    ):
                        file.write(chunk)
                return file_path
        except ClientResponseError as e:
            return None

    @staticmethod
    async def _download_single_progress(
            download_directory_path: Path,
            archived_url: ArchivedUrl,
            client: RetryClient,
            progress: tqdm,
    ) -> Path | None:
        await sleep(random())
        res = await WebArchiveRawDownloader._download_single(
            download_directory_path,
            archived_url,
            client,
        )
        progress.update(1)
        return res
