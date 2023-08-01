from io import BytesIO
from typing import IO

from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Session, Response
from requests_ratelimiter import LimiterAdapter
from tqdm.auto import tqdm
from urllib3 import Retry

from archive_query_log import __version__ as version

session = Session()
session.headers.update({
    "User-Agent": f"AQL/{version} (Webis group)",
})
_retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[502, 503, 504],
)
_limiter = Limiter(
    RequestRate(1, Duration.SECOND * 10),
)
_adapter = LimiterAdapter(
    max_retries=_retries,
    limiter=_limiter,
)
# noinspection HttpUrlsUsage
session.mount("http://", _adapter)
session.mount("https://", _adapter)


def download_response_content(
        response: Response,
        chunk_size: int = 1024,
) -> IO[bytes]:
    file = BytesIO()
    total = int(response.headers.get('content-length', 0))
    with tqdm(
            desc="Downloading",
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=chunk_size):
            size = file.write(data)
            bar.update(size)
    file.seek(0)
    return file
