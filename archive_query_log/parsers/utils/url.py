from urllib.parse import parse_qsl, unquote
from pydantic import HttpUrl


def parse_url_query_parameter(parameter: str, url: HttpUrl) -> str | None:
    for key, value in parse_qsl(url.query):
        if key == parameter:
            return value
    return None


def parse_url_fragment_parameter(parameter: str, url: HttpUrl) -> str | None:
    for key, value in parse_qsl(url.fragment):
        if key == parameter:
            return value
    return None


def parse_url_path_segment(segment: int, url: HttpUrl) -> str | None:
    path = url.path
    if path is None:
        return None
    path_segments = path.split("/")
    if len(path_segments) <= segment:
        return None
    path_segment = path_segments[segment]
    return unquote(path_segment)
