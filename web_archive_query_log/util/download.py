from asyncio import ensure_future, gather, sleep
from contextlib import asynccontextmanager
from pathlib import Path
from random import random
from typing import Iterable, Mapping, Callable

from aiohttp import TCPConnector, ClientSession, ClientTimeout, \
    ClientResponseError, ClientConnectorError, ServerTimeoutError, \
    ClientPayloadError
from aiohttp_retry import RetryClient, JitterRetry
from tqdm.auto import tqdm

from web_archive_query_log.model import ArchivedUrl

_MAX_CONNECTIONS_PER_HOST = 10
_MAX_BYTES_PER_SECOND = 1 * 1000 * 1000  # 1MB


class WebArchiveRawDownloader:

    @asynccontextmanager
    async def _session(self) -> ClientSession:
        # The Wayback Machine doesn't seem to support more than 10
        # parallel connections from the same IP.
        connector = TCPConnector(
            limit_per_host=_MAX_CONNECTIONS_PER_HOST,
        )
        # Graceful timeout as the Wayback Machine is sometimes very slow.
        timeout = ClientTimeout(
            total=15 * 60,
            connect=5 * 60,  # Setting up a connection is especially slow.
            sock_read=5 * 60,
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
            max_timeout=15 * 60,  # 15 minutes
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
            archived_urls: Iterable[ArchivedUrl],
            download_directory_path: Path,
            file_name: Callable[[ArchivedUrl], str],
    ) -> Mapping[ArchivedUrl, Path]:
        """
        Download the original HTML of a collection of archived URLs
        from the Internet Archive's Wayback Machine and
        return the paths to the individual downloaded files.

        The downloader will retry requests with a backoff and will continue
        downloading URLs even if some URLs fail.

        :param archived_urls: The archived URLs to download.
        :param download_directory_path: Path to the directory in which the
         downloaded HTML files should be stored.
        :param file_name: Function for specifying each URL's file name
         in the download directory.
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
                    archived_url=archived_url,
                    download_directory_path=download_directory_path,
                    file_name=file_name,
                    client=client,
                    progress=progress,
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
            archived_url: ArchivedUrl,
            download_directory_path: Path,
            file_name: Callable[[ArchivedUrl], str],
    ) -> Path | None:
        """
        Download the original HTML of a single archived URL
        from the Internet Archive's Wayback Machine and
        return the path to the downloaded file.

        The downloader will retry requests with a backoff.

        :param archived_url: The archived URL to download.
        :param download_directory_path: Path to the directory in which the
         downloaded HTML file should be stored.
        :param file_name: Function for specifying each URL's file name
         in the download directory.
        :return: The download file path if the request was successful,
         and None otherwise.
        """
        async with self._client() as client:
            return await self._download_single(
                archived_url=archived_url,
                download_directory_path=download_directory_path,
                file_name=file_name,
                client=client,
            )

    @staticmethod
    async def _download_single(
            archived_url: ArchivedUrl,
            download_directory_path: Path,
            file_name: Callable[[ArchivedUrl], str],
            client: RetryClient,
    ) -> Path | None:
        file_path = download_directory_path / file_name(archived_url)
        if file_path.exists():
            return file_path
        url = archived_url.raw_archive_url
        await sleep(1.0 * random())
        try:
            async with client.get(url) as response:
                with file_path.open("wb") as file:
                    async for data, _ in response.content.iter_chunks():
                        file.write(data)
                return file_path
        except ClientResponseError:
            file_path.unlink(missing_ok=True)
            return None
        except BaseException as e:
            file_path.unlink(missing_ok=True)
            raise e

    @staticmethod
    async def _download_single_progress(
            archived_url: ArchivedUrl,
            download_directory_path: Path,
            file_name: Callable[[ArchivedUrl], str],
            client: RetryClient,
            progress: tqdm,
    ) -> Path | None:
        res = await WebArchiveRawDownloader._download_single(
            archived_url=archived_url,
            download_directory_path=download_directory_path,
            file_name=file_name,
            client=client,
        )
        progress.update(1)
        return res
