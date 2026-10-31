from urllib.parse import quote_from_bytes

from pydantic import AnyHttpUrl
from pytest import mark

from archive_query_log.parsers.utils.url import (
    parse_url_fragment_parameter,
    parse_url_query_parameter,
)

_EUC_JP_QUERY = "%BF%CD%B5%A4+%A5%C8%A5%C3%A5%D7+%CD%A2%C6%FE%BC%D6"
_EUC_JP_DECODED = "人気 トップ 輸入車"


def _parse_query(query_string: str) -> str | None:
    return parse_url_query_parameter(
        "q", AnyHttpUrl(f"https://example.org/search?{query_string}")
    )


@mark.parametrize(
    ("query_string", "expected"),
    [
        ("q=test", "test"),
        ("q=hello+world&page=2", "hello world"),
        ("q=caf%C3%A9+%D0%B4", "café д"),
        ("q=%E4%B8%AD%E6%96%87", "中文"),
        ("q=%EF%BF%BD", "\ufffd"),
        ("q=中文", "中文"),
    ],
)
def test_parse_url_query_parameter_utf8(query_string: str, expected: str) -> None:
    assert _parse_query(query_string) == expected


def test_parse_url_query_parameter_non_utf8() -> None:
    assert _parse_query(f"q={_EUC_JP_QUERY}&DC=10") == _EUC_JP_DECODED


def test_parse_url_fragment_parameter_non_utf8() -> None:
    url = AnyHttpUrl(f"http://search.goo.ne.jp/web.jsp#MT={_EUC_JP_QUERY}&DC=10")
    assert parse_url_fragment_parameter("MT", url) == _EUC_JP_DECODED


def test_parse_url_parameters_missing() -> None:
    url = AnyHttpUrl("https://www.google.com/search")
    assert parse_url_query_parameter("q", url) is None
    assert parse_url_fragment_parameter("q", url) is None


@mark.parametrize(
    ("query", "encoding"),
    [
        ("定时关机器", "gb18030"),
        ("高邮头闸公交查询", "gb18030"),
        ("東京のホテル", "euc_jp"),
        ("テスト", "shift_jis"),
        ("개미는 오늘도", "euc_kr"),
        ("почта россии в москве на карте", "cp1251"),
        ("Schokoladensoße", "cp1252"),
    ],
)
def test_parse_url_query_parameter_guesses_encoding(query: str, encoding: str) -> None:
    encoded = quote_from_bytes(query.encode(encoding), safe="")
    assert _parse_query(f"q={encoded}") == query


def test_parse_url_query_parameter_declared_encoding() -> None:
    # Ambiguous, but declared as Big5 instead of the more likely GB18030.
    assert _parse_query("q=%BF%CD%B5%A4&ie=big5") == b"\xbf\xcd\xb5\xa4".decode("big5")
    assert _parse_query("IE=EUC-JP&q=%BF%CD%B5%A4") == "人気"


@mark.parametrize("declared", ["utf-8", "bogus"])
def test_parse_url_query_parameter_ignores_unusable_declaration(declared: str) -> None:
    assert _parse_query(f"q={_EUC_JP_QUERY}&ie={declared}") == _EUC_JP_DECODED


def test_parse_url_query_parameter_keeps_utf8_next_to_non_utf8() -> None:
    query_string = "ie=UTF-8&bs=%B0%A1&q=%E5%87%8C%E6%BA%90%E5%B8%82&oq=%B5%E7%D3%B0"
    assert _parse_query(query_string) == "凌源市"


def test_parse_url_query_parameter_ignores_other_invalid_values() -> None:
    other = quote_from_bytes("почта россии в москве".encode("cp1251"), safe="")
    assert _parse_query(f"q={_EUC_JP_QUERY}&x={other}") == _EUC_JP_DECODED
