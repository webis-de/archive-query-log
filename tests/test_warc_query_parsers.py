from pathlib import Path
from typing import Iterator, Iterable

from pytest import mark


from archive_query_log.parsers.warc_query import parse_serp_warc_query_action

from tests import TESTS_DATA_PATH
from tests.utils import MockWarcStore, iter_test_serps, verify_yaml

_SERPS_PATHS = (
    # TESTS_DATA_PATH / "360.jsonl",
    # TESTS_DATA_PATH / "aliexpress.jsonl",
    # TESTS_DATA_PATH / "amazon.jsonl",
    # TESTS_DATA_PATH / "ask.jsonl",
    # TESTS_DATA_PATH / "baidu.jsonl",
    # TESTS_DATA_PATH / "bing.jsonl",
    # TESTS_DATA_PATH / "bongacams.jsonl",
    # TESTS_DATA_PATH / "brave.jsonl",
    # TESTS_DATA_PATH / "canva.jsonl",
    # TESTS_DATA_PATH / "chefkoch.jsonl",
    # TESTS_DATA_PATH / "cnn.jsonl",
    # TESTS_DATA_PATH / "csdn.jsonl",
    # TESTS_DATA_PATH / "duckduckgo.jsonl",
    # TESTS_DATA_PATH / "ebay.jsonl",
    # TESTS_DATA_PATH / "ecosia.jsonl",
    # TESTS_DATA_PATH / "espn.jsonl",
    # TESTS_DATA_PATH / "etsy.jsonl",
    # TESTS_DATA_PATH / "facebook.jsonl",
    # TESTS_DATA_PATH / "github.jsonl",
    # TESTS_DATA_PATH / "google.jsonl",
    # TESTS_DATA_PATH / "imdb.jsonl",
    # TESTS_DATA_PATH / "imgur.jsonl",
    # TESTS_DATA_PATH / "indeed.jsonl",
    # TESTS_DATA_PATH / "jd.jsonl",
    # TESTS_DATA_PATH / "linkedin.jsonl",
    # TESTS_DATA_PATH / "manual.jsonl",
    # TESTS_DATA_PATH / "naver.jsonl",
    # TESTS_DATA_PATH / "pornhub.jsonl",
    # TESTS_DATA_PATH / "qq.jsonl",
    # TESTS_DATA_PATH / "qwant.jsonl",
    # TESTS_DATA_PATH / "reddit.jsonl",
    # TESTS_DATA_PATH / "roblox.jsonl",
    # TESTS_DATA_PATH / "sogou.jsonl",
    # TESTS_DATA_PATH / "stackoverflow.jsonl",
    # TESTS_DATA_PATH / "tribunnews.jsonl",
    # TESTS_DATA_PATH / "twitch.jsonl",
    # TESTS_DATA_PATH / "twitter.jsonl",
    # TESTS_DATA_PATH / "vk.jsonl",
    # TESTS_DATA_PATH / "weibo.jsonl",
    # TESTS_DATA_PATH / "wikimedia.jsonl",
    # TESTS_DATA_PATH / "xvideos.jsonl",
    # TESTS_DATA_PATH / "yahoo.jsonl",
    # TESTS_DATA_PATH / "yandex.jsonl",
    TESTS_DATA_PATH / "youtube.jsonl",
)


def _iter_clean_actions(actions: Iterable[dict]) -> Iterator[dict]:
    """
    Remove non-deterministic fields from actions for easier approval testing.
    """
    for action in actions:
        if "last_parsed" in action["doc"]["warc_query_parser"]:
            del action["doc"]["warc_query_parser"]["last_parsed"]
        yield action


@mark.parametrize("serps_path", _SERPS_PATHS, ids=[p.stem for p in _SERPS_PATHS])
def test_warc_query_parsers(request, serps_path: Path) -> None:
    warc_store = MockWarcStore(serps_path)
    verify_yaml(
        request=request,
        data=[
            {
                "serp_id": str(serp.id),
                "memento_url": str(serp.memento_url),
                "actions": list(
                    _iter_clean_actions(
                        parse_serp_warc_query_action(
                            serp=serp,
                            warc_store=warc_store,
                        )
                    )
                ),
            }
            for serp in iter_test_serps(serps_path)
        ],
    )
