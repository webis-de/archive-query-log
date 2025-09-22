from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from re import compile as re_compile
from typing import Iterable, Iterator, Pattern, Sequence
from uuid import uuid5, UUID

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature
from pydantic import BaseModel
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_PAGE_PARSER
from archive_query_log.orm import Serp, InnerParser
from archive_query_log.parsers.utils import clean_int
from archive_query_log.parsers.utils.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.utils.time import utc_now


class UrlPageParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_URL_PAGE_PARSER, self.model_dump_json())

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
    def parse(self, serp: Serp) -> int | None: ...


class QueryParameterUrlPageParser(UrlPageParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_query_parameter(self.parameter, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


class FragmentParameterUrlPageParser(UrlPageParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_fragment_parameter(self.parameter, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


class PathSegmentUrlPageParser(UrlPageParser):
    segment: int

    def parse(self, serp: Serp) -> int | None:
        page_string = parse_url_path_segment(self.segment, serp.capture.url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=self.remove_pattern,
        )


def _parse_serp_url_page_action(serp: Serp) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        serp.url_page_parser is not None
        and serp.url_page_parser.should_parse is not None
        and not serp.url_page_parser.should_parse
    ):
        return

    for parser in URL_PAGE_PARSERS:
        if not parser.is_applicable(serp):
            continue
        url_page = parser.parse(serp)
        if url_page is None:
            # Parsing was not successful.
            continue
        yield serp.update_action(
            url_page=url_page,
            url_page_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        url_page_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_page(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(~Term(url_page_parser__should_parse=False))
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
            changed_serps, total=num_changed_serps, desc="Parsing URL page", unit="SERP"
        )
        actions = chain.from_iterable(
            _parse_serp_url_page_action(serp) for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")


URL_PAGE_PARSERS: Sequence[UrlPageParser] = (
    # Provider: QQ (wechat.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.htm\?"),
        parameter="page",
    ),
    # Provider: Amazon (amazon.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("0508d4c9-9423-4e3b-8e15-267040100ae6"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="page",
    ),
    # Provider: JD.com (jd.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7158c4f2-b1ae-4862-828d-5f8d46c3269f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: 360 (360.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="pn",
    ),
    # Provider: Microsoft Bing (bing.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/shop\?"),
        parameter="page",
    ),
    # Provider: eBay (ebay.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        parameter="_pgn",
    ),
    # Provider: AliExpress (aliexpress.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/w/wholesale"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/wholesale"),
        parameter="page",
    ),
    # Provider: Yandex (yandex.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="p",
    ),
    # Provider: LinkedIn (linkedin.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("962ab074-1a32-4fed-a6b4-8db693cd1a23"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Apple (apple.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4a0ba050-7e6f-4e6a-b50e-f3e378512f39"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: PornHub (pornhub.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        parameter="page",
    ),
    # Provider: StackOverflow (stackoverflow.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/questions/tagged"),
        parameter="page",
    ),
    # Provider: TribunNews (tribunnews.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("88e85822-b891-41d4-93dc-da45db4af885"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.page",
    ),
    # Provider: Chaturbate (chaturbate.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e0fa9954-ddac-4afb-9183-9766f993b01a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    # Provider: XVideos (xvideos.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="p",
    ),
    # Provider: GitHub (github.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: CNN (cnn.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c3e70d8e-b2e7-4b14-9104-374cd03185d2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Etsy (etsy.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: xHamster (xhamster.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7b739c60-648a-452f-a9ce-7c50a237a25f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+page"),
        parameter="page",
    ),
    # Provider: Sogou (sogou.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/result\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/sogou\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/weixin\?"),
        parameter="page",
    ),
    # Provider: Instructure (instructure.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ad67b828-d658-4109-833e-8614728b5936"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Flipkart (flipkart.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("35c5c1ae-aca4-41dc-87e4-17956a50afdb"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Fandom (fandom.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("f946b946-88aa-4aa9-a7e9-3bd1ab43e897"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+\?"),
        segment=2,
    ),
    # Provider: BBC (bbc.co.uk)
    QueryParameterUrlPageParser(
        provider_id=UUID("40227760-efc6-4290-a7eb-fd1e2dba500f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: detikcom (detik.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("060ad729-c126-4cdd-bb41-810f747aba86"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: cnblogs (cnblogs.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/blogpost\?"),
        parameter="pageindex",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/kb\?"),
        parameter="pageindex",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/news\?"),
        parameter="pageindex",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/question\?"),
        parameter="pageindex",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="pageindex",
    ),
    # Provider: Walmart (walmart.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("53146b84-b82b-4b36-960e-d95cc73863b5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Alibaba (alibaba.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("38a0c350-e40b-4bde-b0ca-2760c49247bb"),
        url_pattern=re_compile(r"^https?://[^/]+/trade/search\?"),
        parameter="page",
    ),
    # Provider: Freepik (freepik.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("bd284b5c-ca5c-4614-af84-e0f74b069726"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: National Institutes of Health (nih.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("e0421c49-101f-4e66-8318-b47ae737189b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Stack Exchange (stackexchange.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a5be09d9-0e19-4a2d-80ce-b8d78f768465"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Daum (daum.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("10b57fbe-76cc-402f-b7ca-308b8cf3d300"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Udemy (udemy.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("72941c35-661e-40de-8a6b-0a5eb1ee1b90"),
        url_pattern=re_compile(r"^https?://[^/]+/courses/.*search\-query"),
        parameter="p",
    ),
    # Provider: Avito (avito.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("49405df5-bac8-4d07-af32-e336aa82d6f3"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+\?"),
        parameter="p",
    ),
    # Provider: Alibaba Cloud (aliyun.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a1325524-1903-42e5-886a-721e244c5280"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: W3Schools (w3schools.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5802cad3-1a6f-46a8-b646-0cd8b49c4db5"),
        url_pattern=re_compile(r"^https?://[^/]+/.*#gsc"),
        parameter="gsc.page",
    ),
    # Provider: Tokopedia (tokopedia.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b6ff76de-e4b8-4a75-b3a2-dd9a522e6969"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Youm7 (youm7.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("abc4dab5-7c5e-4f4b-bd3c-062c0f444281"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: SlideShare (slideshare.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("248a5485-79e6-46c7-882c-708fbd7f3d55"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: China Internet Information Center (china.com.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("e904cce7-7ded-45fb-a614-db254cca9262"),
        url_pattern=re_compile(r"^https?://[^/]+/news/query"),
        parameter="startPage",
    ),
    # Provider: Bukalapak (bukalapak.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("6210e971-e05d-4195-b5ce-e83e7fb9c92c"),
        url_pattern=re_compile(r"^https?://[^/]+/products/"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("6210e971-e05d-4195-b5ce-e83e7fb9c92c"),
        url_pattern=re_compile(r"^https?://[^/]+/products\?"),
        parameter="page",
    ),
    # Provider: Ask.com (ask.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        parameter="page",
    ),
    # Provider: US Postal Service (usps.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("f85d9c64-e72a-4871-a8fd-73b9d5acd0d5"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="PNO",
    ),
    # Provider: Rambler (rambler.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("5498178c-319e-4ccd-af98-e4c61476bea7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Chegg (chegg.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d5c2ded0-1a93-4ad2-9c9b-dcdaf1491a1d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: Kakao (kakao.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("affade1b-1e35-40b8-8fb8-0ff133250713"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[^/]+"),
        segment=3,
        remove_pattern=re_compile(r"page:"),
    ),
    # Provider: Naukri.com (naukri.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("2bc57145-7373-42fa-9268-b6cff3e22a92"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+-jobs-[0-9]+\?"),
        segment=1,
        remove_pattern=re_compile(r"^[^/]+-jobs-"),
    ),
    # Provider: SourceForge (sourceforge.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("f2693944-32e9-4976-973e-23947f56d10a"),
        url_pattern=re_compile(r"^https?://[^/]+/(directory|software)"),
        parameter="page",
    ),
    # Provider: WebMD (webmd.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b9df840d-7f5f-4ed1-9619-b68bd7540e5f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search_results"),
        parameter="page",
    ),
    # Provider: Ecosia (ecosia.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/news\?"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/videos\?"),
        parameter="p",
    ),
    # Provider: DC Inside (dcinside.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("a4f676fa-4b8a-48c6-9879-45e95c75c283"),
        url_pattern=re_compile(r"^https?://[^/]+/post/p/[^/]+/sort/[^/]+/q/[^/]+"),
        segment=3,
    ),
    # Provider: GOV.UK (gov.gov.uk)
    QueryParameterUrlPageParser(
        provider_id=UUID("0cc990e6-376f-45cb-be16-4f6ade723e76"),
        url_pattern=re_compile(r"^https?://[^/]+/search/all\?"),
        parameter="page",
    ),
    # Provider: El Fagr (elfagr.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("a5e294b8-3a84-4662-8318-9983be7e2c54"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Bandcamp (bandcamp.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ce34adf9-ab2f-4715-9823-3afd19d34eaa"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: 123RF (123rf.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c3184333-c73d-442f-9d7f-5f0968e82fcb"),
        url_pattern=re_compile(r"^https?://[^/]+/stock-photo/[^/]\.html\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("c3184333-c73d-442f-9d7f-5f0968e82fcb"),
        url_pattern=re_compile(r"^https?://[^/]+/lizenzfreie-bilder/[^/]\.html\?"),
        parameter="page",
    ),
    # Provider: FiveThirtyEight (fivethirtyeight.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("be396697-ee09-4c67-bf41-4430acb70575"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: TD Ameritrade (tdameritrade.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("40dead1b-05ca-4a38-ac51-88392f851a40"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results\.html\?"),
        parameter="pageNumber",
    ),
    # Provider: SFGATE (sfgate.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9eda3ef4-dd23-440c-935a-7061be9f8b5c"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Gobierno de México (gob.mx)
    QueryParameterUrlPageParser(
        provider_id=UUID("7bd87442-ae0a-4896-8b2b-4c387c6d5e5c"),
        url_pattern=re_compile(r"^https?://[^/]+/busqueda\?"),
        parameter="gsc.page",
    ),
    # Provider: VectorStock (vectorstock.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("7f787607-7271-49ad-bc8a-21af5ed922e8"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(royalty-free-vectors|free-vectors)/[^/]+-vectors-page_[0-9]+"
        ),
        segment=2,
        remove_pattern=re_compile(r"^[^/]+-vectors-page_"),
    ),
    # Provider: FMovies (fmovies.wtf)
    QueryParameterUrlPageParser(
        provider_id=UUID("d639b0d6-181d-449f-98e2-9d64d823f076"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d639b0d6-181d-449f-98e2-9d64d823f076"),
        url_pattern=re_compile(r"^https?://[^/]+/ajax/film/search\?"),
        parameter="page",
    ),
    # Provider: BigGo (biggo.com.tw)
    QueryParameterUrlPageParser(
        provider_id=UUID("e4cdad56-71d6-4887-8aeb-4ebd004e23e0"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="p",
    ),
    # Provider: Sage Publications (sagepub.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a1e98542-11e3-4a4f-8eae-4067dbba2e65"),
        url_pattern=re_compile(
            r"^https?://[^/]+/[a-z]+-[a-z]+/[a-z]+/(content|events|product)/[^/]+"
        ),
        parameter="page",
    ),
    # Provider: Tasnim News (tasnimnews.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("43f49c54-7325-44a6-94e6-064ba6650506"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/search\?"),
        parameter="page",
    ),
    # Provider: CyberLeninka (cyberleninka.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("bafe8c81-483c-4155-9abe-0dca1990429d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Semantic Scholar (semanticscholar.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("1053663b-2f2a-4df6-aa54-2af7f69b0747"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: NSW Government (nsw.gov.au)
    QueryParameterUrlPageParser(
        provider_id=UUID("5ce5e859-95ec-4f7b-b5de-fcc2ab4f099e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Got Porn (gotporn.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("f0e0f967-ba27-458e-8841-c420c5903ae2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("f0e0f967-ba27-458e-8841-c420c5903ae2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: Pennsylvania State University (psu.edu)
    QueryParameterUrlPageParser(
        provider_id=UUID("56bcd5fe-4f51-4c3f-a5e2-edb7dd159659"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="gsc.page",
    ),
    # Provider: Prensa Libre (prensalibre.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("1863e6b9-c89f-489d-a28e-44eaa8bcabe0"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Worldstarhiphop (worldstarhiphop.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("630a2ad0-43ec-44fa-9897-cb91388bdb64"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/search\.php"),
        parameter="start",
    ),
    # Provider: SAPO (sapo.pt)
    QueryParameterUrlPageParser(
        provider_id=UUID("be2ffd65-ef03-45ed-8618-c4ae06f39035"),
        url_pattern=re_compile(r"^https?://[^/]+/pesquisa"),
        parameter="gsc.page",
    ),
    # Provider: Digital Photography Review (dpreview.com)
    FragmentParameterUrlPageParser(
        provider_id=UUID("04c33826-d8f2-453f-b272-216004cf7221"),
        url_pattern=re_compile(r"^https?://[^/]+/products/search/"),
        parameter="page",
    ),
    # Provider: TnaFilx (tnaflix.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c092b9b8-70ac-4158-ba8c-2943a7364fc8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="page",
    ),
    # Provider: Excite (excite.co.jp)
    QueryParameterUrlPageParser(
        provider_id=UUID("3721d489-4632-416e-9c68-a522e86a8806"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("3721d489-4632-416e-9c68-a522e86a8806"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="page",
    ),
    # Provider: AniWave (9anime.gs)
    QueryParameterUrlPageParser(
        provider_id=UUID("3b594398-ba2d-444a-bbb2-a0d931ae0c9a"),
        url_pattern=re_compile(r"^https?://[^/]+/filter\?"),
        parameter="page",
    ),
    # Provider: Books.com.tw (books.com.tw)
    PathSegmentUrlPageParser(
        provider_id=UUID("b3f58a77-6b8f-48d0-9468-c9f7d6b6c4f8"),
        url_pattern=re_compile(
            r"^https?://[^/]+/search/[^/]+/cat/[^/]+/sort/[^/]+/[^/]+/[^/]+/ovs/[^/]+/spell/[^/]+/[^/]+/[^/]+/page/[0-9]+"
        ),
        segment=16,
    ),
    # Provider: Le360 (le360.ma)
    QueryParameterUrlPageParser(
        provider_id=UUID("b36c0344-253a-43e2-bd6a-ae02b6194111"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche/[^/]+"),
        parameter="page",
    ),
    # Provider: Euronews (euronews.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("638a0885-33f0-4b3b-9920-3f8bc9bde235"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: University of Toronto (utoronto.ca)
    QueryParameterUrlPageParser(
        provider_id=UUID("b075bc97-ce48-430e-84f7-e3aa080c675a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("b075bc97-ce48-430e-84f7-e3aa080c675a"),
        url_pattern=re_compile(r"^https?://[^/]+/news/searchnews\?"),
        parameter="page",
    ),
    # Provider: CCM (commentcamarche.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("5cb93699-fd67-40f7-81a3-aa1324967c3f"),
        url_pattern=re_compile(r"^https?://[^/]+/s/[^/]+"),
        parameter="page",
    ),
    # Provider: Akurat.co (akurat.co)
    QueryParameterUrlPageParser(
        provider_id=UUID("170a1b67-ea94-44ef-88b5-7fc79690f6a8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.page",
    ),
    # Provider: Monster (monster.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("42dda8bb-1e26-4cae-96af-f4ec1d489ddc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs/search\?"),
        parameter="page",
    ),
    # Provider: Sportzwiki (sportzwiki.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("2fd7cfb3-ce38-4395-a68a-c9a1c892792d"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Arabi21 (arabi21.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5e7fc1f2-c62b-4e44-8218-b18cd9438d90"),
        url_pattern=re_compile(r"^https?://[^/]+/[A-z]+\/*.Search\?"),
        parameter="page",
    ),
    # Provider: REI (rei.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c7363663-70c4-4572-b29a-6fffc871d767"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Ci123 (ci123.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/all/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/ask/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/bbs/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/blog/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/baobao/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/qq/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/zhishi/"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/ping/"),
        parameter="p",
    ),
    # Provider: State of Washington (wa.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("ac48eb32-9279-4e2a-ba30-f4097e2aa4c2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="gsc.page",
    ),
    # Provider: مستقل آنلاین (mostaghelonline.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("1e3ae50c-0c23-443b-9bff-46a2a967941d"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/"),
        parameter="curp",
    ),
    # Provider: اليمن العربي (elyamnelaraby.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("2ba639c9-f738-47ff-bad7-484fd4d30048"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: FINN.no (finn.no)
    QueryParameterUrlPageParser(
        provider_id=UUID("d592ffa5-ca1b-4614-a7be-41c40bb08a13"),
        url_pattern=re_compile(r"^https?://[^/]+/bap/forsale/search\.html\?"),
        parameter="page",
    ),
    # Provider: AcFun (acfun.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("5cdceac8-20bd-4b64-9c3f-3f76382ee11a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="pCursor",
    ),
    # Provider: ArzDigital (arzdigital.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("52277d36-7baa-45ab-ade5-4822cfa63683"),
        url_pattern=re_compile(r"^https?://[^/]+/search/page/[0-9]+/\?"),
        segment=3,
    ),
    # Provider: تاروت رنگی (taroot-rangi.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("9f77dcac-7522-4be1-bc62-ca42b451b1de"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: अमर उजाला (amarujala.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d07b5be0-141a-436c-a22d-e8c9e3f76bd0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Life Insurance Corporation of India (licindia.in)
    QueryParameterUrlPageParser(
        provider_id=UUID("c5753309-d9d4-41f6-90df-b8f587064e85"),
        url_pattern=re_compile(r"^https?://[^/]+/Search-Results\?"),
        parameter="page",
    ),
    # Provider: to10.gr (to10.gr)
    PathSegmentUrlPageParser(
        provider_id=UUID("89582999-4f2c-47d2-8730-3a13ce459e6a"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Know Your Meme (knowyourmeme.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9b322171-87d0-4360-baea-43c51ee1e21b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: aShemaleTube (ashemaletube.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("6e61c33d-821f-4162-a8a7-973a4b502369"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: iXXX (ixxx.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("f962ea26-a492-45a6-aa3d-1c1e18130b8b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: Careers360 (careers360.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b859c96c-d7e2-4651-8c06-f3c4a0bdbdd0"),
        url_pattern=re_compile(r"^https?://[^/]+/qna\?"),
        parameter="page",
    ),
    # Provider: MyFonts (myfonts.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("fdb7f465-eb54-418e-8160-bb0c9351e5e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="product_data[page]",
    ),
    # Provider: World Bank (worldbank.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("fc3a762d-0183-4c8a-99c1-15fad3aa4789"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="currentTab",
    ),
    # Provider: Klix.ba (klix.ba)
    QueryParameterUrlPageParser(
        provider_id=UUID("c5693c2a-98e5-4c3e-a4a2-a6eb72a4c890"),
        url_pattern=re_compile(r"^https?://[^/]+/pretraga\?"),
        parameter="str",
    ),
    # Provider: Yellow Pages (yellowpages.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ef513c8b-dc83-45d5-a818-501d51778b73"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Thumbzilla (thumbzilla.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ad18a9a7-2154-4047-b054-f68554456c9e"),
        url_pattern=re_compile(r"^https?://[^/]+/tags/[^/]+"),
        parameter="page",
    ),
    # Provider: ARY News (arynews.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("42530a28-ea0c-4816-9044-7159fb1ba877"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: 19888.tv (19888.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("78a4d2a7-4fc6-4f14-b594-5e5cff741484"),
        url_pattern=re_compile(r"^https?://[^/]+/provide/title_[^/]+/p[0-9]+"),
        segment=3,
        remove_pattern=re_compile(r"^p|\.html$"),
    ),
    PathSegmentUrlPageParser(
        provider_id=UUID("78a4d2a7-4fc6-4f14-b594-5e5cff741484"),
        url_pattern=re_compile(r"^https?://[^/]+/chanpin/p[0-9]+/\?"),
        segment=2,
        remove_pattern=re_compile(r"^p"),
    ),
    # Provider: Info.com (info.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("793a56e2-018f-46b8-b690-98edcf0599c2"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="page",
    ),
    # Provider: IGGGAMES (igg-games.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("aebf22a2-21ff-4a13-aa83-5347ba271175"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Filmweb (filmweb.pl)
    QueryParameterUrlPageParser(
        provider_id=UUID("65d6fc3c-79b6-4f1e-bc70-ef8213bf9327"),
        url_pattern=re_compile(r"^https?://[^/]+/films/search\?"),
        parameter="page",
    ),
    # Provider: Docker (docker.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8289c33f-8137-480e-9135-585b89048efe"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="sf_paged",
    ),
    # Provider: Watan News (watanserb.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("965cc1ba-e630-4b32-997b-076c26407521"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: رؤيا الإخباري (royanews.tv)
    QueryParameterUrlPageParser(
        provider_id=UUID("8210b75a-b44e-4fda-8e79-e794195990e0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: pc6 (pc6.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("593dd220-59e2-458c-9302-288800957037"),
        url_pattern=re_compile(r"^https?://[^/]+/cse/search\?"),
        parameter="entry",
    ),
    # Provider: HaiBunda (haibunda.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("cf2765be-6f7f-4ac4-acdb-c64368e2cd38"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[0-9]+"),
        segment=2,
    ),
    # Provider: Thomann (thomann.de)
    QueryParameterUrlPageParser(
        provider_id=UUID("e18a3dc0-ad5c-41d5-832a-cb3dea6d1d37"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z+]/search_dir\.html\?"),
        parameter="pg",
    ),
    # Provider: Corporate Finance Institute (corporatefinanceinstitute.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b878b7ab-263b-42e4-b515-b78c315ff957"),
        url_pattern=re_compile(r"^https?://[^/]+/resources/\?"),
        parameter="page_number",
    ),
    # Provider: 01net (01net.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("cd13f7e1-5ee1-47ed-9f1a-e846c4f3b699"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Porn HD (pornhd.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ea61cd89-315b-44fa-8760-e2ad7fdae326"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: Naijaloaded (naijaloaded.com.ng)
    PathSegmentUrlPageParser(
        provider_id=UUID("83652197-a457-4683-a947-f1829de35f0c"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Wenxuecity (wenxuecity.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("fe93cb3f-a8d9-4cb9-8bcc-f078590a405d"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Storyblocks (storyblocks.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("0029204e-8569-4918-bf53-bb8efd6272b5"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search/"),
        parameter="page",
    ),
    # Provider: SBNation (sbnation.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d5b954ec-5c68-47cd-87f9-b46b9b861d72"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Milenio (milenio.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8abcfe6e-c7c5-4c50-94a0-da0d21e85bc4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: iSLCollective (islcollective.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("f9bfbc2a-23eb-47f1-ad69-41c2c8409b83"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: CareerBuilder (careerbuilder.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8b47e032-5be6-4ebb-8019-db5564a8a3b5"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="page_number",
    ),
    # Provider: npm (npmjs.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("01d257c4-7e9e-4568-9264-cfd20224b8d6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: ProQuest (proquest.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("4cc8b413-3a37-4945-98e5-89e5a4c64940"),
        url_pattern=re_compile(r"^https?://[^/]+/results/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: BoyFriendTv (boyfriendtv.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("e7628616-5f0d-455d-a70c-9fe0d156e7f0"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: Slidesgo (slidesgo.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("59856d35-1875-4a02-8398-85c982ed256f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: PornHat (pornhat.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("23bcdea8-3f3e-43dc-9ca7-2da9c16eef8a"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: Cisco Networking Academy (netacad.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("af2ad80d-c03c-4eab-af86-6dfbc3d0b4e8"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node/"),
        parameter="page",
    ),
    # Provider: NiPic.com (nipic.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("6c908f6f-8d57-4e25-b011-fa192dc84e5b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    # Provider: Check24 (check24.de)
    QueryParameterUrlPageParser(
        provider_id=UUID("155c901b-8757-47ae-82b5-6050e5d8ded3"),
        url_pattern=re_compile(r"^https?://[^/]+/suche\?"),
        parameter="page",
    ),
    # Provider: Fashion Nova (fashionnova.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("47d05717-f34e-4b1b-9109-8c73340be59e"),
        url_pattern=re_compile(r"^https?://[^/]+/pages/search-results/"),
        parameter="page",
    ),
    # Provider: Joe Monster (joemonster.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("d74f0524-3c3b-4ca8-8c7e-29724329005e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="pageID",
    ),
    # Provider: PowerSchool (powerschool.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("93b46460-d539-4e3c-b813-15b22e084cc3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Pearson VUE (pearsonvue.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("6c4c0fa5-b9fa-4e62-9886-860a305f296a"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\.aspx\?"),
        parameter="page",
    ),
    # Provider: State Bank of India (sbi.co.in)
    QueryParameterUrlPageParser(
        provider_id=UUID("1e03bb45-3f2d-4031-aef4-52a67da17e89"),
        url_pattern=re_compile(r"^https?://[^/]+/web/personal-banking"),
        parameter="_com_liferay_portal_search_web_portlet_SearchPortlet_cur",
    ),
    # Provider: SecNews (secnews.gr)
    PathSegmentUrlPageParser(
        provider_id=UUID("9c9e737a-4517-431a-a4c3-8b0cab060140"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Ministère de l'Intérieur et des Outre-mer (interieur.gouv.fr)
    QueryParameterUrlPageParser(
        provider_id=UUID("fca823dd-aa70-4dbd-a66b-48acdbedb553"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche\?"),
        parameter="page",
    ),
    # Provider: Turkish Revenue Administration (gib.gov.tr)
    QueryParameterUrlPageParser(
        provider_id=UUID("90679401-944e-47ec-bd85-308288cb1930"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node/"),
        parameter="page",
    ),
    # Provider: JB Hi-Fi (jbhifi.com.au)
    QueryParameterUrlPageParser(
        provider_id=UUID("601e395a-1f76-45ef-9679-21db78e786ba"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Chefkoch (chefkoch.de)
    PathSegmentUrlPageParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        segment=2,
        remove_pattern=re_compile(r"s"),
    ),
    # Provider: Micro Center (microcenter.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9bb94e4e-bf20-41a5-85b8-b29509a3980e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search_results\.aspx"),
        parameter="page",
    ),
    # Provider: U.S. Securities and Exchange Commission (sec.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("fd6decbc-de52-41e5-9ec6-55c8bf4f2a96"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Azərbaycan Respublikasının Dövlət İmtahan Mərkəzi (dim.gov.az)
    QueryParameterUrlPageParser(
        provider_id=UUID("232d2521-6b66-4889-8e1b-aa02ab6ecf27"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="PAGEN_1",
    ),
    # Provider: Science (science.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("ab2d9ff0-538e-4b60-b11c-7098366ed819"),
        url_pattern=re_compile(r"^https?://[^/]+/action/doSearch\?"),
        parameter="startPage",
    ),
    # Provider: 文春オンライン (bunshun.jp)
    QueryParameterUrlPageParser(
        provider_id=UUID("090d9a0d-3e5a-4834-ba71-0d469b9be72a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: 广州房地产 (fzg360.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("091c298f-59a6-4575-8064-a8482c777557"),
        url_pattern=re_compile(
            r"^https?://[^/]+/news/lists/keyword/[^/]+/page/[0-9]+\.html"
        ),
        segment=6,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: ManualsLib (manualslib.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("59585d0e-d541-46e5-8053-fca52e6e64e7"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[^/]+.html\?"),
        parameter="page",
    ),
    # Provider: TinEye (tineye.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8d7f7bfa-f362-4af0-bb56-6cb192b1ba94"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="page",
    ),
    # Provider: JavBus (javbus.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("a32be5bd-cf27-4718-8f4e-6f139d7e3deb"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: Library of Congress (loc.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("a84af1ec-3f71-46da-aa6e-5d142987ae95"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(search|audio|books|film-and-videos|manuscripts|maps|notated-music|newspapers|photos|web-archives)"
        ),
        parameter="sp",
    ),
    # Provider: MSD Manuals (msdmanuals.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("50732f3e-0826-41e0-808c-15b376709870"),
        url_pattern=re_compile(r"^https?://[^/]+/.*SearchResults\?"),
        parameter="page",
    ),
    # Provider: Fuq.com (fuq.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("efb01398-7ed7-4c47-af4b-6a25e315fba9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: SarvGyan (sarvgyan.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("5c7befd5-3401-4f42-a677-07c52eea401b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+"),
        segment=2,
    ),
    # Provider: SimplyHired (simplyhired.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("89728fb8-5c3d-41fd-b5cc-0b07561ba9b0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="pn",
    ),
    # Provider: Tebyan.NET (tebyan.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("04f99189-55a8-4aeb-8a12-7894ab465a0d"),
        url_pattern=re_compile(r"^https?://[^/]+/newindex\.aspx\?"),
        parameter="pi",
    ),
    # Provider: bigbasket (bigbasket.com)
    FragmentParameterUrlPageParser(
        provider_id=UUID("a5821288-5394-423c-87f1-23af9d38c955"),
        url_pattern=re_compile(r"^https?://[^/]+/ps/\?"),
        parameter="!page",
    ),
    # Provider: iWank TV (iwank.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("7b550685-e0e9-4030-b825-68d8cb8b485b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+/"),
        segment=3,
    ),
    # Provider: Instant Gaming (instant-gaming.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("bcf30841-c443-4e79-b5f2-466772889b0a"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/\?"),
        parameter="page",
    ),
    # Provider:  Kongfz (kongfz.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a837f299-5f5c-405a-a1a0-4f45f80a4b0e"),
        url_pattern=re_compile(r"^https?://[^/]+/product_result/\?"),
        parameter="pagenum",
    ),
    # Provider: Babyshop (babyshop.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4024ca33-9987-43be-94a2-22368cb56765"),
        url_pattern=re_compile(r"^https?://[^/]+/search/searchbytext\?"),
        parameter="page",
    ),
    # Provider: e621 (e621.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("160f245d-4694-433a-a37f-0fbd8f1f2e0c"),
        url_pattern=re_compile(r"^https?://[^/]+/posts\?"),
        parameter="page",
    ),
    # Provider: Interactive Brokers (interactivebrokers.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("77cc8fa4-e988-4a4e-9144-53a258e5dfbd"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/index\.php\?"),
        parameter="page",
    ),
    # Provider: Traveler Master (travelermaster.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("42b1b2ad-edbf-4280-904b-f4c7f3ff44a6"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: ElecFans (elecfans.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("669c53aa-5718-4eab-9f39-accdc8b266e3"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="page",
    ),
    # Provider: Tailor Brands (tailorbrands.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e8442408-f6df-4abe-b4ff-7c5ab3c6f367"),
        url_pattern=re_compile(r"^https?://[^/]+/hc/[a-z]+-[a-z]+/search\?"),
        parameter="page",
    ),
    # Provider: RussianFood (russianfood.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("220615bc-4668-49c8-96fa-c6a063a2f2c6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/simple/index\.php\?"),
        parameter="page",
    ),
    # Provider: TMDB (themoviedb.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("2238fb75-68f6-452c-a2f7-986cce78bb32"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: PCWorld (pcworld.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("aada27c7-823d-4932-9033-583ca685d641"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.page",
    ),
    # Provider: Altibbi (altibbi.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("2da5cc76-c62d-43f6-8000-e8d697f07689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/questions\?"),
        parameter="page",
    ),
    # Provider: ZAFUL (zaful.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("55a1e624-32fe-45d3-89d5-25b697e6bf9a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="pn",
    ),
    # Provider: iG (ig.com.br)
    QueryParameterUrlPageParser(
        provider_id=UUID("1414ff73-56d6-4c16-8e38-40ff05bb4b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/buscar"),
        parameter="p",
    ),
    # Provider: AnySex (anysex.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("30121aa8-cd20-4fc8-806c-ca5cd0aafac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Patagonia (patagonia.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c5d9bdcf-34e3-4308-b685-744fe8d8586d"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]/[a-z]/search/\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("c5d9bdcf-34e3-4308-b685-744fe8d8586d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="page",
    ),
    # Provider: Bonanza (bonanza.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("3c4b3e42-869b-4833-b2b5-a947e5752d4c"),
        url_pattern=re_compile(r"^https?://[^/]+/items/search\?"),
        parameter="q[page]",
    ),
    # Provider: MQL5 (mql5.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("65362caf-d7e6-4d2c-9678-d636622538b5"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search"),
        parameter="page",
    ),
    # Provider: 9to5Mac (9to5mac.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("ac75cebc-810a-4e73-904b-5e58030a46d2"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: USAGov (usa.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("f8511351-145c-49f0-a357-2970d58e4462"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Al-Maraabi Medias (al-maraabimedias.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("d5f49941-eed9-444a-b382-85fa68969e37"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="paged",
    ),
    # Provider: U.S. Department of Justice (justice.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("bd846aca-1170-47fc-9425-0fcda3616e11"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Alison (alison.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b2a98af7-4b12-4df0-ad7c-c67eeb6b925f"),
        url_pattern=re_compile(r"^https?://[^/]+/(courses|careers-search)\?"),
        parameter="page",
    ),
    # Provider: The Ringer (theringer.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e66088e3-89c2-4819-bace-6574ff14cd04"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Zimmertüren OCHS (tueren-fachhandel.de)
    QueryParameterUrlPageParser(
        provider_id=UUID("26c9fc75-5f47-49f1-940f-cba62d62834a"),
        url_pattern=re_compile(r"^https?://[^/]+/catalogsearch/result\?"),
        parameter="p",
    ),
    # Provider: Zimbio (zimbio.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("bcd95c84-590b-476f-8333-33ddbc519551"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.page",
    ),
    # Provider: ehow (ehow.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7e1d4dec-4b92-4b25-9321-54a404500bb3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: しぃアンテナ (2ch-c.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("5c7b08a7-c0cc-47e0-8b08-3382aee61b5d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="pn",
    ),
    # Provider: HS编码查询 (hsbianma.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("b54cc512-eb0c-4585-8822-52f5f3a5bf5a"),
        url_pattern=re_compile(r"^https?://[^/]+/Search/[0-9]+\?"),
        segment=2,
    ),
    # Provider: 早报 (zaobao.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("cdf2dd02-9ce5-441a-ac5d-b44d766bcf03"),
        url_pattern=re_compile(r"^https?://[^/]+/search/site/[^/]+"),
        parameter="page",
    ),
    # Provider: GiveMeSport (givemesport.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("75dbe70c-7e8c-4284-a863-40f1d44297d1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+"),
        segment=2,
    ),
    # Provider: Internshala (internshala.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("492e2ccf-6053-42dc-81f8-4b7877a33634"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(internships|jobs)/keywords-[^/]+/page-[0-9]+/"
        ),
        segment=3,
        remove_pattern=re_compile(r"^page-"),
    ),
    # Provider: Jogos 360 (jogos360.com.br)
    QueryParameterUrlPageParser(
        provider_id=UUID("bca1691b-0feb-40cc-98f2-aaba2aeaed44"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="p",
    ),
    # Provider: Belgium.be (fgov.be)
    QueryParameterUrlPageParser(
        provider_id=UUID("9fa587a9-21ee-4547-9277-704587f8a8fb"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="page",
    ),
    # Provider: 오늘의유머 (todayhumor.co.kr)
    QueryParameterUrlPageParser(
        provider_id=UUID("514f72b9-c0b6-439c-8955-cc353bd7e738"),
        url_pattern=re_compile(r"^https?://[^/]+/board/list\.php\?"),
        parameter="page",
    ),
    # Provider: Dice (dice.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("cbbd5882-5eea-43bf-9b67-a1a0d70854db"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="page",
    ),
    # Provider: خبر ورزشی (khabarvarzeshi.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("48cb0cd7-35e1-4800-a23e-997a9835a77a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="pi",
    ),
    # Provider: Arcalive (arca.live)
    QueryParameterUrlPageParser(
        provider_id=UUID("198a7743-5a99-4e42-be03-4178c90d7c97"),
        url_pattern=re_compile(r"^https?://[^/]+/b/breaking\?"),
        parameter="p",
    ),
    # Provider: JAV HD Porn (javhdporn.net)
    PathSegmentUrlPageParser(
        provider_id=UUID("231b8492-f522-4ffa-a80d-2a75cf76cef1"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page/[0-9]+"),
        segment=4,
    ),
    # Provider: LetPub编辑 (letpub.com.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("a0da5575-f218-41a0-b897-e7054dc30d28"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.php\?"),
        parameter="currentsearchpage",
    ),
    # Provider: Área VIP (areavip.com.br)
    PathSegmentUrlPageParser(
        provider_id=UUID("21fdae62-990e-41b4-bca4-126a5c5779c7"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: OpenDNS (opendns.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("af4be1f9-d453-4c8c-93a7-c4f8e6fc42ce"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="cludopage",
    ),
    # Provider: Brave (brave.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e3be3140-7f78-4de1-a43b-6c75d345e4c4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: CK365 (ck365.cn)
    PathSegmentUrlPageParser(
        provider_id=UUID("294e275f-689e-4b62-af94-986e62c3fda8"),
        url_pattern=re_compile(r"^https?://[^/]+/news/search(-xzg-)?kw-[^-]-\.html"),
        segment=2,
        remove_pattern=re_compile(
            "^search(-xzg-)?kw-[^-]-(-fields-[0-9])?|(-page-[0-9])?-?\.html$"
        ),
    ),
    # Provider: Western Governors University (wgu.edu)
    QueryParameterUrlPageParser(
        provider_id=UUID("0673e75f-baa6-4365-b4ad-04cab6c5d8ad"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html"),
        parameter="cludopage",
    ),
    # Provider: Levi's (levi.com.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("1ced0855-8d1d-4505-bce8-d5f518b74a01"),
        url_pattern=re_compile(r"^https?://[^/]+/[A-Z]/[a-z]+_[A-Z]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: Radio Times (radiotimes.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("156d3e19-bb02-4073-96cc-a3ad67abd76f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/news/page/[0-9]+/\?"),
        segment=4,
    ),
    # Provider: موقع برستيج (brstej.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("a41f74d7-fb1c-4d42-ab0e-80304d7042f9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="page",
    ),
    # Provider: 欧乐影院 (olevod.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("b4e6ec20-ca60-4e65-a3a7-2005b455a945"),
        url_pattern=re_compile(
            r"^https?://[^/]+/index\.php/[^/]+/search/page/[0-9]+/wd/[^/]+\.html"
        ),
        segment=5,
    ),
    # Provider: Kinsta (kinsta.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("97228c7c-449c-4773-bf49-e3f0c4dd5dbb"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Aftodioikisi.gr (aftodioikisi.gr)
    PathSegmentUrlPageParser(
        provider_id=UUID("df0db395-d7f9-4e32-af97-065dc80c4733"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Thomasnet (thomasnet.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("c920856e-587f-4ea6-adb9-b7348e01db93"),
        url_pattern=re_compile(
            r"^https?://[^/]+/search/(industry-insights|white-paper-guides|product-news|company-news)/[0-9]+"
        ),
        segment=3,
    ),
    # Provider: Dafiti (dafiti.com.br)
    QueryParameterUrlPageParser(
        provider_id=UUID("5533a9d5-0172-448a-8af6-1804d29732a7"),
        url_pattern=re_compile(r"^https?://[^/]+/catalog/\?"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("5533a9d5-0172-448a-8af6-1804d29732a7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    # Provider: Linkvertise (linkvertise.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("2852fdb7-8243-4dda-a522-3ba445a24eb1"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+/\?"),
        segment=3,
    ),
    # Provider: 999.md (999.md)
    QueryParameterUrlPageParser(
        provider_id=UUID("11c61ce1-cedb-482e-b1b0-4e53aa5525e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Académie de Versailles (ac-versailles.fr)
    QueryParameterUrlPageParser(
        provider_id=UUID("b2a0848d-3974-410e-b80a-728ba6ecff8f"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche"),
        parameter="page",
    ),
    # Provider: Manganato (manganato.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d9abf7ba-9cfb-4dd8-ae30-d0b91e021a5d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/story/[^/]+\?"),
        parameter="page",
    ),
    # Provider: Kizi (kizi.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4908058e-98db-48cd-aa45-2fe0de8cc75a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Jobartis (jobartis.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e2543f76-712e-4373-b66b-730d133d17d6"),
        url_pattern=re_compile(r"^https?://[^/]+/vagas-emprego\?"),
        parameter="page",
    ),
    # Provider: فتوکده (photokade.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("873db19a-45ea-424c-89b5-ee22bd2e4367"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: HDrezka (hdrezka.me)
    QueryParameterUrlPageParser(
        provider_id=UUID("842851b8-57c2-4523-8005-af3ac3e47652"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: ActBlue (secure.actblue.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9ed9815d-fde0-44b9-bee4-6b3644ebd2ff"),
        url_pattern=re_compile(r"^https?://[^/]+/directory\?"),
        parameter="page",
    ),
    # Provider: LetMeJerk (letmejerk.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("56693bc3-0d40-46b5-ac95-5466fa202e31"),
        url_pattern=re_compile(r"^https?://[^/]+/se/"),
        parameter="p",
    ),
    # Provider: CJ Dropshipping (cjdropshipping.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e15f1c19-5590-422a-8a16-0f489e3216ca"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="pageNum",
    ),
    # Provider: TigerDirect (tigerdirect.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("58fd63ad-8dff-4cd8-8996-ae3b87d99bb0"),
        url_pattern=re_compile(r"^https?://[^/]+/applications/SearchTools"),
        parameter="page",
    ),
    # Provider: منیبان (moniban.news)
    QueryParameterUrlPageParser(
        provider_id=UUID("e00da4ec-26f7-455c-b42d-fbe525f7e907"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/"),
        parameter="curp",
    ),
    # Provider: EMPFlix (empflix.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4473c856-9a24-4c27-954f-de8240b21e3a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Asura Scans (asura.gg)
    PathSegmentUrlPageParser(
        provider_id=UUID("47230112-5794-4fa1-8a6a-01e60ac03341"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: 快吧游戏 (kuai8.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("55b2f892-a52d-48b7-86ed-4e7dc3c6869c"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Federal Trade Commission (ftc.gov)
    QueryParameterUrlPageParser(
        provider_id=UUID("9d6923ad-9fcd-4a9a-bb03-a13a9de17ab9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Gimy TV (gimy.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("c7b1f5f4-934b-43c8-8072-8ce53056663e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"([^0-9.])"),
    ),
    # Provider: JRA日本中央競馬会 (jra.go.jp)
    QueryParameterUrlPageParser(
        provider_id=UUID("56b0ef36-b4b5-4d8d-87d5-0e8dface495a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: WebCrawler (webcrawler.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ca614ed7-7c57-464f-9f7e-0e3e36f849da"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="page",
    ),
    # Provider: 17货源 (17zwd.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("69f6d361-8e1d-42e3-9db4-ba6e0d8888e6"),
        url_pattern=re_compile(r"^https?://[^/]+/sks\.htm\?"),
        parameter="spage",
    ),
    # Provider: PRWeb (prweb.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("696acb0c-c481-45a3-a8d6-b456fde2129a"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\.aspx\?"),
        parameter="start",
    ),
    # Provider: YIFY Subtitles (yts-subs.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8e54437d-2e26-4276-8bd6-b64af9adfd9e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+\?page"),
        parameter="page",
    ),
    # Provider: Повар.ру (povar.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("6915ef60-fd7e-408a-a225-23447a8fb7a9"),
        url_pattern=re_compile(r"^https?://[^/]+/xmlsearch\?"),
        parameter="page",
    ),
    # Provider: НТВ.Ru (ntv.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("a09b2970-91e6-4ea7-8b6a-d89196186a17"),
        url_pattern=re_compile(r"^https?://[^/]+/finder/\?"),
        parameter="pn",
    ),
    # Provider: InvestorPlace (investorplace.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("16728571-5a71-4790-abc8-43de01db9764"),
        url_pattern=re_compile(r"^https?://[^/]+/search&\?"),
        parameter="pg",
    ),
    # Provider: FreeOnes (freeones.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("8bafca69-c2d8-4b85-b3dc-168030c5c875"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(search|suche)\?"),
        parameter="p",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("8bafca69-c2d8-4b85-b3dc-168030c5c875"),
        url_pattern=re_compile(r"^https?://[^/]+/(photos|babes|videos|cams)\?"),
        parameter="p",
    ),
    # Provider: AGE动漫 (agemys.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7f4dfd14-b1bf-4286-a354-1f98602e7f8b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Gogoanime (gogoanime.fi)
    QueryParameterUrlPageParser(
        provider_id=UUID("25c75bd9-145e-4bef-8125-b361e91d4832"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="page",
    ),
    # Provider: Légifrance (legifrance.gouv.fr)
    QueryParameterUrlPageParser(
        provider_id=UUID("0657eade-da9a-48ae-b132-263551c04cb7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="page",
    ),
    # Provider: Gay Male Tube (gaymaletube.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5c638567-14e2-41a1-ab1f-bf0436fd426b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+\?"),
        parameter="page",
    ),
    # Provider: VAVEL (vavel.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b829f8d1-e439-4669-8d14-8ffdf8825d67"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="page",
    ),
    # Provider: BestJavPorn (bestjavporn.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("34468ac0-17d8-4208-b999-f7a1fdbef8f0"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page/[0-9]+"),
        segment=4,
    ),
    # Provider: WoWProgress (wowprogress.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5f71c55f-fd47-4cf6-851c-312bfa82a70d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: المواطن (elmwatin.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("0879f31d-e840-4dd5-ac87-6b100195cac6"),
        url_pattern=re_compile(r"^https?://[^/]+/list\.aspx\?"),
        parameter="Page",
    ),
    # Provider: Hongkiat (hongkiat.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("b4b74976-b043-48d2-942a-1f6943b3416b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Manga Raw (mangaraw.co)
    QueryParameterUrlPageParser(
        provider_id=UUID("54dc3b01-8316-4526-8396-b455edf5ac44"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    # Provider: Gazeta do Povo (gazetadopovo.com.br)
    QueryParameterUrlPageParser(
        provider_id=UUID("73b0e565-bc20-4fba-963a-ce498b1ce6f2"),
        url_pattern=re_compile(r"^https?://[^/]+/busca"),
        parameter="page",
    ),
    # Provider: 留园网 (6park.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("2faeba1b-de53-482a-a5d6-a56df7aec7c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="p",
    ),
    # Provider: Perez Hilton (perezhilton.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("815b4535-d42a-499a-b2c7-4fc09aad6a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Ero Video (ero-video.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("1b090369-2f18-4bc7-8c91-e4dea41e3f9e"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="page",
    ),
    # Provider: IFLScience (iflscience.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7a49ec69-7eef-4e5d-8ee1-e9813eec739e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: PornTube (porntube.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("df350b9c-4017-46ef-b219-bbe74d53e24a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: American Military News (americanmilitarynews.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("92c40ea3-f34f-4fe7-97f1-3fafbdf091bd"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Alot (alot.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("b0dff7be-a08d-4355-b176-a9914c13ed6a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: 美国之音中文网 (voachinese.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("454c52f4-382f-4fc5-9233-cca81b5715b5"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="pp",
    ),
    # Provider: Bue de Musica (buedemusica.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("c1a5a3d7-fa59-464b-b3c3-08a152ef7ec9"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Arch Linux (archlinux.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("d6bd0924-be4d-4b5d-b3d7-54cbc89e475d"),
        url_pattern=re_compile(r"^https?://[^/]+/packages"),
        parameter="page",
    ),
    # Provider: SEOClerks (seoclerk.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("994de6d6-3931-4af4-a2c1-286197d64d9f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page/[0-9]+"),
        segment=4,
    ),
    # Provider: CCN (ccn.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("71a377ac-2de2-498d-881f-292bb91809a1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Pornez.net (pornez.net)
    PathSegmentUrlPageParser(
        provider_id=UUID("085e931f-8c39-4b41-91d2-41d5391652c8"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Search Engine Land (searchengineland.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("d7b39362-63c1-485b-b682-02f3e3e9089d"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Pronto.com (pronto.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("1f984e0a-8de7-48ce-a265-fcf191919b82"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\?"),
        parameter="page",
    ),
    # Provider: rolloid (rolloid.net)
    PathSegmentUrlPageParser(
        provider_id=UUID("8baf6399-830e-44c4-9c6b-1317b06c4dbf"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Movierulz (5movierulz.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("24182d53-4e55-4a11-8452-3f4fdd07d6f4"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Movies2watch (movies2watch.tv)
    QueryParameterUrlPageParser(
        provider_id=UUID("d0e30f77-6422-4d50-82ed-e08f1fb9dbdc"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="page",
    ),
    # Provider: 稿定 (gaoding.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("d92a661b-e529-4513-922f-75246403f463"),
        url_pattern=re_compile(r"^https?://[^/]+/contents/[^/]+_pn[0-9]+"),
        segment=2,
        remove_pattern=re_compile(r"^.*_pn"),
    ),
    # Provider: The Vintage News (thevintagenews.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("a2237d78-cdd0-4476-a886-92a309c89993"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: ORIENT (orient.tm)
    QueryParameterUrlPageParser(
        provider_id=UUID("2497b49b-4e0f-4e75-b789-16d469dab969"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: KBH Games (kbhgames.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("a569f86c-dc75-40d9-a107-4aebdbe69708"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Fanpop (fanpop.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("1097060d-7676-43b0-b6fa-4ebd632e74e5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page_num",
    ),
    # Provider: Hearthstone Top Decks (hearthstonetopdecks.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("682ce07c-60a7-46c5-a4c2-f0639eb39b5b"),
        url_pattern=re_compile(r"^https?://[^/]+/(cards|decks)/page/[0-9]+/\?"),
        segment=3,
    ),
    # Provider: المستقبل الاقتصادي (mostkbal.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c4cc8db3-b372-4439-ad1a-c96de222e4dc"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\?"),
        parameter="page",
    ),
    # Provider: SearchLock (searchlock.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("3df606b7-2fea-4e22-9670-53ea29b6b4d5"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="apgn",
    ),
    # Provider: tagDiv (tagdiv.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("0662ac89-c677-473f-887b-8750c9dd13d3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: LivingSocial (livingsocial.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("31a21d99-f2c7-4d31-8b1f-1a2a8632cb22"),
        url_pattern=re_compile(r"^https?://[^/]+/browse/[^/]+\?"),
        parameter="page",
    ),
    # Provider: University of Zambia (unza.zm)
    QueryParameterUrlPageParser(
        provider_id=UUID("6e73ff3b-1604-488b-8303-b08f492d2155"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node\?"),
        parameter="page",
    ),
    # Provider: SexKbj (sexkbj.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("f4b82c86-c0f3-4eec-a572-aa61fa631a37"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: 全球塑胶网 (51pla.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/buyinfo/search\?"),
        parameter="pageNo",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/company/search\?"),
        parameter="pageNo",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/price/search\?"),
        parameter="pageNo",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/product/search\?"),
        parameter="pageNo",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/spec/search\?"),
        parameter="pageNo",
    ),
    # Provider: Jacquie Lawson (jacquielawson.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("2f4b5ee3-aa5b-43ef-8648-648025b803d4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: The Institute for Health Metrics and Evaluation (healthdata.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("4ab4dc1f-186a-49eb-85aa-5de655e95933"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: پیشنهاد ویژه (pishnahadevizheh.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("936e6dd5-d991-4ef4-a4ca-238fb5584d40"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/\?"),
        parameter="curp",
    ),
    # Provider: خبرگزاری موج (mojnews.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4bc98471-167d-4cc2-9cb6-31ef0d33330a"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/newsstudios/search\?"),
        parameter="gsc.page",
    ),
    # Provider: WeaPlay (weadown.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("4c8978cb-58c8-4caa-acbd-5f4bdd3ac140"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: WebHostingTalk (webhostingtalk.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("7c47f364-b486-460d-9feb-3c8cc29c3759"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="page",
    ),
    # Provider: z3.fm (z3.fm)
    QueryParameterUrlPageParser(
        provider_id=UUID("d82bc7ec-69a3-4ace-a1c0-512539b0ba06"),
        url_pattern=re_compile(r"^https?://[^/]+/mp3/search\?"),
        parameter="page",
    ),
    # Provider: هير نيوز (her-news.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("53182eac-a03f-4fa1-87cd-2b5fd29e37b0"),
        url_pattern=re_compile(r"^https?://[^/]+/list\.aspx\?"),
        parameter="Page",
    ),
    # Provider: خوندنی (khoondanionline.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("3240b96e-42e3-4959-9850-35cc65682eea"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/\?"),
        parameter="curp",
    ),
    # Provider: The Pirate Bay (pirateproxy.lat)
    QueryParameterUrlPageParser(
        provider_id=UUID("5b0d6f76-f59f-41f5-9dcc-be6ce4caa7a9"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="page",
    ),
    # Provider: aufeminin.com (aufeminin.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5cee89de-b0b1-4bfa-acc3-aabfa10e1377"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="p",
    ),
    # Provider: Sharp (jp.sharp)
    QueryParameterUrlPageParser(
        provider_id=UUID("74a5a3c8-783f-4ba1-9f8d-1d5dbfdcd41d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/index\.html"),
        parameter="page",
    ),
    # Provider: JavDB (javdb.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("464b3f84-541e-45bf-a5aa-8eb1969ffef6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: PornerBros (pornerbros.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("34d6c064-a76e-4696-b3a4-26ea15b712b3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: search.ch (search.ch)
    QueryParameterUrlPageParser(
        provider_id=UUID("b940b181-da03-481c-a5de-3b3860dd1b45"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="pages",
    ),
    # Provider: 北京教育考试院 (bjeea.cn)
    QueryParameterUrlPageParser(
        provider_id=UUID("8793daba-99ca-4cb2-9090-f36bad4efb67"),
        url_pattern=re_compile(r"^https?://[^/]+/plus/search\.php\?"),
        parameter="PageNo",
    ),
    # Provider: dogpile (dogpile.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("af246cce-08a8-447a-8a48-8af7266d5981"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="page",
    ),
    # Provider: PornTop.com (porntop.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("09373ee0-5fd0-48a9-93a0-edcb9d9f31b4"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="p",
    ),
    # Provider: Naija News (naijanews.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("7d326758-4efe-4523-a58a-1121ed097165"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: SEXSEQ (sexseq.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("48ac3be4-3906-49b0-a4e9-e8b4401603c6"),
        url_pattern=re_compile(r"^https?://[^/]+/trends/[^/]+/[0-9]+/"),
        segment=3,
    ),
    # Provider: Jomys (jomys.xyz)
    QueryParameterUrlPageParser(
        provider_id=UUID("222b2c1d-a658-4938-81da-b217e09074c5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: 中国搜索 (chinaso.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/all"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/block"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/game"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/social"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/story"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/video\?"),
        parameter="pn",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/young\?"),
        parameter="pn",
    ),
    # Provider: 漫猫动漫 (comicat.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("57c6b6fd-d915-4b8e-98fd-9c83d20a0743"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="page",
    ),
    # Provider: Manga Fox (fanfox.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("84774e22-f12e-4372-93d1-14ced15ec2de"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Hell Porno (hellporno.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("dccf0a94-ba06-498d-a221-3165b07bcea9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Sarcasm (sarcasm.co)
    PathSegmentUrlPageParser(
        provider_id=UUID("1bde6ae8-906c-4906-b12b-ca2a582894f5"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: 俺のエロ本 (oreno-erohon.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("3eff1424-bebf-430e-af61-fa29c5dcf934"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: IBTimes (ibtimes.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("dcd1db5c-31c9-4fa8-886f-f0d93c11003f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/site/"),
        parameter="page",
    ),
    # Provider: BlackFriday.com (blackfriday.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("32059869-8f93-43ad-ad27-c27afada5350"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results\?"),
        parameter="page",
    ),
    # Provider: The Western Journal (westernjournalism.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("8f53efb7-a0bf-4800-a6dd-92c1beae2f5f"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Fanpage (fanpage.gr)
    PathSegmentUrlPageParser(
        provider_id=UUID("80b1810e-9871-436e-b34e-4efe4607b33c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page/[0-9]+"),
        segment=4,
    ),
    # Provider: MMA Mania (mmamania.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("615534b9-49a0-40a6-af82-226dd549549c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: ASG.TO (asg.to)
    QueryParameterUrlPageParser(
        provider_id=UUID("cc0e6857-7647-4bb1-8a8c-0b09dbf2cee3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Bloody Elbow (bloodyelbow.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("54aed98f-7dee-468b-8e07-c7e23b0676d4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: PlugRush (plugrush.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("f8c5e565-a3da-4d47-b858-5b689a316d74"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Justindianporn.me (justindianporn.me)
    QueryParameterUrlPageParser(
        provider_id=UUID("bd5edd10-228a-4e33-a0dc-992d445fd508"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="p",
    ),
    # Provider: Kwork (kwork.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("6b051f83-0b97-4c9d-97f2-a7da12e44c43"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Единая Россия (er.ru)
    QueryParameterUrlPageParser(
        provider_id=UUID("c2ecfa24-e9a8-4565-86de-7181e4a9869a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: JobStreet (jobstreet.com.sg)
    PathSegmentUrlPageParser(
        provider_id=UUID("02b4a425-deba-4d4d-b54a-e30372ccb4b2"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/job-search/[^/]+/[0-9]+"),
        segment=4,
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("02b4a425-deba-4d4d-b54a-e30372ccb4b2"),
        url_pattern=re_compile(r"^https?://[^/]+/career-resources/search\?"),
        parameter="pages",
    ),
    # Provider: AngoVagas (angovagas.net)
    PathSegmentUrlPageParser(
        provider_id=UUID("9335de96-a119-4723-a5b6-89f45d9c0151"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Cooch.tv (cooch.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("4e6c9864-a484-452e-b6d1-ab099aa7d4f4"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/[^/]+/[0-9]+\.html"),
        segment=4,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: Canal Tutorial (canaltutorial.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("24b6d8a5-ed91-45ef-99fd-dad8ca4dfbc1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: هنتاي تايم (hentai-time.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("da31e49e-9afe-4643-a9ce-46b0321bd2d6"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: World News (wn.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("74c7cdaa-32b9-4d6c-ae92-56ce997e16b0"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="pagenum",
    ),
    # Provider: Shodan (shodan.io)
    QueryParameterUrlPageParser(
        provider_id=UUID("7b1ae7ee-e273-48ab-ac8a-47a3cd0e5e48"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: WooCommerce (woothemes.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9ea9b48e-ab51-4cbb-bde5-eec8f04b1533"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="page",
    ),
    # Provider: Open Site Explorer (opensiteexplorer.org)
    QueryParameterUrlPageParser(
        provider_id=UUID("eb1c148d-91f8-4bec-a887-268b86f0eaba"),
        url_pattern=re_compile(r"^https?://[^/]+/links"),
        parameter="page",
    ),
    # Provider: 中天電視 (ctitv.com.tw)
    PathSegmentUrlPageParser(
        provider_id=UUID("01d6d4f5-6e18-4c2d-8a4c-1f1be902c0a0"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Liftable (liftable.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("043c803d-9028-43e4-9a4f-6fb6beb4faa7"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider:  IMzog (imzog.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("80345c90-c3ea-4232-a7c5-1e6a5f13e6ae"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+/[0-9]+"),
        segment=4,
    ),
    # Provider: ViralNova (viralnova.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("176886ca-2705-4784-b9ec-336910841d80"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Metacrawler (metacrawler.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5dcb661f-4094-490e-89d3-58d8e8010d65"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="page",
    ),
    # Provider: Websta (websta.me)
    PathSegmentUrlPageParser(
        provider_id=UUID("da02c58e-e127-41f4-86a3-98e74060de37"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: XGap (xgap.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("95ed525b-e3c4-407f-8231-4094c9791066"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/[^/]+/[0-9]+\.html"),
        segment=4,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: mBank (mbank.com.pl)
    QueryParameterUrlPageParser(
        provider_id=UUID("ac4db475-1ef3-4960-aac6-11b04f72e28f"),
        url_pattern=re_compile(r"^https?://[^/]+/szukaj"),
        parameter="pag",
    ),
    # Provider: Nhà Đất Số (nhadatso.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9554d90d-19cf-45f3-a76f-c8707833a918"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: skat.dk (skat.dk)
    QueryParameterUrlPageParser(
        provider_id=UUID("aeda1dc1-8c3a-4a7c-acc0-4a5c5c868957"),
        url_pattern=re_compile(r"^https?://[^/]+/data\.aspx\?"),
        parameter="cludopage",
    ),
    # Provider: Kiddle (kiddle.co)
    QueryParameterUrlPageParser(
        provider_id=UUID("f0b94471-dbf4-4cb0-ae1d-f489e8b39fc1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\.php\?"),
        parameter="gsc.page",
    ),
    # Provider: eCRATER (ecrater.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("72d69cbf-f7f2-4bd6-86f5-e108df7faf53"),
        url_pattern=re_compile(r"^https?://[^/]+/filter\.php\?"),
        parameter="srn",
    ),
    # Provider: Eurovision Song Contest (eurovision.tv)
    QueryParameterUrlPageParser(
        provider_id=UUID("baeb5c1b-e668-4bdd-bc56-2beb43788b8f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="page",
    ),
    # Provider: Sportsala (sportsala.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("608207c6-fa62-4133-b3cf-0c292fdf39a3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Ah Me (ah-me.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("83027581-7f28-4e93-9749-5c4ddaac3af6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page[0-9]+\.html"),
        segment=3,
        remove_pattern=re_compile(r"page|\.html$"),
    ),
    PathSegmentUrlPageParser(
        provider_id=UUID("83027581-7f28-4e93-9749-5c4ddaac3af6"),
        url_pattern=re_compile(r"^https?://[^/]+/pics/search/[^/]+/[0-9]+"),
        segment=4,
    ),
    # Provider: stock.xchng (sxc.hu)
    QueryParameterUrlPageParser(
        provider_id=UUID("490daf6a-dfc6-4478-bed9-a9ecaec189bb"),
        url_pattern=re_compile(r"^https?://[^/]+/browse\.phtml\?"),
        parameter="p",
    ),
    # Provider: Mayo Clinic (mayoclinic.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("67a8bb04-9df6-42d2-bb37-d569235f386b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search-results\?"),
        parameter="page",
    ),
    # Provider: Shopping.com (shopping.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("4ea817c7-02bc-46e3-999a-229061f04ab9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="page",
    ),
    # Provider: Porn 24 TV (porn24.tv)
    PathSegmentUrlPageParser(
        provider_id=UUID("24577ff5-b90c-4417-a1f3-df3d177800ee"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+/[0-9]+\.html"),
        segment=4,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: Pornhost (pornhost.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("ff7883ef-f22f-4151-aa7f-3f4b2193311d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="start",
    ),
    # Provider: TubeREL (tuberel.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("597039e4-1117-40b8-8877-b3e7a8402dde"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+/[0-9]+"),
        segment=4,
    ),
    # Provider: السبورة (alsbbora.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("3137763d-5b52-4673-ba8b-3a9d44d99689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="page",
    ),
    # Provider: 楚天视界 (ct10000.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("a8973cf2-a22c-4f9f-911c-86032ccf7baa"),
        url_pattern=re_compile(r"^https?://[^/]+/s\.html\?"),
        parameter="page",
    ),
    # Provider: SlidePlayer (slideplayer.com.br)
    QueryParameterUrlPageParser(
        provider_id=UUID("a28f1776-0461-4df2-9445-e11db8b2a689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="page",
    ),
    # Provider: zooplus (zooplus.hu)
    QueryParameterUrlPageParser(
        provider_id=UUID("731c5c13-9e57-45ca-a0e0-affabcac9448"),
        url_pattern=re_compile(r"^https?://[^/]+/search/results\?"),
        parameter="p",
    ),
    # Provider: Autoproyecto (autoproyecto.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("94ce6cb1-2a0e-49b0-bd60-f773625832a8"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: MarkosWeb (markosweb.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("5c60e797-b0b9-4d8b-8b88-e79c027a0912"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="qsc.page",
    ),
    # Provider: پارسی جو (parsijoo.ir)
    QueryParameterUrlPageParser(
        provider_id=UUID("fc72f433-1823-40fb-8656-553cd5fe8111"),
        url_pattern=re_compile(r"^https?://[^/]+/*.\?"),
        parameter="page",
    ),
    # Provider: مخزن (m5zn.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("c2f50eb0-14d4-41bf-ae15-7a2d276f253f"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Kelkoo (kelkoo.de)
    QueryParameterUrlPageParser(
        provider_id=UUID("d4a76357-195d-40e0-9fa2-4cc467ed7b00"),
        url_pattern=re_compile(r"^https?://[^/]+/(search|suche)\?"),
        parameter="page",
    ),
    # Provider: Shentai (shentai.org)
    PathSegmentUrlPageParser(
        provider_id=UUID("9daa83ed-a31c-4903-92d5-1592610d6b10"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Hot Sale (hotsale.com.ar)
    PathSegmentUrlPageParser(
        provider_id=UUID("1ec7c017-4661-4238-8679-c484b50a4fc8"),
        url_pattern=re_compile(r"^https?://[^/]+/ofertas/[0-9]+\?"),
        segment=2,
    ),
    # Provider: GlobalSpec (globalspec.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/article/search"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/all"),
        parameter="page",
    ),
    QueryParameterUrlPageParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/reference"),
        parameter="page",
    ),
    # Provider: Petal Search (petalsearch.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("c9223006-4a0e-479f-8445-7847a48ea9ed"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="pn",
    ),
    # Provider: Comboios de Portugal (cp.pt)
    QueryParameterUrlPageParser(
        provider_id=UUID("465eccde-a010-443b-9c67-29bfd1064594"),
        url_pattern=re_compile(r"^https?://[^/]+/passageiros/pt/resultados-pesquisa\?"),
        parameter="p",
    ),
    # Provider: Badjojo (badjojo.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("9753b480-b174-4bdd-a7b9-385b28a38fe7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="p",
    ),
    # Provider: International Consortium of Investigative Journalists (icij.org)
    PathSegmentUrlPageParser(
        provider_id=UUID("7f3d4d7e-8db4-4c5f-b4ad-0abaaf2662ca"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Adzuna (adzuna.co.uk)
    QueryParameterUrlPageParser(
        provider_id=UUID("6ea49e2e-163c-4dd8-a8aa-bc6b75cf2274"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs/search\?"),
        parameter="p",
    ),
    # Provider: The Gudda (thegudda.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("433d38b3-a881-41a6-921c-2641c6bbc14c"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: Jet Boobs (jetboobs.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("69422465-7293-4352-b0f1-6c758e3ba113"),
        url_pattern=re_compile(r"^https?://[^/]+/en/[0-9]+/[^/]+/[0-9]+\.html"),
        segment=4,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: Wazap! (wazap.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("1a9fcf03-39a6-42a0-ab49-1b53b1a57f41"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.wz\?"),
        parameter="p",
    ),
    # Provider: My Chic Consulting (mychicconsulting.es)
    PathSegmentUrlPageParser(
        provider_id=UUID("aa896c31-3ca1-471d-a869-caa10bff530f"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: KidzSearch (kidzsearch.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("83aa1880-9a2c-4f04-92c1-9afb205c9eed"),
        url_pattern=re_compile(
            r"^https?://[^/]+/kz(?:image|video|facts|wiki|news|game|app)?search\.php\?"
        ),
        parameter="gsc.page",
    ),
    # Provider: args.me (args.me)
    QueryParameterUrlPageParser(
        provider_id=UUID("05fb19ff-b8c4-4b47-b18a-4493e2df57f4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="page",
    ),
    # Provider: Bielefeld Academic Search Engine (base-search.net)
    QueryParameterUrlPageParser(
        provider_id=UUID("f89ecd33-9ced-493e-939d-3e99d578bee4"),
        url_pattern=re_compile(r"^https?://[^/]+/Search/Results\?"),
        parameter="page",
    ),
    # Provider: ChatNoir (chatnoir.eu)
    QueryParameterUrlPageParser(
        provider_id=UUID("e9a0e2d3-390f-4832-9805-40067771b1bf"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="p",
    ),
    # Provider: Digital Genie (genieknows.com)
    PathSegmentUrlPageParser(
        provider_id=UUID("2fcabf98-a825-4cf6-8df2-b2be82ca705a"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: leit.is (leit.is)
    QueryParameterUrlPageParser(
        provider_id=UUID("98cf9ba4-a44e-4075-ac18-4d9f09767276"),
        url_pattern=re_compile(r"^https?://[^/]+/(leita|company_search)\?"),
        parameter="page",
    ),
    # Provider: Miner (miner.hu)
    PathSegmentUrlPageParser(
        provider_id=UUID("13fc4e4d-b2fb-441d-a434-647989fafc7a"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        segment=2,
    ),
    # Provider: mySimon (mysimon.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("cb2cd314-9890-4fed-9643-5cbfaffbc698"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\?"),
        parameter="p",
    ),
    # Provider: Newslookup (newslookup.com)
    QueryParameterUrlPageParser(
        provider_id=UUID("d00f4edc-801d-4aee-99ca-289636ac7b7e"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        parameter="p",
    ),
    # Provider: NexTag (nextag.de)
    QueryParameterUrlPageParser(
        provider_id=UUID("89b8efa1-8a1e-4928-958b-8f7fad8efacc"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\/products\?"),
        parameter="page",
    ),
)
