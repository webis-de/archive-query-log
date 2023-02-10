# This file is auto-generated by generate_tests.py.
from web_archive_query_log.results.test.test_utils import verify_serp_parsing


def test_parse_query_imgur_search_term_string_1565643838():
    verify_serp_parsing(
        "https://web.archive.org/web/20190812230358id_/https://imgur.com/search?q={search_term_string}",
        "imgur",
    )


def test_parse_query_imgur_search_term_string_1547858079():
    verify_serp_parsing(
        "https://web.archive.org/web/20190119013439id_/https://imgur.com/search?q={search_term_string}",
        "imgur",
    )
