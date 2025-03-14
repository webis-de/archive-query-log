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
