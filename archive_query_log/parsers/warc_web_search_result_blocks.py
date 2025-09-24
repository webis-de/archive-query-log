from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from re import compile as re_compile
from typing import Iterable, Iterator, Pattern, Sequence
from urllib.parse import urljoin
from uuid import uuid5, UUID

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from lxml.etree import _Element, tostring  # nosec: B410
from pydantic import HttpUrl, BaseModel
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import (
    NAMESPACE_WARC_WEB_SEARCH_RESULT_BLOCKS_PARSER,
    NAMESPACE_WEB_SEARCH_RESULT_BLOCK,
)
from archive_query_log.orm import (
    Serp,
    InnerParser,
    WebSearchResultBlock,
    InnerSerp,
    WebSearchResultBlockId,
)
from archive_query_log.parsers.utils.warc import open_warc
from archive_query_log.parsers.utils.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now


class WebSearchResultBlockData(BaseModel):
    id: UUID
    rank: int
    content: str
    url: HttpUrl | None = None
    title: str | None = None
    text: str | None = None


class WarcWebSearchResultBlocksParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        return uuid5(
            NAMESPACE_WARC_WEB_SEARCH_RESULT_BLOCKS_PARSER, self.model_dump_json()
        )

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

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

    @abstractmethod
    def parse(
        self, serp: Serp, warc_store: WarcS3Store
    ) -> list[WebSearchResultBlockData] | None: ...


