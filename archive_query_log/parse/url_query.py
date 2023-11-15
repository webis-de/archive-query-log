from archive_query_log.orm import UrlQueryParser
from archive_query_log.parse.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment


def parse_url_query(parser: UrlQueryParser, url: str) -> str | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse query.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No query parameter given.")
        query = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        query = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        query = parse_url_path_segment(parser.segment, url)
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
