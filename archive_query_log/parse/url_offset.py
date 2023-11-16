from archive_query_log.orm import UrlOffsetParser
from archive_query_log.parse.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment


def parse_url_offset(parser: UrlOffsetParser, url: str) -> int | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse offset.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No offset parameter given.")
        offset_string = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        offset_string = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        offset_string = parse_url_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if offset_string is None:
        return None

    # Clean up offset string.
    if parser.remove_pattern is not None:
        offset_string = parser.remove_pattern.sub("", offset_string)
    offset_string = offset_string.strip()
    offset = int(offset_string)
    return offset
