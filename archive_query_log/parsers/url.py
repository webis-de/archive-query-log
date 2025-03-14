from urllib.parse import parse_qsl, urlsplit, unquote


def parse_url_query_parameter(
        parameter: str, url: str) -> str | None:
    for key, value in parse_qsl(urlsplit(url).query):
        if key == parameter:
            return value
    return None


def parse_url_fragment_parameter(
        parameter: str, url: str) -> str | None:
    for key, value in parse_qsl(urlsplit(url).fragment):
        if key == parameter:
            return value
    return None


def parse_url_path_segment(segment: int, url: str) -> str | None:
    path_segments = urlsplit(url).path.split("/")
    if len(path_segments) <= segment:
        return None
    path_segment = path_segments[segment]
    return unquote(path_segment)
