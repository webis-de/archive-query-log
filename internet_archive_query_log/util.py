from urllib.parse import urlparse

from click.types import StringParamType
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def backoff_session() -> Session:
    session = Session()
    retries = Retry(
        total=10,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


class UrlParamType(StringParamType):
    name = "url"

    def convert(self, value, param, ctx):
        value = super().convert(value, param, ctx)
        if value is None:
            return None
        tokens = urlparse(value)
        if not tokens.scheme or not tokens.netloc:
            self.fail(f"{value} is not a valid URL", param, ctx)
        return value


URL = UrlParamType()
