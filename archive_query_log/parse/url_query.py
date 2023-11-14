from urllib.parse import parse_qsl, urlsplit, unquote

from archive_query_log.orm import UrlQueryParser


def parse_url_query(parser: UrlQueryParser, url: str) -> str | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse query.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No query parameter given.")
        query = _parse_url_query_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        query = _parse_url_query_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        query = _parse_url_query_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if query is None:
        return None

    # Clean up query.
    if parser.remove_pattern is not None:
        query = parser.remove_pattern.sub("", query)
    if parser.space_pattern is not None:
        query = parser.space_pattern.sub(" ", query)
    query = query.strip()
    query = " ".join(query.split())
    return query


def _parse_url_query_query_parameter(parameter: str, url: str) -> str | None:
    for key, value in parse_qsl(urlsplit(url).query):
        if key == parameter:
            return value
    return None


def _parse_url_query_fragment_parameter(
        parameter: str, url: str) -> str | None:
    for key, value in parse_qsl(urlsplit(url).fragment):
        if key == parameter:
            return value
    return None


def _parse_url_query_path_segment(segment: int, url: str) -> str | None:
    path_segments = urlsplit(url).path.split("/")
    if len(path_segments) <= segment:
        return None
    path_segment = path_segments[segment]
    return unquote(path_segment)
