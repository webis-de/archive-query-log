from archive_query_log.orm import UrlPageParser
from archive_query_log.parse.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment


def parse_url_page(parser: UrlPageParser, url: str) -> int | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse page.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No page parameter given.")
        page_string = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        page_string = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        page_string = parse_url_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if page_string is None:
        return None

    # Clean up page string.
    if parser.remove_pattern is not None:
        page_string = parser.remove_pattern.sub("", page_string)
    page_string = page_string.strip()
    page = int(page_string)
    return page
