# flake8: noqa
# This file is auto-generated by generate_tests.py.
from archive_query_log.results.test.test_utils import verify_serp_parsing


def test_parse_query_imdb_pulse_1283006912():
    verify_serp_parsing(
        "https://web.archive.org/web/20100828144832id_/http://www.imdb.com:80/find?s=all&q=Pulse",
        "imdb",
    )


def test_parse_query_imdb_0609265_s_nm_1329020836():
    verify_serp_parsing(
        "https://web.archive.org/web/20120212042716id_/http://www.imdb.com:80/find?q=0609265;s=nm",
        "imdb",
    )


def test_parse_query_imdb_angelina_jolie_1452700725():
    verify_serp_parsing(
        "https://web.archive.org/web/20160113155845id_/http://www.imdb.com:80/find?ref_=nv_sr_fn&q=Angelina+Jolie&s=all",
        "imdb",
    )


def test_parse_query_imdb_marcela_gomez_montoya_1614546944():
    verify_serp_parsing(
        "https://web.archive.org/web/20210228211544id_/http://www.imdb.com/find?q=Marcela%20G%C3%B3mez%20Montoya&exact=true",
        "imdb",
    )


def test_parse_query_imdb_murder_world_1268209692():
    verify_serp_parsing(
        "https://web.archive.org/web/20100310082812id_/http://www.imdb.com:80/find?s=all&q=murder+world",
        "imdb",
    )


def test_parse_query_imdb_gundula_rapsch_1628094679():
    verify_serp_parsing(
        "https://web.archive.org/web/20210804163119id_/https://www.imdb.com/find?q=Gundula+Rapsch&s=nm",
        "imdb",
    )


def test_parse_query_imdb_sam_claflin_1472223834():
    verify_serp_parsing(
        "https://web.archive.org/web/20160826150354id_/http://www.imdb.com:80/find?q=Sam%20Claflin&s=nm",
        "imdb",
    )


def test_parse_query_imdb_the_expanse_1521743964():
    verify_serp_parsing(
        "https://web.archive.org/web/20180322183924id_/http://www.imdb.com:80/find?s=all&q=the+expanse",
        "imdb",
    )


def test_parse_query_imdb_dogville_1187303706():
    verify_serp_parsing(
        "https://web.archive.org/web/20070816223506id_/http://www.imdb.com:80/find?s=all&q=dogville",
        "imdb",
    )


def test_parse_query_imdb_hunger_games_1518585690():
    verify_serp_parsing(
        "https://web.archive.org/web/20180214052130id_/http://www.imdb.com:80/find?q=hunger+games&s=tt&ref_=fn_tt",
        "imdb",
    )
