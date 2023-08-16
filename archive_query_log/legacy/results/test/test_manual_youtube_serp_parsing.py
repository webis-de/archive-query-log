# flake8: noqa
from archive_query_log.legacy.results.test.test_utils import verify_serp_parsing


def test_chaoz_time_search():
    verify_serp_parsing(
        'https://web.archive.org/web/20220510040811id_/https://www.youtube.com/results?search_query=%21%21%21Chaoz+time%21%21%21',
        'youtube'
    )
