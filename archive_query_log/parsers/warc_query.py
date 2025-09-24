from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from re import compile as re_compile
from typing import Iterable, Iterator, Pattern, Sequence
from uuid import uuid5, UUID

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from pydantic import BaseModel
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_QUERY_PARSER
from archive_query_log.orm import (
    Serp,
    InnerParser,
)
from archive_query_log.parsers.utils import clean_text
from archive_query_log.parsers.utils.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now
from archive_query_log.utils.warc import WarcStore


class WarcQueryParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    def is_applicable(self, serp: Serp) -> bool:
        # Check if provider matches.
        if self.provider_id is not None and self.provider_id != serp.provider.id:
            return False

        # Check if URL matches pattern.
        if self.url_pattern is not None and not self.url_pattern.match(
            serp.capture.url.encoded_string()
        ):
            return False
        return True

    @cached_property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_WARC_QUERY_PARSER, self.model_dump_json())

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

    @abstractmethod
    def parse(self, serp: Serp, warc_store: WarcStore) -> str | None: ...


class XpathWarcQueryParser(WarcQueryParser):
    xpath: str

    def parse(self, serp: Serp, warc_store: WarcStore) -> str | None:
        if serp.warc_location is None:
            return None

        with warc_store.read(serp.warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        queries = safe_xpath(tree, self.xpath, str)
        for query in queries:
            query_cleaned = clean_text(
                text=query,
                remove_pattern=self.remove_pattern,
                space_pattern=self.space_pattern,
            )
            if query_cleaned is not None:
                return query_cleaned
        return None


def parse_serp_warc_query_action(
    serp: Serp,
    warc_store: WarcStore,
) -> Iterator[dict]:
    # Re-check if it can be parsed.
    if (
        serp.warc_location is None
        or serp.warc_location.file is None
        or serp.warc_location.offset is None
        or serp.warc_location.length is None
    ):
        return

    # Re-check if parsing is necessary.
    if (
        serp.warc_query_parser is not None
        and serp.warc_query_parser.should_parse is not None
        and not serp.warc_query_parser.should_parse
    ):
        return

    for parser in WARC_QUERY_PARSERS:
        if not parser.is_applicable(serp):
            continue
        warc_query = parser.parse(serp, warc_store)
        if warc_query is None:
            # Parsing was not successful.
            continue
        yield serp.update_action(
            warc_query=warc_query,
            warc_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_query(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location") & ~Term(warc_query_parser__should_parse=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.params(size=size).execute()

        changed_serps = tqdm(
            changed_serps,
            total=num_changed_serps,
            desc="Parsing WARC query",
            unit="SERP",
        )
        actions = chain.from_iterable(
            parse_serp_warc_query_action(serp, config.s3.warc_store)
            for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")


WARC_QUERY_PARSERS: Sequence[WarcQueryParser] = (
    # Provider: Google (google.com)
    XpathWarcQueryParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//form[@id = 'tsf']//input[@name = 'q']/@value | //form[@id = 'sf']//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//form[@name = 'gs']//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//form[@action = '/search']//input[@name = 'q']/@value",
    ),
    # Provider: Google Scholar (scholar.google.com)
    XpathWarcQueryParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/scholar\?"),
        xpath="//input[@id = 'gs_hdr_tsi']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/scholar\?"),
        xpath="//input[@id = 'sbhost']/@value",
    ),
    # Provider: YouTube (youtube.com)
    XpathWarcQueryParser(
        provider_id=UUID("b13b2543-adb4-4c80-92d2-c57ca7e21d76"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        xpath="//input[@id = 'masthead-search-term']/@value",
    ),
    # Provider: Baidu (baidu.com)
    XpathWarcQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//input[@id = 'kw']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/cse/site\?"),
        xpath="//input[@id = 'kw']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//input[@id = 'kw']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/f\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search_form ')]//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' search_ipt ')]/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//form[@action = '/s']//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' i ')]/@value",
    ),
    # Provider: QQ (wechat.com)
    XpathWarcQueryParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/x/search/\?"),
        xpath="//input[@id = 'keywords']/@value",
    ),
    # Provider: Facebook (facebook.com)
    XpathWarcQueryParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//form[@action and contains(@action, 'search')]//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//form//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@id = 'initial_browse_result']//h1//text()",
    ),
    # Provider: Yahoo! (yahoo.com)
    XpathWarcQueryParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//input[@id = 'yschsp']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//form[@action and contains(@action, 'search')]//input[@name = 'p']/@value",
    ),
    # Provider: Amazon (amazon.com)
    XpathWarcQueryParser(
        provider_id=UUID("0508d4c9-9423-4e3b-8e15-267040100ae6"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//input[@id = 'twotabsearchtextbox']/@value",
    ),
    # Provider: JD.com (jd.com)
    XpathWarcQueryParser(
        provider_id=UUID("7158c4f2-b1ae-4862-828d-5f8d46c3269f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'key-re-search']/@value",
    ),
    # Provider: 360 (360.cn)
    XpathWarcQueryParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//input[@id = 'keyword']/@value",
    ),
    # Provider: Weibo (weibo.com)
    XpathWarcQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/weibo/[^/]+"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-input ')]//input[@type = 'text']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/weibo\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-input ')]//input[@type = 'text']/@value",
    ),
    # Provider: Reddit (reddit.com)
    XpathWarcQueryParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//input[@id = 'header-search-bar']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//form[@id = 'search']//input[@name = 'q']/@value",
    ),
    # Provider: Vk.com (vk.com)
    XpathWarcQueryParser(
        provider_id=UUID("fedcc039-b257-4bb4-978e-2a43897e9bce"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'search_query']/@value",
    ),
    # Provider: Microsoft Bing (bing.com)
    XpathWarcQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'sb_form_q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search\?"),
        xpath="//input[@id = 'sb_form_q']/@value",
    ),
    # Provider: Twitter (twitter.com)
    XpathWarcQueryParser(
        provider_id=UUID("1f6b5bbd-e8a0-443b-abb0-1070b4c182e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'q']/@value",
    ),
    # Provider: eBay (ebay.com)
    XpathWarcQueryParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        xpath="//input[@id = 'gh-ac']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        xpath="//input[@id = '_fsb_nkw']/@value",
    ),
    # Provider: Naver (naver.com)
    XpathWarcQueryParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//input[@id = 'nx_query']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//input[@name = 'query']/@value",
    ),
    # Provider: AliExpress (aliexpress.com)
    XpathWarcQueryParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/w/wholesale"),
        xpath="//input[@id = 'search-key']/@value | //input[@id = 'SearchTextIdx']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/wholesale"),
        xpath="//input[@id = 'search-key']/@value | //input[@id = 'SearchTextIdx']/@value",
    ),
    # Provider: Yandex (yandex.ru)
    XpathWarcQueryParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search"),
        xpath="//form[@class and contains(concat(' ', normalize-space(@class), ' '), ' search2 ')]//input[@name = 'text']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search"),
        xpath="//form[@class and contains(concat(' ', normalize-space(@class), ' '), ' search2 ')]//input[@name = 'text']/@value",
    ),
    # Provider: PornHub (pornhub.com)
    XpathWarcQueryParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//input[@id = 'searchInput']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//form[@id = 'search_form']//input[@name = 'search']/@value",
    ),
    # Provider: StackOverflow (stackoverflow.com)
    XpathWarcQueryParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/questions/tagged"),
        xpath="//form[@id = 'search']//input[@name = 'q']/@value",
    ),
    # Provider: IMDb (imdb.com)
    XpathWarcQueryParser(
        provider_id=UUID("24998fe9-f9c7-4245-8647-3ef63e98deef"),
        url_pattern=re_compile(r"^https?://[^/]+/find\?"),
        xpath="//div[@id = 'nb_search']//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24998fe9-f9c7-4245-8647-3ef63e98deef"),
        url_pattern=re_compile(r"^https?://[^/]+/find\?"),
        xpath="//input[@id = 'navbar-query']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24998fe9-f9c7-4245-8647-3ef63e98deef"),
        url_pattern=re_compile(r"^https?://[^/]+/find\?"),
        xpath="//form[@action = '/find']//input[@name = 'q']/@value",
    ),
    # Provider: XVideos (xvideos.com)
    XpathWarcQueryParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//input[@id = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//form[@id = 'xv-search-form']//input[@name = 'k']/@value",
    ),
    # Provider: GitHub (github.com)
    XpathWarcQueryParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//form[@class and contains(concat(' ', normalize-space(@class), ' '), ' js-site-search-form ')]//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' header-search-input ')]/@value",
    ),
    # Provider: Etsy (etsy.com)
    XpathWarcQueryParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'search-query']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@id = 'global-enhancements-search-query']/@value",
    ),
    # Provider: Sogou (sogou.com)
    XpathWarcQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/sogou\?"),
        xpath="//input[@id = 'upquery']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//input[@id = 'upquery']/@value",
    ),
    # Provider: Indeed (indeed.com)
    XpathWarcQueryParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        xpath="//input[@id = 'text-input-what']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        xpath="//input[@id = 'what']/@value",
    ),
    # Provider: Roblox (roblox.com)
    XpathWarcQueryParser(
        provider_id=UUID("22396243-6004-451e-a309-2316926f1e4a"),
        url_pattern=re_compile(r"^https?://[^/]+/(catalog\/browse.aspx\?|discover)"),
        xpath="//input[@id = 'keywordTextbox']/@value",
    ),
    # Provider: Imgur (imgur.com)
    XpathWarcQueryParser(
        provider_id=UUID("792e5262-389c-41d7-b6ce-2189e41e3da2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//span[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-term-text ')]//text()",
    ),
    # Provider: DuckDuckGo (duckduckgo.com)
    XpathWarcQueryParser(
        provider_id=UUID("3725fae7-edf7-4243-bcce-e5ccb615ae76"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[(@class and contains(concat(' ', normalize-space(@class), ' '), ' header__content ')) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' header__search '))]//input[@id = 'search_form_input']/@value",
    ),
    # Provider: Ask.com (ask.com)
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//input[@id = 'js-top-q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//form[@id = 'ft']//input[@id = 'q']/@value | //form[@id = 'ft']//input[@name = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//form[@id = 'lrform']//input[@id = 'q']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchBox-container ')]//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchBox-input ')]/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchBoxRounded-container ')]//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchBoxRounded-input ')]/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@id = 'searchBox']//input[(@id = 'top_q_comm') and (@class and contains(concat(' ', normalize-space(@class), ' '), ' ac_input '))]/@value",
    ),
    # Provider: Wikimedia (wikisource.org)
    XpathWarcQueryParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        xpath="//input[@id = 'searchText']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        xpath="//div[@id = 'searchText']//input/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        xpath="//input[@id = 'sdms-search-input__input']/@value",
    ),
    # Provider: Ecosia (ecosia.org)
    XpathWarcQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-form__input ')]/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-form-input ')]/@value",
    ),
    # Provider: Qwant (qwant.com)
    XpathWarcQueryParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'SearchBar-module')]//input[@type = 'search']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//form[@id = 'headsearchform']//input[@id = 'headsearchbar']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//form[@class and starts-with(@class, 'SearchBar-module')]//input[@type = 'search']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//form[@id = 'search-form']//input[@id = 'search-input']/@value",
    ),
    # Provider: Chefkoch (chefkoch.de)
    XpathWarcQueryParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        xpath="//input[@id = 'inputfield_quicksearch']/@value",
    ),
    XpathWarcQueryParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        xpath="//div[@id = 'schnellsuche']//form[@action and contains(@action, 'suche.php')]//input[@class and contains(concat(' ', normalize-space(@class), ' '), ' input_schnellsuche_text ')]/@value",
    ),
    # Provider: Brave (brave.com)
    XpathWarcQueryParser(
        provider_id=UUID("e3be3140-7f78-4de1-a43b-6c75d345e4c4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//form[@id = 'searchform']//input[@id = 'searchbox']/@value",
    ),
    # Provider: ChatNoir (chatnoir.eu)
    XpathWarcQueryParser(
        provider_id=UUID("e9a0e2d3-390f-4832-9805-40067771b1bf"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//input[@id = 'SearchInput']/@value",
    ),
    # Provider: TripAdvisor (tripadvisor.com)
    XpathWarcQueryParser(
        provider_id=UUID("59dea5e0-eb0d-43d3-b1c1-70c22fbc25e1"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' SEARCH_LHN ')]//form[@id = 'SEARCH_LHN_form']//input[@id = 'mainSearch']/@value",
    ),
)
