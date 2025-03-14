from contextlib import asynccontextmanager
from typing import AsyncIterator

from aiohttp import ClientSession, TCPConnector, ClientTimeout, \
    ClientConnectorError, ServerTimeoutError, ClientPayloadError
from aiohttp_retry import RetryClient, JitterRetry


@asynccontextmanager
async def archive_http_session(
        limit: int = 10,
) -> AsyncIterator[ClientSession]:
    # The Wayback Machine doesn't seem to support more than 10
    # parallel connections from the same IP.
    connector = TCPConnector(
        limit_per_host=limit,
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
async def archive_http_client(limit: int = 10) -> AsyncIterator[RetryClient]:
    retry_options = JitterRetry(
        attempts=10,
        start_timeout=10,  # 10 seconds
        max_timeout=15 * 60,  # 15 minutes
        statuses={429, 502, 503, 504},  # server errors
        exceptions={
            ClientConnectorError,
            ServerTimeoutError,
            ClientPayloadError,
        },
    )
    async with archive_http_session(limit) as session:
        retry_client = RetryClient(
            client_session=session,
            retry_options=retry_options,
        )
        yield retry_client
