# flake8: noqa
from archive_query_log.results.test.test_utils import verify_serp_parsing


def test_9_11_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210411035549id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+9/11+revisited%22',
        'google'
    )


def test_lenin_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210227012632id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+Lenin%22',
        'google'
    )


def test_august_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210225074449id_/http://www.google.com/search?hl=en&q=%22%22+%22Agust&iacute;n',
        'google'
    )


def test_cortisol_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210609042746id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&safe=off&q=++++%22+Cortisol+test%22',
        'google'
    )


def test_coxsackie_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210330143639id_/http://www.google.com/search?hl=en&ie=ISO-8859-1&q=%22+coxsackie+virus%22_',
        'google'
    )


def test_homemade_l_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210330143719id_/http://www.google.com/search?hl=en&source=hp&ie=ISO-8859-1&q=%22+homemade+l',
        'google'
    )


def test_homemade_dove_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210330143611id_/http://www.google.com/search?hl=en&ie=ISO-8859-1&q=%22+dove%22+%22soap%22+%22',
        'google'
    )


def test_dead_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20210224224643id_/http://www.google.com/search?hl=en&lr=&ie=ISO-8859-1&q=%22+dead+cock%22+mortuary',
        'google'
    )


def test_boston_hotels_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20030829041921id_/http://www.google.com:80/search?q=%22+www.boston-hotels-cheap.net%22',
        'google'
    )


def test_extractresult_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20030901014927id_/http://www.google.com:80/search?q=%22+www.exactresult.+com/%22',
        'google'
    )


def test_wallstquotes_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20030829090453id_/http://www.google.com:80/search?q=%22+www.wallstquotes.+com%22',
        'google'
    )