class XpathWarcWebSearchResultBlocksParser(WarcWebSearchResultBlocksParser):
    xpath: str
    url_xpath: str | None = None
    title_xpath: str | None = None
    text_xpath: str | None = None

    def parse(
        self, serp: Serp, warc_store: WarcS3Store
    ) -> list[WebSearchResultBlockData] | None:
        if serp.warc_location is None:
            return None

        with open_warc(warc_store, serp.warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        elements = safe_xpath(tree, self.xpath, _Element)
        if len(elements) == 0:
            return None

        web_search_result_blocks = []
        element: _Element
        for i, element in enumerate(elements):
            url: str | None = None
            if self.url_xpath is not None:
                urls = safe_xpath(element, self.url_xpath, str)
                if len(urls) > 0:
                    url = urls[0].strip()
                    url = urljoin(serp.capture.url.encoded_string(), url)
            title: str | None = None
            if self.title_xpath is not None:
                titles = safe_xpath(element, self.title_xpath, str)
                if len(titles) > 0:
                    title = titles[0].strip()
            text: str | None = None
            if self.text_xpath is not None:
                texts = safe_xpath(element, self.text_xpath, str)
                if len(texts) > 0:
                    text = texts[0].strip()

            content: str = tostring(
                element,
                encoding=str,
                method="xml",
                pretty_print=False,
                with_tail=True,
            )
            web_search_result_block_id_components = (
                str(serp.id),
                str(self.id),
                str(hash(content)),
                str(i),
            )
            web_search_result_block_id = uuid5(
                NAMESPACE_WEB_SEARCH_RESULT_BLOCK,
                ":".join(web_search_result_block_id_components),
            )
            web_search_result_blocks.append(
                WebSearchResultBlockData(
                    id=web_search_result_block_id,
                    rank=i,
                    content=content,
                    url=HttpUrl(url) if url is not None else None,
                    title=title,
                    text=text,
                )
            )
        return web_search_result_blocks


def parse_serp_warc_web_search_result_blocks_action(
    serp: Serp,
    warc_store: WarcS3Store,
    index_web_search_result_blocks: str,
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
        serp.warc_web_search_result_blocks_parser is not None
        and serp.warc_web_search_result_blocks_parser.should_parse is not None
        and not serp.warc_web_search_result_blocks_parser.should_parse
    ):
        return

    for parser in WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS:
        if not parser.is_applicable(serp):
            continue
        warc_web_search_result_blocks = parser.parse(serp, warc_store)
        if warc_web_search_result_blocks is None:
            # Parsing was not successful.
            continue
        for web_search_result_block in warc_web_search_result_blocks:
            web_search_result_block = WebSearchResultBlock(
                id=web_search_result_block.id,
                last_modified=utc_now(),
                archive=serp.archive,
                provider=serp.provider,
                serp_capture=serp.capture,
                serp=InnerSerp(
                    id=serp.id,
                ),
                rank=web_search_result_block.rank,
                content=web_search_result_block.content,
                url=web_search_result_block.url,
                title=web_search_result_block.title,
                text=web_search_result_block.text,
                parser=InnerParser(
                    id=parser.id,
                    should_parse=False,
                    last_parsed=utc_now(),
                ),
            )
            web_search_result_block.meta.index = index_web_search_result_blocks
            yield web_search_result_block.create_action()
        yield serp.update_action(
            warc_web_search_result_blocks=[
                WebSearchResultBlockId(
                    id=web_search_result_block.id,
                    rank=web_search_result_block.rank,
                )
                for web_search_result_block in warc_web_search_result_blocks
            ],
            warc_web_search_result_blocks_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_web_search_result_blocks_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_web_search_result_blocks(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(warc_web_search_result_blocks_parser__should_parse=False)
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
            desc="Parsing WARC web search result blocks",
            unit="SERP",
        )
        actions = chain.from_iterable(
            parse_serp_warc_web_search_result_blocks_action(
                serp,
                config.s3.warc_store,
                config.es.index_web_search_result_blocks,
            )
            for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")


WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS: Sequence[WarcWebSearchResultBlocksParser] = (
    # Provider: Google (google.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'search']//div[@id = 'rso']//div[(@class and contains(concat(' ', normalize-space(@class), ' '), ' g ')) and (not(@class and contains(concat(' ', normalize-space(@class), ' '), ' g-blk ')))] | //div[@id = 'search']//div[@id = 'ires']//div[(@class and contains(concat(' ', normalize-space(@class), ' '), ' g ')) and (not(@class and contains(concat(' ', normalize-space(@class), ' '), ' g-blk ')))] | //div[@id = 'search']//ol[@id = 'rso']//li[(@class and contains(concat(' ', normalize-space(@class), ' '), ' g ')) and (not(@class and contains(concat(' ', normalize-space(@class), ' '), ' g-blk ')))]",
        url_xpath="*[@class and contains(concat(' ', normalize-space(@class), ' '), ' r ')]//a/@href | *[@class and contains(concat(' ', normalize-space(@class), ' '), ' rc ')]//a/@href | h3//a/@href | a/@href",
        title_xpath="*[@class and contains(concat(' ', normalize-space(@class), ' '), ' r ')]//a//h3//text() | *[@class and contains(concat(' ', normalize-space(@class), ' '), ' rc ')]//a//h3//text() | h3//text() | a//h3//text()",
        text_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' st ')]//text() | span//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'main']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' xpd ')]",
        url_xpath="a/@href",
        title_xpath="a//h3//text()",
        text_xpath="div//div//div//div//div//div//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'gs_res_ccl_mid']/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' gs_r ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' gs_rt ')]//a/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' gs_rt ')]//text()",
        text_xpath="dic[@class and contains(concat(' ', normalize-space(@class), ' '), ' gs_rs ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'search']//div[@id = 'ires']//table[@class and contains(concat(' ', normalize-space(@class), ' '), ' images_table ')]//tr//td",
        url_xpath="a/@href",
        title_xpath=".//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' g ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' r ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' l ')]/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' r ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//p[@class = 'g']",
        url_xpath="a/@href",
        title_xpath="a//text()",
    ),
    # Provider: YouTube (youtube.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("b13b2543-adb4-4c80-92d2-c57ca7e21d76"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        xpath="//div[(@id = 'page') and (@class and contains(concat(' ', normalize-space(@class), ' '), ' search '))]//div[@id = 'results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' yt-lockup ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' yt-lockup-title ')]//a/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' yt-lockup-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' yt-lockup-description ')]//text()",
    ),
    # Provider: Baidu (baidu.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//div[@id = 'content_left']/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')] | //div[@id = 'content_left']/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-op ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' t ')]/a/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' t ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' c-abstract ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/f\?"),
        xpath="//ul[@id = 'thread_list']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' j_thread_list ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' threadlist_title ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' threadlist_title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' threadlist_text ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//table//tr//td[@class and contains(concat(' ', normalize-space(@class), ' '), ' f ')]",
        url_xpath="a[not(@class and contains(concat(' ', normalize-space(@class), ' '), ' m '))]/@href",
        title_xpath="a[not(@class and contains(concat(' ', normalize-space(@class), ' '), ' m '))]//text()",
    ),
    # Provider: QQ (wechat.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        xpath="//div[@id = 'search_container']/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' wrapper ')]/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' wrapper_main ')]/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_item ')]",
        url_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_title ')]/a/@href",
        title_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/x/search/\?"),
        xpath="//div[@id = 'search_container']/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' wrapper ')]/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' wrapper_main ')]/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_item ')]",
        url_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_title ')]/a/@href",
        title_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_title ')]//text()",
    ),
    # Provider: Facebook (facebook.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search.php\?"),
        xpath="//div[@id = 'pagelet_search_results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detailedsearch_result ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' instant_search_title ')]/a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' instant_search_title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' fsm ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@id = 'all_search_results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' _gli ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' _gll ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' _gll ')]//a//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search_result ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search_title ')]/a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search_title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' fsm ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' uiList ')]/li",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' TextTitle ')]/a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' TextTitle ')]//text()",
    ),
    # Provider: Yahoo! (yahoo.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//div[@id = 'results']//div[@id = 'main']//div[@id = 'web']//ol//li//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' res ')]",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' abstr ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//div[@id = 'web']//ol//li//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' algo ')] | //div[@id = 'web']//ol//li//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' algo-sr ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' aAbs ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' content ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' nomod ')]//ol//li",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//table//tr//td//font//ol//li",
        url_xpath="big//a/@href",
        title_xpath="big//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//dl//dd//li",
        url_xpath="a/@href",
        title_xpath="a//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/?\?"),
        xpath="//ul[@type = 'disc']//li",
        url_xpath="a/@href",
        title_xpath="a//text()",
    ),
    # Provider: Amazon (amazon.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("0508d4c9-9423-4e3b-8e15-267040100ae6"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//div[@id = 'search']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-result-list ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-result-item ')]",
        url_xpath="h2//a/@href",
        title_xpath="h2//text()",
    ),
    # Provider: JD.com (jd.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("7158c4f2-b1ae-4862-828d-5f8d46c3269f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'J_goodsList']//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' gl-warp ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' gl-item ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' p-name ')]/a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' p-name ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("7158c4f2-b1ae-4862-828d-5f8d46c3269f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[(@id = 'plist') and (@class and contains(concat(' ', normalize-space(@class), ' '), ' psearch '))]//ul//li[@sku] | //div[(@id = 'plist') and (@class and contains(concat(' ', normalize-space(@class), ' '), ' psearch '))]//ul//li[@bookid]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' p-name ')]/a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' p-name ')]//text()",
    ),
    # Provider: 360 (360.cn)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//div[@id = 'main']//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-list ')]",
        url_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-title ')]//a/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-desc ')]//text() | p[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-desc ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        xpath="//div[@id = 'main']//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-list ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-cont ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-title-link ')]/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-cont ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-title-link ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-cont ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-abstract ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-content-box ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-content-desc ')]//span[@class and contains(concat(' ', normalize-space(@class), ' '), ' mh-content-desc-info ')]//text()",
    ),
    # Provider: Reddit (reddit.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@data-testid = 'posts-list']//div[@data-testid = 'post-container']",
        url_xpath="div[@data-adclicklocation = 'title']//a/@href",
        title_xpath="div[@data-testid = 'post-title']//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@id = 'siteTable']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' thing ')] | //div[@id = 'siteTable']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' link ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]/@href",
        title_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result-group ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-title ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result-body ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        xpath="//div[@id = 'AppRouter-main-content']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' Post ')]",
        url_xpath="a[@data-testid = 'post_timestamp']/@href",
        title_xpath="a//h3//text()",
    ),
    # Provider: Vk.com (vk.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("fedcc039-b257-4bb4-978e-2a43897e9bce"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//table[@id = 'search_table']//td[@id = 'results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' people_row ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' name ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' name ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-desc ')]//text() | p[@class and contains(concat(' ', normalize-space(@class), ' '), ' res-desc ')]//text()",
    ),
    # Provider: Microsoft Bing (bing.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//ol[@id = 'b_results']/li[@class and contains(concat(' ', normalize-space(@class), ' '), ' b_algo ')]",
        url_xpath="h2/a/@href",
        title_xpath="h2//text()",
        text_xpath="p//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'results']//ul//li",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sb_tlst ')]//h3//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sb_tlst ')]//h3//text()",
        text_xpath="p//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search\?"),
        xpath="//div[@id = 'mmComponent_images_2']//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' dgControl_list ')]//li//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' isv ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' imgpt ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' img_info ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' lnkw ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' infopt ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' infnmpt ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' infpd ')]//a//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search\?"),
        xpath="//div[@id = 'main']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' content ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' item ')] | //span[@id = 'main']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' content ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' item ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' tit ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' tit ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' des ')]//text()",
    ),
    # Provider: Twitter (twitter.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("1f6b5bbd-e8a0-443b-abb0-1070b4c182e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//ol[@id = 'stream-items-id']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' stream-item ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' tweet-timestamp ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' account-group ')]//text()",
        text_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' tweet-text ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("1f6b5bbd-e8a0-443b-abb0-1070b4c182e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' searches ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' timeline ')]//table[@class and contains(concat(' ', normalize-space(@class), ' '), ' tweet ')]",
        url_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' timestamp ')]//a/@href",
        title_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' user-info ')]//text()",
        text_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' tweet-content ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' tweet-text ')]//text()",
    ),
    # Provider: eBay (ebay.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        xpath="//div[@id = 'ResultSetItems']//ul[@id = 'GalleryViewInner']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' sresult ')]",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' srp-results ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-item ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-item__link ')]/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-item__title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' rs ')]//table[@class and contains(concat(' ', normalize-space(@class), ' '), ' rsittlref ')]//tr",
        url_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' dtl ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' ittl ')]//a/@href",
        title_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' dtl ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sttl ')]//text()",
    ),
    # Provider: Naver (naver.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' lst_total ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' bx ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' total_tit ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' total_tit ')]//text()",
        text_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' total_dsc ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' webdoc ')]//ul//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_web_top ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_web_title ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_web_title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_web_passage ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' blog ')]//ul//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_blog_top ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_blog_title ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_blog_title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sh_blog_passage ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        xpath="//body//small//ul//table",
        url_xpath="tr[@valign = 'top']//td//table//tr//td//small//a/@href",
        title_xpath="tr[@valign = 'top']//td//table//tr//td//small//a//text()",
    ),
    # Provider: AliExpress (aliexpress.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/w/wholesale"),
        xpath="//div[@id = 'hs-list-items']//ul//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')] | //ul[@id = 'hs-list-items']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')] | //ul[@id = 'list-items']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' info ')]//h3//a/@href | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//h3//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' info ')]//h3//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//span[@class and contains(concat(' ', normalize-space(@class), ' '), ' brief ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/wholesale"),
        xpath="//div[@id = 'hs-list-items']//ul//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')] | //ul[@id = 'hs-list-items']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')] | //ul[@id = 'list-items']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' list-item ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' info ')]//h3//a/@href | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//h3//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' info ')]//h3//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' detail ')]//span[@class and contains(concat(' ', normalize-space(@class), ' '), ' brief ')]//text()",
    ),
    # Provider: BongaCams (bongacams.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("936ddb10-649f-4757-b761-3205506725c7"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(female|male|couples|trans|new-models)/tags/[^/]+"
        ),
        xpath="//div[@id = 'mls_container']//div[@id = 'mls_models']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mls_models ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' ls_thumb ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' lst_info ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' lst_info ')]//a//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' lst_topic ')]//text()",
    ),
    # Provider: PornHub (pornhub.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//ul[@id = 'videoSearchResult']//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' videoblock ')]",
        url_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' nf-videos ')]//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' videos ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' videoblock ')] | //ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' nf-videos ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' videoblock ')]",
        url_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href | h5[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text() | h5[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' video_box ')]",
        url_xpath="a/@href",
        title_xpath="a//span[@class and contains(concat(' ', normalize-space(@class), ' '), ' small ')]//text()",
    ),
    # Provider: StackOverflow (stackoverflow.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/questions/tagged"),
        xpath="//div[@id = 'questions']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-post-summary--content ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-link ')]/@href",
        title_xpath="h3[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-post-summary--content-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-post-summary--content-excerpt ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/questions/tagged"),
        xpath="//div[@id = 'questions']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' summary ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' question-hyperlink ')]/@href",
        title_xpath="h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' excerpt ')]//text()",
    ),
    # Provider: IMDb (imdb.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("24998fe9-f9c7-4245-8647-3ef63e98deef"),
        url_pattern=re_compile(r"^https?://[^/]+/find\?"),
        xpath="//table[@class and contains(concat(' ', normalize-space(@class), ' '), ' findList ')]//tr[@class and contains(concat(' ', normalize-space(@class), ' '), ' findResult ')]",
        url_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_text ')]//a/@href",
        title_xpath="td[@class and contains(concat(' ', normalize-space(@class), ' '), ' result_text ')]//a//text()",
    ),
    # Provider: XVideos (xvideos.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@id = 'content']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' thumb-block ')]",
        url_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@id = 'content']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' thumbBlock ')]",
        url_xpath="p//a/@href",
        title_xpath="p//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//body[@id = 'home']//div//table//tr//td//div//table[@bgcolor = '#EEEDF1']//tr//td",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' miniature ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' miniature ')]//span//text()",
    ),
    # Provider: GitHub (github.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' repo-list ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' repo-list-item ')]",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
        text_xpath="p[(@class and contains(concat(' ', normalize-space(@class), ' '), ' d-inline-block ')) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' text-gray '))]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' repo-list ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' repo-list-item ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' flex-auto ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' d-flex ')]//a/@href | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mt-n1 ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' text-normal ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' flex-auto ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' d-flex ')]//a//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mt-n1 ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' text-normal ')]//a//text()",
        text_xpath="p[@class]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'package_search_results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' hx_hit-package ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' h4 ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' h4 ')]//text()",
        text_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' mb-1 ')]//text()",
    ),
    # Provider: Etsy (etsy.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' listings ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-card ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-title ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-title ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-listings-group ')]//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' responsive-listing-grid ')]//li",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-link ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-link ')]//h2//text() | a[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-link ')]//h3//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@data-search-results]//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' wt-grid ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' wt-list-unstyled ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-link ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' listing-link ')]//h3//text()",
    ),
    # Provider: Sogou (sogou.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/sogou\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' rb ')] | //div[@class and contains(concat(' ', normalize-space(@class), ' '), ' results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' vrwrap ')]",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' ft ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' strBox ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' str_info ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' fz-mid ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' rb ')] | //div[@class and contains(concat(' ', normalize-space(@class), ' '), ' results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' vrwrap ')]",
        url_xpath="h3//a/@href",
        title_xpath="h3//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' ft ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' strBox ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' str_info ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' fz-mid ')]//text()",
    ),
    # Provider: Indeed (indeed.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        xpath="//td[@id = 'resultsCol']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')] | //td[@id = 'resultsCol']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' row ')]",
        url_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' jobtitle ')]//a/@href",
        title_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' jobtitle ')]//text()",
        text_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' summary ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        xpath="//td[@id = 'resultsCol']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' summary ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        xpath="//div[@id = 'mosaic-zone-jobcards']//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]",
        url_xpath="./@href",
        title_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' jobTitle ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' job-snippet ')]//text()",
    ),
    # Provider: Roblox (roblox.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("22396243-6004-451e-a309-2316926f1e4a"),
        url_pattern=re_compile(r"^https?://[^/]+/(catalog\/browse.aspx\?|discover)"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' CatalogItemOuter ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' CatalogItemName ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' name ')]/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' CatalogItemName ')]//text()",
    ),
    # Provider: DuckDuckGo (duckduckgo.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("3725fae7-edf7-4243-bcce-e5ccb615ae76"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@id = 'links']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__body ')]//h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__title ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__a ')]/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__body ')]//h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__title ')]//text()",
    ),
    # Provider: Ask.com (ask.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' l-web-results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_headline ')]/@href | h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-title ')]//a/@href | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-title ')]//a/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_headline ')]//text() | h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-title ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_abstract ')]//text() | p[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-description ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result-description ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@id = 'teoma-results']//div[((@class and contains(concat(' ', normalize-space(@class), ' '), ' pad ')) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' pl10 '))) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' pr10 '))] | //div[@id = 'webr']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mb16 ')] | //div[@id = 'webr']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' m10_0_16 ')]",
        url_xpath="div[@id and starts-with(@id, 'r_t')]//a/@href",
        title_xpath="div[@id and starts-with(@id, 'r_t')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' T1 ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchResults-results ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchResults-item ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchResults-item-title ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchResults-item-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' PartialSearchResults-item-details ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        xpath="//div[@id = 'teoma-results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' wresult ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_headline_block ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_headline_block ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' sa_content_block ')]//text()",
    ),
    # Provider: Wikimedia (wikisource.org)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' mw-search-results ')]//li",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mw-search-result-heading ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mw-search-result-heading ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' searchresult ')]//text()",
    ),
    # Provider: Ecosia (ecosia.org)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//section[@class and contains(concat(' ', normalize-space(@class), ' '), ' mainline ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' mainline__result-wrapper ')]//article[(@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')) and (not(@class and contains(concat(' ', normalize-space(@class), ' '), ' ad-result ')))]",
        url_xpath="header[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title ')]//h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title__heading ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title__link ')]/@href | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__header ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__title ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__link ')]/@href",
        title_xpath="header[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title ')]//h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title__heading ')]//text() | div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__header ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__columns ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result__description ')]//p[@class and contains(concat(' ', normalize-space(@class), ' '), ' web-result__description ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//main[@class and contains(concat(' ', normalize-space(@class), ' '), ' results-wrapper ')]//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]",
        url_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-firstline-title ')]//a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-title ')]/@href",
        title_xpath="h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-firstline-title ')]//text()",
        text_xpath="p[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-snippet ')]//text()",
    ),
    # Provider: Qwant (qwant.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'Stack-module')]//div[@class and starts-with(@class, 'WebResult-module__container')]",
        url_xpath="div[@class and starts-with(@class, 'WebResult-module__subContainer')]//a/@href",
        title_xpath="div[@class and starts-with(@class, 'WebResult-module__subContainer')]//a//h2[@class and starts-with(@class, 'Text-module')]//text() | div[@class and starts-with(@class, 'WebResult-module__subContainer')]//a[@class and starts-with(@class, 'external Text-module__typo')]//text()",
        text_xpath="div[@class and starts-with(@class, 'Text-module')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'SER-module__subContainer')]//div[@class and starts-with(@class, 'Stack-module__VerticalStack')]//div[@class and contains(@class, 'HeaderContainer')]",
        url_xpath="div[@class and starts-with(@class, 'Stack-module__VerticalStack')]//a/@href",
        title_xpath="div[@class and starts-with(@class, 'Stack-module__VerticalStack')]//text()",
        text_xpath="div[@class and starts-with(@class, 'Text-module')]//span//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'SER-module__subContainer')]",
        url_xpath="a[@class and contains(@class, 'SER-module__title')]/@href",
        title_xpath="a[@class and contains(@class, 'SER-module__title')]//text()",
        text_xpath="p[@class and contains(@class, 'SER-module__description')]//text() | div[@class and contains(@class, 'SER-module__description')]//text() | div[@class and contains(@class, 'SER-module__domain')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'SER-module__subContainer')]",
        url_xpath="a/@href",
        title_xpath="a//text()",
        text_xpath="div[@class and starts-with(@class, 'Text')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@id = 'contenerresults']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' result ')]",
        url_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//a/@href",
        title_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' title ')]//text()",
        text_xpath="p[not(@class and contains(concat(' ', normalize-space(@class), ' '), ' url '))]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        xpath="//div[@class and starts-with(@class, 'Videos-module__VideosList')]//a[@data-testid = 'videoResult']",
        url_xpath="./@href",
        title_xpath="div[@class and contains(@class, 'VideoCardTitle')]//text()",
        text_xpath="div[@class and contains(@class, 'VideoCardDescription')]//text()",
    ),
    # Provider: Chefkoch (chefkoch.de)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        xpath="//ul[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list ')]//li[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item ')]",
        url_xpath="a[./div][@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item-content ')]/@href",
        title_xpath="a/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item-content ')]/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item-title ')]//text()",
        text_xpath="a/div[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item-content ')]/p[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-list-item-subtitle ')]//text()",
    ),
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        xpath="//table[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result-table ')]//tr[@class and contains(concat(' ', normalize-space(@class), ' '), ' rowclick ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result-title ')]/@href",
        title_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result-title ')]//text()",
    ),
    # Provider: Brave (brave.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("e3be3140-7f78-4de1-a43b-6c75d345e4c4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath="//div[@id = 'results']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' snippet ')]",
        url_xpath="a[@class and contains(concat(' ', normalize-space(@class), ' '), ' result-header ')]/@href",
        title_xpath="span[@class and contains(concat(' ', normalize-space(@class), ' '), ' snippet-title ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' snippet-content ')]//text() | p[@class and contains(concat(' ', normalize-space(@class), ' '), ' snippet-description ')]//text() | div[(@class and contains(concat(' ', normalize-space(@class), ' '), ' text-sm ')) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' text-gray '))]//text() | div[(@class and contains(concat(' ', normalize-space(@class), ' '), ' description ')) and (@class and contains(concat(' ', normalize-space(@class), ' '), ' text-sm '))]//text()",
    ),
    # Provider: ChatNoir (chatnoir.eu)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("e9a0e2d3-390f-4832-9805-40067771b1bf"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        xpath="//section[@id = 'SearchResults']//article[@class and contains(concat(' ', normalize-space(@class), ' '), ' search-result ')]",
        url_xpath="h2//a/@href",
        title_xpath="h2//text()",
    ),
    # Provider: TripAdvisor (tripadvisor.com)
    XpathWarcWebSearchResultBlocksParser(
        provider_id=UUID("59dea5e0-eb0d-43d3-b1c1-70c22fbc25e1"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\?"),
        xpath="//div[@id = 'SEARCH_RESULTS']//div[@class and contains(concat(' ', normalize-space(@class), ' '), ' searchResult ')]",
        url_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' srHead ')]//a/@href",
        title_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' srHead ')]//text()",
        text_xpath="div[@class and contains(concat(' ', normalize-space(@class), ' '), ' srSnippet ')]//text()",
    ),
)
