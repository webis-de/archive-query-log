from asyncio import sleep
from pathlib import Path
from random import random
from typing import Iterable, Callable, Mapping

from aiohttp import ClientResponseError
from aiohttp_retry import RetryClient
from asyncio_pool import AioPool
from tqdm.auto import tqdm

from archive_query_log.legacy.model import ArchivedUrl
from archive_query_log.legacy.util.archive_http import archive_http_client


class WebArchiveRawDownloader:

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
        async with archive_http_client(limit=10) as client:
            pool = AioPool(size=100)  # avoid creating too many tasks at once

            async def download_single(archived_url: ArchivedUrl):
                return await self._download_single_progress(
                    archived_url,
                    download_directory_path,
                    file_name,
                    client,
                    progress,
                )

            responses = await pool.map(download_single, archived_urls)
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
        async with archive_http_client(limit=1) as client:
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
        await sleep(1.0 * random())  # nosec: B311
        try:
            async with client.get(url) as response:
                response.raise_for_status()
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
