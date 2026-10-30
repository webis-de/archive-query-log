from urllib.parse import parse_qsl, unquote, unquote_to_bytes
from pydantic import AnyHttpUrl
from resiliparse.parse.encoding import detect_encoding


def detect_url_encoding(encoded: str) -> str:
    """If UTF-8 decoding fails, guess the URL encoding from the raw bytes."""
    data = unquote_to_bytes(encoded.replace("+", " "))
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return detect_encoding(data)
    return "utf-8"


def parse_url_query_parameter(parameter: str, url: AnyHttpUrl) -> str | None:
    if url.query is None:
        return None
    for key, value in parse_qsl(
        url.query,
        encoding=detect_url_encoding(url.query),
    ):
        if key == parameter:
            return value
    return None


def parse_url_fragment_parameter(parameter: str, url: AnyHttpUrl) -> str | None:
    if url.fragment is None:
        return None
    for key, value in parse_qsl(
        url.fragment,
        encoding=detect_url_encoding(url.fragment),
    ):
        if key == parameter:
            return value
    return None


def parse_url_path_segment(segment: int, url: AnyHttpUrl) -> str | None:
    path = url.path
    if path is None:
        return None
    path_segments = path.split("/")
    if len(path_segments) <= segment:
        return None
    path_segment = path_segments[segment]
    return unquote(path_segment)
