from pydantic import AnyHttpUrl
from pytest import mark

from archive_query_log.parsers.utils.url import (
    detect_url_encoding,
    parse_url_fragment_parameter,
    parse_url_query_parameter,
)

_EUC_JP_QUERY = "%BF%CD%B5%A4+%A5%C8%A5%C3%A5%D7+%CD%A2%C6%FE%BC%D6"


@mark.parametrize(
    "encoded",
    [
        "",
        "q=test",
        "q=hello+world&page=2",
        "q=caf%C3%A9",
        "q=%D0%B4%D0%B5%D1%80%D0%B5%D0%B2%D0%BE",
        "q=%E4%B8%AD%E6%96%87",
        "q=%EF%BF%BD",
    ],
)
def test_detect_url_encoding_valid_utf8(encoded: str) -> None:
    assert detect_url_encoding(encoded) == "utf-8"


def test_detect_url_encoding_guesses_invalid_utf8() -> None:
    assert detect_url_encoding(f"MT={_EUC_JP_QUERY}") == "euc_jp"


def test_parse_url_query_parameter_non_utf8() -> None:
    url = AnyHttpUrl(f"http://search.goo.ne.jp/web.jsp?MT={_EUC_JP_QUERY}&DC=10")
    assert parse_url_query_parameter("MT", url) == "人気 トップ 輸入車"


def test_parse_url_fragment_parameter_non_utf8() -> None:
    url = AnyHttpUrl(f"http://search.goo.ne.jp/web.jsp#MT={_EUC_JP_QUERY}&DC=10")
    assert parse_url_fragment_parameter("MT", url) == "人気 トップ 輸入車"


def test_parse_url_query_parameter_utf8() -> None:
    url = AnyHttpUrl("https://www.google.com/search?q=caf%C3%A9+%D0%B4")
    assert parse_url_query_parameter("q", url) == "café д"


def test_parse_url_parameters_missing() -> None:
    url = AnyHttpUrl("https://www.google.com/search")
    assert parse_url_query_parameter("q", url) is None
    assert parse_url_fragment_parameter("q", url) is None
