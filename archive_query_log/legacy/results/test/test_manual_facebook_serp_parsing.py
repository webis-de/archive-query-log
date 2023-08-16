# flake8: noqa
from archive_query_log.legacy.results.test.test_utils import verify_serp_parsing


def test_jam_of_the_day_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20140917021101id_/https://www.facebook.com/search.php?q=%22Jam+of+the+Day&init=quick&tas=0.8517628074453497&search_first_focus=1302687872720',
        'facebook'
    )


def test_victoria_pynchon_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20110110152620id_/http://www.facebook.com/search.php?q=%22Victoria+Pynchon%22&init=q',
        'facebook'
    )


def test_anthony_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20130817124019id_/http://www.facebook.com/search.php?init=srp&sfxp&q=ANTHONY',
        'facebook'
    )


def test_7_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210506042113id_/http://www.facebook.com/search.php?q=7',
        'facebook'
    )


def test_aj_duca_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20131226205922id_/http://www.facebook.com/search.php?q=AJ+Duca',
        'facebook'
    )


def test_noam_chomsky_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210125134751id_/http://www.facebook.com/search.php?q=3DNoam%20Chomsky&init=3Dquick=',
        'facebook'
    )


def test_taylor_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210126125305id_/http://www.facebook.com/search.php?q=3Dtaylor+company&am=',
        'facebook'
    )


def test_5_orsz_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210410211649id_/http://www.facebook.com/search.php?q=5+orsz%C3%A1gos',
        'facebook'
    )


def test_1_million_cards_orsz_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210304074906id_/http://www.facebook.com/search.php?q=1+million+cards&init=quick&tas=0.7974472279549098',
        'facebook'
    )


def test_abvie_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210610122030id_/http://www.facebook.com/search.php?q=Abbvie&type=users&init=srp',
        'facebook'
    )
