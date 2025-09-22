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
from archive_query_log.namespaces import NAMESPACE_URL_QUERY_PARSER
from archive_query_log.orm import (
    Capture,
    Serp,
    InnerCapture,
    InnerParser,
)
from archive_query_log.parsers.utils import clean_text
from archive_query_log.parsers.utils.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.utils.time import utc_now


class UrlQueryParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_URL_QUERY_PARSER, self.model_dump_json())

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

    def is_applicable(self, capture: Capture) -> bool:
        # Check if provider matches.
        if self.provider_id is not None and self.provider_id != capture.provider.id:
            return False

        # Check if URL matches pattern.
        if self.url_pattern is not None and not self.url_pattern.match(
            capture.url.encoded_string()
        ):
            return False
        return True

    @abstractmethod
    def parse(self, capture: Capture) -> str | None: ...


class QueryParameterUrlQueryParser(UrlQueryParser):
    parameter: str

    def parse(self, capture: Capture) -> str | None:
        query = parse_url_query_parameter(self.parameter, capture.url)
        if query is None:
            return None
        return clean_text(
            text=query,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


class FragmentParameterUrlQueryParser(UrlQueryParser):
    parameter: str

    def parse(self, capture: Capture) -> str | None:
        fragment = parse_url_fragment_parameter(self.parameter, capture.url)
        if fragment is None:
            return None
        return clean_text(
            text=fragment,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


class PathSegmentUrlQueryParser(UrlQueryParser):
    segment: int

    def parse(self, capture: Capture) -> str | None:
        segment = parse_url_path_segment(self.segment, capture.url)
        if segment is None:
            return None
        return clean_text(
            text=segment,
            remove_pattern=self.remove_pattern,
            space_pattern=self.space_pattern,
        )


def _parse_serp_url_query_action(
    config: Config,
    capture: Capture,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        capture.url_query_parser is not None
        and capture.url_query_parser.should_parse is not None
        and not capture.url_query_parser.should_parse
    ):
        return

    for parser in URL_QUERY_PARSERS:
        if not parser.is_applicable(capture):
            continue
        url_query = parser.parse(capture)
        if url_query is None:
            # Parsing was not successful.
            continue
        serp = Serp(
            index=config.es.index_serps,
            id=capture.id,
            last_modified=utc_now(),
            archive=capture.archive,
            provider=capture.provider,
            capture=InnerCapture(
                id=capture.id,
                url=capture.url,
                timestamp=capture.timestamp,
                status_code=capture.status_code,
                digest=capture.digest,
                mimetype=capture.mimetype,
            ),
            url_query=url_query,
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
            url_page_parser=InnerParser(
                should_parse=True,
            ),
            url_offset_parser=InnerParser(
                should_parse=True,
            ),
            warc_query_parser=InnerParser(
                should_parse=True,
            ),
            warc_web_search_result_blocks_parser=InnerParser(
                should_parse=True,
            ),
        )
        yield serp.create_action()
        yield capture.update_action(
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield capture.update_action(
        url_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_query(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_captures)
    changed_captures_search: Search = (
        Capture.search(using=config.es.client, index=config.es.index_captures)
        .filter(~Term(url_query_parser__should_parse=False))
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_captures = changed_captures_search.count()
    if num_changed_captures > 0:
        changed_captures: Iterable[Capture] = changed_captures_search.params(
            size=size
        ).execute()

        changed_captures = tqdm(
            changed_captures,
            total=num_changed_captures,
            desc="Parsing URL query",
            unit="capture",
        )
        actions = chain.from_iterable(
            _parse_serp_url_query_action(config, capture)
            for capture in changed_captures
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed captures.")


URL_QUERY_PARSERS: Sequence[UrlQueryParser] = (
    # Provider: Google (google.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="for",
    ),
    # Provider: Google Scholar (scholar.google.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/scholar\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/citations\?"),
        parameter="mauthors",
    ),
    # Provider: YouTube (youtube.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b13b2543-adb4-4c80-92d2-c57ca7e21d76"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        parameter="search_query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("b13b2543-adb4-4c80-92d2-c57ca7e21d76"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search\?"),
        parameter="search_query",
    ),
    # Provider: Baidu (baidu.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/f\?"),
        parameter="kw",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="wd",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="word",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/sf/vsearch\?"),
        parameter="wd",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/cse/site\?"),
        parameter="q",
    ),
    # Provider: QQ (wechat.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.htm\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/?/search\.html\?"),
        parameter="ms_key",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("14c06b53-c6d9-4f8e-a4eb-912a141d23c7"),
        url_pattern=re_compile(r"^https?://[^/]+/x/search/\?"),
        parameter="q",
    ),
    # Provider: Facebook (facebook.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8615690c-a19b-4e08-b55f-31413557e6e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Tmall (tmall.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d539ccc8-2e10-4225-956f-596c7718b08a"),
        url_pattern=re_compile(r"^https?://[^/]+/search_product"),
        parameter="q",
    ),
    # Provider: Taobao (taobao.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("626875c0-2ecc-4e70-98c1-dcce8bbdaf20"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Yahoo! (yahoo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="p",
    ),
    # Provider: Amazon (amazon.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0508d4c9-9423-4e3b-8e15-267040100ae6"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="k",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("0508d4c9-9423-4e3b-8e15-267040100ae6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: JD.com (jd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7158c4f2-b1ae-4862-828d-5f8d46c3269f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="keyword",
    ),
    # Provider: 360 (360.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/i\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/ns\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce3da23a-fa5f-4d38-b3cd-81cbd6fed53a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Weibo (weibo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/pic\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/realtime\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/topic\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/user\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/video\?"),
        parameter="q",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/weibo/[^/]+"),
        segment=2,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("76114509-8086-47e9-8fac-c1d4707772f7"),
        url_pattern=re_compile(r"^https?://[^/]+/weibo\?"),
        parameter="q",
    ),
    # Provider: Reddit (reddit.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("46800332-216a-4dd0-8b1b-3502187d04a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Netflix (netflix.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("86c3d588-855f-498f-b078-1f186531d9f9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Vk.com (vk.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fedcc039-b257-4bb4-978e-2a43897e9bce"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="c[q]",
    ),
    # Provider: Microsoft (microsoft.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dae12f5e-3b1d-46ad-a8d8-1417b9c33128"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+-[a-z]+/search"),
        parameter="q",
    ),
    # Provider: CSDN (csdn.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8f00523a-226a-472b-b2da-ce782bce08a1"),
        url_pattern=re_compile(r"^https?://[^/]+/.*/search\?"),
        parameter="q",
    ),
    # Provider: Microsoft Bing (bing.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/news/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/shop\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/search\?"),
        parameter="q",
    ),
    # Provider: Twitter (twitter.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1f6b5bbd-e8a0-443b-abb0-1070b4c182e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Twitch (twitch.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0afc634d-3ae4-4019-a84a-abab73f63c51"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="term",
    ),
    # Provider: Zoom (zoom.us)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("2e7be331-813d-46da-930b-5d2310fd5c81"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search"),
        parameter="q",
    ),
    # Provider: eBay (ebay.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("aa9fc506-7932-4014-baa7-c4f3301906a4"),
        url_pattern=re_compile(r"^https?://[^/]+/([^?]+/)?i\.html\?"),
        parameter="_nkw",
    ),
    # Provider: Naver (naver.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        parameter="query",
    ),
    # Provider: AliExpress (aliexpress.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/w/wholesale"),
        parameter="SearchText",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("38c45272-16b0-41fb-84d1-7aa2b0bc79a2"),
        url_pattern=re_compile(r"^https?://[^/]+/wholesale"),
        parameter="SearchText",
    ),
    # Provider: Yandex (yandex.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/images/search"),
        parameter="text",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="text",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("6d1b6758-45fe-42e2-9f60-ec38558714bc"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search"),
        parameter="text",
    ),
    # Provider: LinkedIn (linkedin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("962ab074-1a32-4fed-a6b4-8db693cd1a23"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="keywords",
    ),
    # Provider: BongaCams (bongacams.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("936ddb10-649f-4757-b761-3205506725c7"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(female|male|couples|trans|new-models)/tags/[^/]+"
        ),
        segment=3,
    ),
    # Provider: Apple (apple.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4a0ba050-7e6f-4e6a-b50e-f3e378512f39"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("4a0ba050-7e6f-4e6a-b50e-f3e378512f39"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("4a0ba050-7e6f-4e6a-b50e-f3e378512f39"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: PornHub (pornhub.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("14d75ec8-5e59-415b-8eac-c155ac8f2184"),
        url_pattern=re_compile(r"^https?://[^/]+/video/search\?"),
        parameter="search",
    ),
    # Provider: Mail.ru (mail.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3620982d-10d2-4052-b2fb-b941da60c682"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="text",
    ),
    # Provider: StackOverflow (stackoverflow.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/questions/tagged/[^/]+"),
        segment=3,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("cdb6ab1e-e1db-47fc-a587-3b6283714d30"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: TribunNews (tribunnews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("88e85822-b891-41d4-93dc-da45db4af885"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: IMDb (imdb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("24998fe9-f9c7-4245-8647-3ef63e98deef"),
        url_pattern=re_compile(r"^https?://[^/]+/find\?"),
        parameter="q",
    ),
    # Provider: LiveJasmin (livejasmin.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("a65be6de-2caa-4928-82b4-d74f66ab4541"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(girls|boys)/[^/]+/.*Search"),
        segment=3,
    ),
    # Provider: Chaturbate (chaturbate.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e0fa9954-ddac-4afb-9183-9766f993b01a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="keywords",
    ),
    # Provider: Odnoklassniki.ru (ok.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("640f174b-c3ed-407e-9617-3bebb6b6c2d8"),
        url_pattern=re_compile(r"^https?://[^/]+/dk\?"),
        parameter="st.query",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("640f174b-c3ed-407e-9617-3bebb6b6c2d8"),
        url_pattern=re_compile(r"^https?://[^/]+/music/search/tracks/[^/]+"),
        segment=4,
    ),
    # Provider: XVideos (xvideos.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4c59f08a-c1a2-4dec-b2f2-3fa4aa3e95a9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="k",
    ),
    # Provider: GitHub (github.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3b3dcee8-bd28-4471-8b95-63361c3aeaa6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: CNN (cnn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c3e70d8e-b2e7-4b14-9104-374cd03185d2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Etsy (etsy.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1eb849c5-ab38-4202-936d-1d8cf6094025"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: xHamster (xhamster.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("7b739c60-648a-452f-a9ce-7c50a237a25f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Sogou (sogou.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/pics\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/result\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/sogou\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/v\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("565cd43a-5921-4214-b7e5-0bcd7efb42fa"),
        url_pattern=re_compile(r"^https?://[^/]+/weixin\?"),
        parameter="query",
    ),
    # Provider: Canva (canva.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d38a1c5d-8b0d-492d-81ee-aa3a7e22cc75"),
        url_pattern=re_compile(r"^https?://[^/]+/design/play\?"),
        parameter="layoutQuery",
    ),
    # Provider: Tumblr (tumblr.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("70c8a490-5500-4421-9657-f5b686894a25"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: ESPN (espn.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("481dec1e-8af8-40cc-b17a-86b2a95ec778"),
        url_pattern=re_compile(r"^https?://[^/]+/search/_/q/[^/]+"),
        segment=4,
    ),
    # Provider: Instructure (instructure.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ad67b828-d658-4109-833e-8614728b5936"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search_api_fulltext",
    ),
    # Provider: Indeed (indeed.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="q",
    ),
    # Provider: Roblox (roblox.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("22396243-6004-451e-a309-2316926f1e4a"),
        url_pattern=re_compile(r"^https?://[^/]+/(catalog\/browse.aspx\?|discover)"),
        parameter="Keyword",
    ),
    # Provider: Imgur (imgur.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("792e5262-389c-41d7-b6ce-2189e41e3da2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Flipkart (flipkart.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("35c5c1ae-aca4-41dc-87e4-17956a50afdb"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Fandom (fandom.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f946b946-88aa-4aa9-a7e9-3bd1ab43e897"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("f946b946-88aa-4aa9-a7e9-3bd1ab43e897"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+\?"),
        parameter="s",
    ),
    # Provider: BBC (bbc.co.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("40227760-efc6-4290-a7eb-fd1e2dba500f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: detikcom (detik.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("060ad729-c126-4cdd-bb41-810f747aba86"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: Booking.com (booking.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c31f59-d709-4895-b406-42e5d0025e2a"),
        url_pattern=re_compile(r"^https?://[^/]+/searchresults"),
        parameter="ss",
    ),
    # Provider: cnblogs (cnblogs.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/blogpost\?"),
        parameter="Keywords",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/kb\?"),
        parameter="Keywords",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/news\?"),
        parameter="Keywords",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s/question\?"),
        parameter="Keywords",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ad856c5-b84e-4277-84bb-aa81deb4c8a3"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="w",
    ),
    # Provider: Walmart (walmart.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("53146b84-b82b-4b36-960e-d95cc73863b5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Alibaba (alibaba.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("38a0c350-e40b-4bde-b0ca-2760c49247bb"),
        url_pattern=re_compile(r"^https?://[^/]+/trade/search\?"),
        parameter="SearchText",
    ),
    # Provider: Freepik (freepik.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bd284b5c-ca5c-4614-af84-e0f74b069726"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: National Institutes of Health (nih.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e0421c49-101f-4e66-8318-b47ae737189b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Salesforce (salesforce.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("11c32f67-a615-4508-9b3a-45ca221f33b0"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Stack Exchange (stackexchange.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a5be09d9-0e19-4a2d-80ce-b8d78f768465"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Daum (daum.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("10b57fbe-76cc-402f-b7ca-308b8cf3d300"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Udemy (udemy.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("72941c35-661e-40de-8a6b-0a5eb1ee1b90"),
        url_pattern=re_compile(r"^https?://[^/]+/courses/.*search\-query"),
        parameter="search-query",
    ),
    # Provider: Craigslist (craigslist.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0161ce52-a862-492e-a6e7-08088554a892"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="query",
    ),
    # Provider: Avito (avito.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("49405df5-bac8-4d07-af32-e336aa82d6f3"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+\?"),
        parameter="q",
    ),
    # Provider: Grid.ID (grid.id)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4e80b4eb-9391-4079-ad41-224938f5674a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: DuckDuckGo (duckduckgo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3725fae7-edf7-4243-bcce-e5ccb615ae76"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3725fae7-edf7-4243-bcce-e5ccb615ae76"),
        url_pattern=re_compile(r"^https?://[^/]+/d\.js\?"),
        parameter="q",
    ),
    # Provider: Alibaba Cloud (aliyun.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a1325524-1903-42e5-886a-721e244c5280"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="k",
    ),
    # Provider: TikTok (tiktok.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5a0d693e-b44c-4bab-85eb-a82084d4036c"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Shutterstock (shutterstock.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b62cb1b5-9112-4fe3-b4b3-361c0cb652de"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("b62cb1b5-9112-4fe3-b4b3-361c0cb652de"),
        url_pattern=re_compile(r"^https?://[^/]+/(editorial|video|music)/search/[^/]+"),
        segment=3,
    ),
    # Provider: XNXX.COM (xnxx.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b0b23e40-4e29-4bed-b4cc-34e4c7ec1f6c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: GOME (gome.com.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("72e8a452-5add-4891-ba97-5e716e9a038d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="question",
    ),
    # Provider: W3Schools (w3schools.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("5802cad3-1a6f-46a8-b646-0cd8b49c4db5"),
        url_pattern=re_compile(r"^https?://[^/]+/.*#gsc"),
        parameter="gsc.q",
    ),
    # Provider: ResearchGate (researchgate.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("093ed74c-073a-47a2-b200-5b78386ca60d"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: Tokopedia (tokopedia.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b6ff76de-e4b8-4a75-b3a2-dd9a522e6969"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Youm7 (youm7.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("abc4dab5-7c5e-4f4b-bd3c-062c0f444281"),
        url_pattern=re_compile(r"^https?://[^/]+/(H|h)ome/Search\?"),
        parameter="allwords",
        space_pattern=re_compile(r"\+"),
    ),
    # Provider: Globo (globo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4fe3c697-baff-4118-950b-378623d0b761"),
        url_pattern=re_compile(r"^https?://[^/]+/busca"),
        parameter="q",
    ),
    # Provider: SlideShare (slideshare.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("248a5485-79e6-46c7-882c-708fbd7f3d55"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: China Internet Information Center (china.com.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e904cce7-7ded-45fb-a614-db254cca9262"),
        url_pattern=re_compile(r"^https?://[^/]+/query"),
        parameter="kw",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e904cce7-7ded-45fb-a614-db254cca9262"),
        url_pattern=re_compile(r"^https?://[^/]+/news/query"),
        parameter="kw",
    ),
    # Provider: Varzesh 3 (varzesh3.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2dfd1b66-b936-4d6f-b0a7-286c8fe33ddc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: wikiHow (wikihow.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6ac3b5b2-5a16-41dd-99d6-c33e7a72f2fc"),
        url_pattern=re_compile(r"^https?://[^/]+/wikiHowTo\?"),
        parameter="search",
    ),
    # Provider: Bukalapak (bukalapak.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("6210e971-e05d-4195-b5ce-e83e7fb9c92c"),
        url_pattern=re_compile(r"^https?://[^/]+/products/s/[^/]+"),
        segment=3,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("6210e971-e05d-4195-b5ce-e83e7fb9c92c"),
        url_pattern=re_compile(r"^https?://[^/]+/products\?"),
        parameter="search[keywords]",
    ),
    # Provider: Ask.com (ask.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("24fb5290-44aa-40e4-8272-0126a74d86cd"),
        url_pattern=re_compile(r"^https?://[^/]+/web\?"),
        parameter="q",
    ),
    # Provider: Intuit (intuit.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c00b9bad-20ad-43df-9a79-16aad0bb87c0"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="search_term",
    ),
    # Provider: US Postal Service (usps.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f85d9c64-e72a-4871-a8fd-73b9d5acd0d5"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="keyword",
    ),
    # Provider: Steam (steampowered.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dcb53102-bc2f-4a57-b6b8-1ac584a76131"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="term",
    ),
    # Provider: Airbnb (airbnb.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("c5700a20-0449-4743-b8d9-d48a0390ea72"),
        url_pattern=re_compile(r"^https?://[^/]+/s/[^/]+"),
        segment=2,
    ),
    # Provider: Bank of America (bankofamerica.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5c611594-b1bc-4118-9ccd-339ee03b0e21"),
        url_pattern=re_compile(r"^https?://[^/]+/global-search-public"),
        parameter="state",
    ),
    # Provider: Wikimedia (wikisource.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        parameter="search",
    ),
    # Provider: Blackboard (blackboard.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dec84fa8-fa38-407c-9ada-043441a21786"),
        url_pattern=re_compile(r"^https?://[^/]+/site-search\?"),
        parameter="q",
    ),
    # Provider: Rambler (rambler.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5498178c-319e-4ccd-af98-e4c61476bea7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Investopedia (investopedia.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2ba78774-eb8f-4fe2-80d5-16379cb3fe30"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 9GAG (9gag.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7e7db9b7-e15c-4172-98c8-0198031b983f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Chegg (chegg.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d5c2ded0-1a93-4ad2-9c9b-dcdaf1491a1d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Kakao (kakao.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("affade1b-1e35-40b8-8fb8-0ff133250713"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Glassdoor (glassdoor.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d04dfca3-c90e-4b26-a2d2-d466b1717a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/Search/"),
        parameter="keyword",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d04dfca3-c90e-4b26-a2d2-d466b1717a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/Job/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"\.htm$"),
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d04dfca3-c90e-4b26-a2d2-d466b1717a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/Salaries/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"\.htm$"),
    ),
    # Provider: Naukri.com (naukri.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2bc57145-7373-42fa-9268-b6cff3e22a92"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+-jobs\?"),
        parameter="k",
    ),
    # Provider: SourceForge (sourceforge.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f2693944-32e9-4976-973e-23947f56d10a"),
        url_pattern=re_compile(r"^https?://[^/]+/(directory|software)"),
        parameter="q",
    ),
    # Provider: WebMD (webmd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b9df840d-7f5f-4ed1-9619-b68bd7540e5f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search_results"),
        parameter="query",
    ),
    # Provider: Youdao (youdao.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("456d491e-61b1-4485-a2f2-c603c05d47c8"),
        url_pattern=re_compile(r"^https?://[^/]+/result\?"),
        parameter="word",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("456d491e-61b1-4485-a2f2-c603c05d47c8"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: DBS Bank (dbs.com.sg)
    QueryParameterUrlQueryParser(
        provider_id=UUID("44575a2d-0431-4e3e-9f33-4bd20a2503bd"),
        url_pattern=re_compile(r"^https?://[^/]+/searchresults\.page"),
        parameter="q",
    ),
    # Provider: Seznam (seznam.cz)
    QueryParameterUrlQueryParser(
        provider_id=UUID("22eba7be-a91c-4b21-80d3-0e837126f203"),
        url_pattern=re_compile(r"^https?://[^/]+/?(obrazky\/)?\?"),
        parameter="q",
    ),
    # Provider: ChinaZ.com (chinaz.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("29db0c25-5d1f-4eb9-8014-e77b36df3a85"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.aspx\?"),
        parameter="keyword",
    ),
    # Provider: Ecosia (ecosia.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/images\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/news\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("7a88141f-90b9-49a5-9083-9a922038c16c"),
        url_pattern=re_compile(r"^https?://[^/]+/videos\?"),
        parameter="q",
    ),
    # Provider: Rediff.com (rediff.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("203da776-b325-4ece-85ff-297ce1c75919"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("203da776-b325-4ece-85ff-297ce1c75919"),
        url_pattern=re_compile(r"^https?://[^/]+/product/[^/]+"),
        segment=2,
    ),
    # Provider: goo (goo.ne.jp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("183282c3-ff26-429b-ae25-f6dbfe90e94e"),
        url_pattern=re_compile(r"^https?://[^/]+/web\.jsp\?"),
        parameter="MT",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("183282c3-ff26-429b-ae25-f6dbfe90e94e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="MT",
    ),
    # Provider: Turkey e-government (turkiye.gov.tr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("541bc6bc-661e-4207-bc18-42e44f50090f"),
        url_pattern=re_compile(r"^https?://[^/]+/arama\?"),
        parameter="aranan",
    ),
    # Provider: DC Inside (dcinside.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("a4f676fa-4b8a-48c6-9879-45e95c75c283"),
        url_pattern=re_compile(r"^https?://[^/]+/combine/q/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("a4f676fa-4b8a-48c6-9879-45e95c75c283"),
        url_pattern=re_compile(r"^https?://[^/]+/post/sort/[^/]+/q/[^/]+"),
        segment=5,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("a4f676fa-4b8a-48c6-9879-45e95c75c283"),
        url_pattern=re_compile(r"^https?://[^/]+/post/p/[^/]+/sort/[^/]+/q/[^/]+"),
        segment=7,
    ),
    # Provider: GOV.UK (gov.gov.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0cc990e6-376f-45cb-be16-4f6ade723e76"),
        url_pattern=re_compile(r"^https?://[^/]+/search/all\?"),
        parameter="keywords",
    ),
    # Provider: El Fagr (elfagr.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a5e294b8-3a84-4662-8318-9983be7e2c54"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="w",
    ),
    # Provider: Bandcamp (bandcamp.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce34adf9-ab2f-4715-9823-3afd19d34eaa"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Allrecipes (allrecipes.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("57c314b1-5625-449a-bb3c-b4fc4e3b1215"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 123RF (123rf.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("c3184333-c73d-442f-9d7f-5f0968e82fcb"),
        url_pattern=re_compile(r"^https?://[^/]+/stock-photo/[^/]\.html"),
        segment=2,
        remove_pattern=re_compile(r"\.html$"),
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("c3184333-c73d-442f-9d7f-5f0968e82fcb"),
        url_pattern=re_compile(r"^https?://[^/]+/lizenzfreie-bilder/[^/]\.html"),
        segment=2,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: FiveThirtyEight (fivethirtyeight.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("be396697-ee09-4c67-bf41-4430acb70575"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Stanford University (stanford.edu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a8924fe-b16c-44ea-b11d-6b7ee8e081a2"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a8924fe-b16c-44ea-b11d-6b7ee8e081a2"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a8924fe-b16c-44ea-b11d-6b7ee8e081a2"),
        url_pattern=re_compile(r"^https?://[^/]+/searchview"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a8924fe-b16c-44ea-b11d-6b7ee8e081a2"),
        url_pattern=re_compile(r"^https?://[^/]+/service\.websearch\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a8924fe-b16c-44ea-b11d-6b7ee8e081a2"),
        url_pattern=re_compile(r"^https?://[^/]+/linux\?"),
        parameter="query",
    ),
    # Provider: Smartsheet (smartsheet.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("f5dbd09d-f322-418a-bc3b-e8ddf6716eff"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Caisse d'allocations familiales (caf.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bcfa6bc3-f4da-4751-bf70-4a2cbf28d443"),
        url_pattern=re_compile(r"^https?://[^/]+/allocataires/recherche\?"),
        parameter="search",
    ),
    # Provider: 4shared (4shared.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("7dc71675-3245-432f-a6b9-cf5c4ba004e0"),
        url_pattern=re_compile(r"^https?://[^/]+/web/q"),
        parameter="query",
    ),
    # Provider: Lifewire (lifewire.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ee41e2e-0ce0-4b05-b94a-86778d826d6a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: TD Ameritrade (tdameritrade.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("40dead1b-05ca-4a38-ac51-88392f851a40"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results\.html\?"),
        parameter="q",
    ),
    # Provider: SFGATE (sfgate.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9eda3ef4-dd23-440c-935a-7061be9f8b5c"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: Gobierno de México (gob.mx)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7bd87442-ae0a-4896-8b2b-4c387c6d5e5c"),
        url_pattern=re_compile(r"^https?://[^/]+/busqueda\?"),
        parameter="gsc.q",
    ),
    # Provider: E*TRADE (etrade.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fb126acc-7567-4387-9be4-97d57855ecb0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: VectorStock (vectorstock.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("7f787607-7271-49ad-bc8a-21af5ed922e8"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(royalty-free-vectors|free-vectors)/[^/]+-vectors(-page_[0-9]+)?"
        ),
        segment=2,
        remove_pattern=re_compile(r"-vectors$|-vectors-page_[0-9]+$"),
        space_pattern=re_compile(r"-"),
    ),
    # Provider: FMovies (fmovies.wtf)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d639b0d6-181d-449f-98e2-9d64d823f076"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="keyword",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("d639b0d6-181d-449f-98e2-9d64d823f076"),
        url_pattern=re_compile(r"^https?://[^/]+/ajax/film/search\?"),
        parameter="keyword",
    ),
    # Provider: BigGo (biggo.com.tw)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4cdad56-71d6-4887-8aeb-4ebd004e23e0"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="q",
    ),
    # Provider: Sage Publications (sagepub.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("a1e98542-11e3-4a4f-8eae-4067dbba2e65"),
        url_pattern=re_compile(
            r"^https?://[^/]+/[a-z]+-[a-z]+/[a-z]+/(content|events|product)/[^/]+"
        ),
        segment=4,
    ),
    # Provider: Tasnim News (tasnimnews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("43f49c54-7325-44a6-94e6-064ba6650506"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/search\?"),
        parameter="query",
    ),
    # Provider: CyberLeninka (cyberleninka.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bafe8c81-483c-4155-9abe-0dca1990429d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Hang Seng Bank (hangseng.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("41aa6c75-52e5-438b-8f46-fe9daaa904b3"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+-[a-z]+/search"),
        parameter="searchString",
    ),
    # Provider: LG (lg.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/br/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/cl/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/cn/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/de/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/eastafrica/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/iraq_ar/catalogsearch"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/mx/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/result\?"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/uk/search"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9d219b4-2835-44a0-926b-15ebbf4aef6b"),
        url_pattern=re_compile(r"^https?://[^/]+/us/search"),
        parameter="q",
    ),
    # Provider: Semantic Scholar (semanticscholar.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1053663b-2f2a-4df6-aa54-2af7f69b0747"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: NSW Government (nsw.gov.au)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5ce5e859-95ec-4f7b-b5de-fcc2ab4f099e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: ZDF (zdf.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5d549740-cca4-4365-9be8-f089cc5d6327"),
        url_pattern=re_compile(r"^https?://[^/]+/suche\?"),
        parameter="q",
    ),
    # Provider: PosterMyWall (postermywall.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("37d2a649-5a7f-4a0c-ada7-05551694f9d9"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.php/posters/search\?"),
        parameter="s",
    ),
    # Provider: Jagran Josh (jagranjosh.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("075dfb0b-4679-4de6-bade-d37fb4101b2f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: University of California, Berkeley (berkeley.edu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ca0de211-c1e5-434b-9526-6fde1cf947c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Got Porn (gotporn.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f0e0f967-ba27-458e-8841-c420c5903ae2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("f0e0f967-ba27-458e-8841-c420c5903ae2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Daily Post Nigeria (dailypost.ng)
    QueryParameterUrlQueryParser(
        provider_id=UUID("af87718a-4c84-4e03-9110-718f757fba65"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Pennsylvania State University (psu.edu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("56bcd5fe-4f51-4c3f-a5e2-edb7dd159659"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: Akhbar el-Yom (akhbarelyom.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("64a1fd1d-caae-4c88-b76a-17193efc6df3"),
        url_pattern=re_compile(r"^https?://[^/]+/News/Search"),
        parameter="query",
    ),
    # Provider: Prensa Libre (prensalibre.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1863e6b9-c89f-489d-a28e-44eaa8bcabe0"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: INDOSPORT (indosport.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4bce288e-c72a-4910-88fc-f784561d85e5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Izvestia (iz.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f9132815-c4aa-4c54-b177-62e8971f5c93"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="text",
    ),
    # Provider: Worldstarhiphop (worldstarhiphop.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("630a2ad0-43ec-44fa-9897-cb91388bdb64"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/search\.php"),
        parameter="s",
    ),
    # Provider: Virgilio (virgilio.it)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b64b701b-eb4a-41ee-add5-f344fe720808"),
        url_pattern=re_compile(r"^https?://[^/]+/ricerca\?"),
        parameter="qs",
    ),
    # Provider: SAPO (sapo.pt)
    QueryParameterUrlQueryParser(
        provider_id=UUID("be2ffd65-ef03-45ed-8618-c4ae06f39035"),
        url_pattern=re_compile(r"^https?://[^/]+/pesquisa"),
        parameter="q",
    ),
    # Provider: Idealo (idealo.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ab9b092a-9c68-4988-a82d-6360a85e59a0"),
        url_pattern=re_compile(
            r"^https?://[^/]+/preisvergleich/MainSearchProductCategory(/100I16-[0-9]+)?\.html\?"
        ),
        parameter="q",
    ),
    # Provider: The Balance (thebalancecareers.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("be1843b8-9091-46cc-bc00-af8b466889ee"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Digital Photography Review (dpreview.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("04c33826-d8f2-453f-b272-216004cf7221"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("04c33826-d8f2-453f-b272-216004cf7221"),
        url_pattern=re_compile(r"^https?://[^/]+/videos"),
        parameter="query",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("04c33826-d8f2-453f-b272-216004cf7221"),
        url_pattern=re_compile(r"^https?://[^/]+/products/search/[^/]+"),
        segment=3,
    ),
    # Provider: TnaFilx (tnaflix.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c092b9b8-70ac-4158-ba8c-2943a7364fc8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="what",
    ),
    # Provider: Las2Orillas (las2orillas.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d9e3608c-f36d-4aab-9e9c-9045625085a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Excite (excite.co.jp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3721d489-4632-416e-9c68-a522e86a8806"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3721d489-4632-416e-9c68-a522e86a8806"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="q",
    ),
    # Provider: AniWave (9anime.gs)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3b594398-ba2d-444a-bbb2-a0d931ae0c9a"),
        url_pattern=re_compile(r"^https?://[^/]+/filter\?"),
        parameter="keyword",
    ),
    # Provider: Wetter.com (wetter.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("96c1e411-7984-4b0d-8a49-0bfea78ad4ec"),
        url_pattern=re_compile(r"^https?://[^/]+/suche"),
        parameter="q",
    ),
    # Provider: TechTudo (techtudo.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7857c8c6-7983-4005-839e-f09d68f4e087"),
        url_pattern=re_compile(r"^https?://[^/]+/busca"),
        parameter="q",
    ),
    # Provider: Books.com.tw (books.com.tw)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b3f58a77-6b8f-48d0-9468-c9f7d6b6c4f8"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Kaiser Permanente (kaiserpermanente.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7ff87c5b-f30d-4816-8805-f08746e2aba2"),
        url_pattern=re_compile(r"^https?://[^/]+/pages/search\?"),
        parameter="query",
    ),
    # Provider: Le360 (le360.ma)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b36c0344-253a-43e2-bd6a-ae02b6194111"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche/[^/]+"),
        segment=2,
    ),
    # Provider: Euronews (euronews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("638a0885-33f0-4b3b-9920-3f8bc9bde235"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: University of Toronto (utoronto.ca)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b075bc97-ce48-430e-84f7-e3aa080c675a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="gsc.q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("b075bc97-ce48-430e-84f7-e3aa080c675a"),
        url_pattern=re_compile(r"^https?://[^/]+/news/searchnews\?"),
        parameter="query",
    ),
    # Provider: CCM (commentcamarche.net)
    PathSegmentUrlQueryParser(
        provider_id=UUID("5cb93699-fd67-40f7-81a3-aa1324967c3f"),
        url_pattern=re_compile(r"^https?://[^/]+/s/[^/]+"),
        segment=2,
    ),
    # Provider: BIGLOBE (biglobe.ne.jp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c1a407bd-97e4-416a-875b-45a278c85116"),
        url_pattern=re_compile(r"^https?://[^/]+/cgi-bin/search"),
        parameter="search",
    ),
    # Provider: El Universal (eluniversal.com.mx)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d74ed8a4-062c-4998-bc32-936f56b3086a"),
        url_pattern=re_compile(r"^https?://[^/]+/resultados-busqueda/[^/]+"),
        segment=2,
    ),
    # Provider: Akurat.co (akurat.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("170a1b67-ea94-44ef-88b5-7fc79690f6a8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Monster (monster.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("42dda8bb-1e26-4cae-96af-f4ec1d489ddc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs/search\?"),
        parameter="q",
    ),
    # Provider: Sportzwiki (sportzwiki.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2fd7cfb3-ce38-4395-a68a-c9a1c892792d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Arabi21 (arabi21.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5e7fc1f2-c62b-4e44-8218-b18cd9438d90"),
        url_pattern=re_compile(r"^https?://[^/]+/[A-z]+\/*.Search\?"),
        parameter="keyword",
    ),
    # Provider: REI (rei.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7363663-70c4-4572-b29a-6fffc871d767"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Ci123 (ci123.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/all/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/ask/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/bbs/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/blog/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/baobao/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/qq/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/zhishi/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("d36c78ba-95e4-4f99-9f31-5c5110841b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/ping/[^/]+"),
        segment=2,
    ),
    # Provider: ThoughtCo (thoughtco.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bc6d9785-446e-4e4c-8875-fe9f9f5457b8"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: iefimerida (iefimerida.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("eec04272-449d-433e-8db0-6068bc39e4f9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: State of Washington (wa.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ac48eb32-9279-4e2a-ba30-f4097e2aa4c2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="gsc.q",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("ac48eb32-9279-4e2a-ba30-f4097e2aa4c2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: مستقل آنلاین (mostaghelonline.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1e3ae50c-0c23-443b-9bff-46a2a967941d"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/"),
        parameter="query",
    ),
    # Provider: اليمن العربي (elyamnelaraby.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2ba639c9-f738-47ff-bad7-484fd4d30048"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="w",
    ),
    # Provider: BEAUTY美人圈 (beauty321.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("69b905fe-319c-4155-99aa-26727d7fed88"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: FINN.no (finn.no)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d592ffa5-ca1b-4614-a7be-41c40bb08a13"),
        url_pattern=re_compile(r"^https?://[^/]+/bap/forsale/search\.html\?"),
        parameter="q",
    ),
    # Provider: AcFun (acfun.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5cdceac8-20bd-4b64-9c3f-3f76382ee11a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="keyword",
    ),
    # Provider: ArzDigital (arzdigital.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("52277d36-7baa-45ab-ade5-4822cfa63683"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="search",
    ),
    # Provider: Bangladesh Pratidin (bd-pratidin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d207f904-2e73-4d57-96b9-3d29229da369"),
        url_pattern=re_compile(r"^https?://[^/]+/home/search\?"),
        parameter="q",
    ),
    # Provider: 在线文档分享平台 (doc88.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("3d6e4bb0-9960-4cce-b2de-508fbfeed9c3"),
        url_pattern=re_compile(r"^https?://[^/]+/tag/[^/]+"),
        segment=2,
    ),
    # Provider: Masrawy (masrawy.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("58a741ba-c85f-43ad-8a3d-5472dde3a08e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/0/[^/]+"),
        segment=3,
    ),
    # Provider: PHP Group (php.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("263f91cb-f755-4579-8c9c-3975b4b551c7"),
        url_pattern=re_compile(r"^https?://[^/]+/manual-lookup\.php\?"),
        parameter="pattern",
    ),
    # Provider: تاروت رنگی (taroot-rangi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9f77dcac-7522-4be1-bc62-ca42b451b1de"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9f77dcac-7522-4be1-bc62-ca42b451b1de"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: अमर उजाला (amarujala.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d07b5be0-141a-436c-a22d-e8c9e3f76bd0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 亿席商务网 (yixiin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("183e4881-334e-435e-8c77-1e4e7e0ed6d6"),
        url_pattern=re_compile(r"^https?://[^/]+/sell/search\.php\?"),
        parameter="kw",
    ),
    # Provider: Julian Fashion (julian-fashion.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("94f6c5db-aef2-4d52-8f36-5bdaeead56da"),
        url_pattern=re_compile(r"https?://[^/]+/[a-z]+-[a-z]+/products/search\?"),
        parameter="searchKey",
    ),
    # Provider: Life Insurance Corporation of India (licindia.in)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5753309-d9d4-41f6-90df-b8f587064e85"),
        url_pattern=re_compile(r"^https?://[^/]+/Search-Results\?"),
        parameter="searchtext",
    ),
    # Provider: to10.gr (to10.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("89582999-4f2c-47d2-8730-3a13ce459e6a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: National Bank of Greece (nbg.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a7fdd97d-9508-4e3f-8727-2877b4661045"),
        url_pattern=re_compile(r"^https?://[^/]+/el/idiwtes/search-results\?"),
        parameter="q",
    ),
    # Provider: American Chemical Society (acs.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1f30153c-ca85-4929-bce6-46e940c77df6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: @nifty (nifty.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("391725ae-2645-43da-843a-993bfe42c79c"),
        url_pattern=re_compile(r"^https?://[^/]+/websearch/search\?"),
        parameter="q",
    ),
    # Provider: Sky News عربية (skynewsarabia.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("15d49216-18c7-4378-975d-a798a287e804"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Agenzia delle Entrate (agenziaentrate.gov.it)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5f87b72d-c092-40f0-a199-ae405e2f6390"),
        url_pattern=re_compile(r"^https?://[^/]+/portale/ricerca\?"),
        parameter="_it_smc_sogei_search_web_SogeiAdvancedSearchPortlet_keywords",
    ),
    # Provider: Know Your Meme (knowyourmeme.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9b322171-87d0-4360-baea-43c51ee1e21b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: FilGoal (filgoal.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cc1a2af1-2768-4daa-be5d-729303386223"),
        url_pattern=re_compile(r"^https?://[^/]+/search/filter\?"),
        parameter="keyword",
    ),
    # Provider: aShemaleTube (ashemaletube.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("6e61c33d-821f-4162-a8a7-973a4b502369"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: iXXX (ixxx.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f962ea26-a492-45a6-aa3d-1c1e18130b8b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("f962ea26-a492-45a6-aa3d-1c1e18130b8b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Programiz (programiz.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("6f4751b7-7056-47ae-aa0a-7620b10d7e2e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Careers360 (careers360.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b859c96c-d7e2-4651-8c06-f3c4a0bdbdd0"),
        url_pattern=re_compile(r"^https?://[^/]+/qna\?"),
        parameter="search",
    ),
    # Provider: MyFonts (myfonts.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fdb7f465-eb54-418e-8160-bb0c9351e5e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("fdb7f465-eb54-418e-8160-bb0c9351e5e7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="product_data[query]",
    ),
    # Provider: Monografias.com (monografias.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("75a2a416-8c91-4268-86c8-0415bd8a7134"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: World Bank (worldbank.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fc3a762d-0183-4c8a-99c1-15fad3aa4789"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="q",
    ),
    # Provider: Zulily (zulily.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("99666382-8f43-4e41-aaca-f9bea23c3bc7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Klix.ba (klix.ba)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5693c2a-98e5-4c3e-a4a2-a6eb72a4c890"),
        url_pattern=re_compile(r"^https?://[^/]+/pretraga\?"),
        parameter="q",
    ),
    # Provider: Entertainment Weekly (ew.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("532a4215-6830-43f8-bb2f-0ea89a4e51ea"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Warcraft Logs (warcraftlogs.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("686394f0-0119-4ea0-8dde-c6beb0b51d28"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="term",
    ),
    # Provider: Yellow Pages (yellowpages.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ef513c8b-dc83-45d5-a818-501d51778b73"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search_terms",
    ),
    # Provider: V LIVE (vlive.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b5857a7a-3cee-4bb0-9b56-e430c731e6c8"),
        url_pattern=re_compile(r"^https?://[^/]+/vstore/search\?"),
        parameter="query",
    ),
    # Provider: Answers (answers.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("30ede086-4156-4afe-9e7a-a96cc6b99a51"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Il Fatto Quotidiano (ilfattoquotidiano.it)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5481505-4757-4e54-b978-1bb9f1029c15"),
        url_pattern=re_compile(r"^https?://[^/]+/risultati-di-ricerca"),
        parameter="q",
    ),
    # Provider: Thumbzilla (thumbzilla.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("ad18a9a7-2154-4047-b054-f68554456c9e"),
        url_pattern=re_compile(r"^https?://[^/]+/tags/[^/]+"),
        segment=2,
    ),
    # Provider: ARY News (arynews.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("42530a28-ea0c-4816-9044-7159fb1ba877"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Sportbox.ru (sportbox.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("feff7d70-5a78-4b33-b8a1-d2c1feef0254"),
        url_pattern=re_compile(r"^https?://[^/]+/reports/search-content\?"),
        parameter="keys",
    ),
    # Provider: 19888.tv (19888.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("78a4d2a7-4fc6-4f14-b594-5e5cff741484"),
        url_pattern=re_compile(r"^https?://[^/]+/provide/title_[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"^title_|\.html$"),
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("78a4d2a7-4fc6-4f14-b594-5e5cff741484"),
        url_pattern=re_compile(r"^https?://[^/]+/chanpin/(p[0-9]+/)?\?"),
        parameter="title",
    ),
    # Provider: Info.com (info.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("793a56e2-018f-46b8-b690-98edcf0599c2"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="q",
    ),
    # Provider: IGGGAMES (igg-games.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("aebf22a2-21ff-4a13-aa83-5347ba271175"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Ubuntu (ubuntu.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1461eb45-4e0d-44ce-801a-e985e382a735"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: City of New York (nyc.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d4ccaab8-ec51-4392-bd09-83653703433f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/index\.page\?"),
        parameter="search-terms",
    ),
    # Provider: Nikkan Sports News (nikkansports.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2485e36d-6d00-43a3-ad08-44d0d6153219"),
        url_pattern=re_compile(r"^https?://[^/]+/search/index\.html\?"),
        parameter="q",
    ),
    # Provider: Navy Federal Credit Union (navyfederal.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5ec6c1c1-a526-4ecf-85ba-bb59ab2cc5bc"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="q",
    ),
    # Provider: Filmweb (filmweb.pl)
    QueryParameterUrlQueryParser(
        provider_id=UUID("65d6fc3c-79b6-4f1e-bc70-ef8213bf9327"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("65d6fc3c-79b6-4f1e-bc70-ef8213bf9327"),
        url_pattern=re_compile(r"^https?://[^/]+/films/search\?"),
        parameter="q",
    ),
    # Provider: Docker (docker.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8289c33f-8137-480e-9135-585b89048efe"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="_sf_s",
    ),
    # Provider: Watan News (watanserb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("965cc1ba-e630-4b32-997b-076c26407521"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: MovieWeb (movieweb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e20f5aea-5412-414d-adeb-aeab0e431fc9"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: LeagueOfGraphs (leagueofgraphs.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f14ff112-71ed-4d6d-ab95-75d308dc4dcf"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: BeSoccer (besoccer.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("bb0391df-d44f-40bb-b14a-b55ae392ea16"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Razer (razer.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("471b5c57-0f05-4161-88a0-6ef40b31c281"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: رؤيا الإخباري (royanews.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8210b75a-b44e-4fda-8e79-e794195990e0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="keyword",
    ),
    # Provider: Ulta Beauty (ulta.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("137e156a-1e4e-4d27-8855-6cf6752101a8"),
        url_pattern=re_compile(r"^https?://[^/]+/ulta/a/_/Ntt-[^/]+"),
        segment=4,
        remove_pattern=re_compile(r"^Ntt-"),
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("137e156a-1e4e-4d27-8855-6cf6752101a8"),
        url_pattern=re_compile(r"^https?://[^/]+/shop/[^/]+"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("137e156a-1e4e-4d27-8855-6cf6752101a8"),
        url_pattern=re_compile(r"^https?://[^/]+/brand/[^/]+"),
        segment=2,
        space_pattern=re_compile(r"-"),
    ),
    # Provider: Méeteo France (meteofrance.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b4453cf8-a287-46a3-af86-76dd22b50a2a"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche/[^/]+"),
        segment=2,
    ),
    # Provider: pc6 (pc6.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("593dd220-59e2-458c-9302-288800957037"),
        url_pattern=re_compile(r"^https?://[^/]+/cse/search\?"),
        parameter="s",
    ),
    # Provider: HaiBunda (haibunda.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cf2765be-6f7f-4ac4-acdb-c64368e2cd38"),
        url_pattern=re_compile(r"^https?://[^/]+/search(/[0-9]+)\?"),
        parameter="query",
    ),
    # Provider: opensubtitles.org (opensubtitles.org)
    PathSegmentUrlQueryParser(
        provider_id=UUID("a42005e6-01cf-4bc0-aa7a-34a536c5dd27"),
        url_pattern=re_compile(
            r"^https?://[^/]+/[a-z]+/search2/sublanguageid-[a-z]+/moviename-[^/]+"
        ),
        segment=4,
        remove_pattern=re_compile(r"moviename-"),
    ),
    # Provider: Thomann (thomann.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e18a3dc0-ad5c-41d5-832a-cb3dea6d1d37"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z+]/search_dir\.html\?"),
        parameter="sw",
    ),
    # Provider: Corporate Finance Institute (corporatefinanceinstitute.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b878b7ab-263b-42e4-b515-b78c315ff957"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("b878b7ab-263b-42e4-b515-b78c315ff957"),
        url_pattern=re_compile(r"^https?://[^/]+/resources/\?"),
        parameter="q",
    ),
    # Provider: 01net (01net.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cd13f7e1-5ee1-47ed-9f1a-e846c4f3b699"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("cd13f7e1-5ee1-47ed-9f1a-e846c4f3b699"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: all-free-download.com (all-free-download.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("748041bb-b786-46e8-a49a-e0b5c8c15869"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(free-vector|free-photos|font)/[^/]+\.html"
        ),
        segment=2,
        remove_pattern=re_compile(r"\.html$"),
        space_pattern=re_compile(r"-"),
    ),
    # Provider: Secret World (sworld.co.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("13e69ed2-5471-4bb2-934b-17fffedad5f6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Al-Anba (alanba.com.kw)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9eb7faab-9e71-4006-b2c0-04503c47361b"),
        url_pattern=re_compile(r"^https?://[^/]+/newspaper/search"),
        parameter="search",
    ),
    # Provider: Porn HD (pornhd.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("ea61cd89-315b-44fa-8760-e2ad7fdae326"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("ea61cd89-315b-44fa-8760-e2ad7fdae326"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Naijaloaded (naijaloaded.com.ng)
    QueryParameterUrlQueryParser(
        provider_id=UUID("83652197-a457-4683-a947-f1829de35f0c"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("83652197-a457-4683-a947-f1829de35f0c"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Wenxuecity (wenxuecity.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fe93cb3f-a8d9-4cb9-8bcc-f078590a405d"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="keyword",
    ),
    # Provider: Storyblocks (storyblocks.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("0029204e-8569-4918-bf53-bb8efd6272b5"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search/[^/]+"),
        segment=3,
    ),
    # Provider: SBNation (sbnation.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d5b954ec-5c68-47cd-87f9-b46b9b861d72"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Milenio (milenio.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8abcfe6e-c7c5-4c50-94a0-da0d21e85bc4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Fajar (fajar.co.id)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7be2229d-31d9-4e8b-a303-aeb425867aad"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Walla! (walla.co.il)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ece43d6d-77d7-4ced-a0a9-ca6f14e44e3e"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: iSLCollective (islcollective.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f9bfbc2a-23eb-47f1-ad69-41c2c8409b83"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search/[^/]+"),
        segment=3,
    ),
    # Provider: The Balance (thebalance.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dc454d1b-efd5-4b27-bc47-4c90a5e587eb"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Us Weekly (usmagazine.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c8f11400-e28b-4026-8119-4750550101d8"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results/\?"),
        parameter="_s",
    ),
    # Provider: Domestika (domestika.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f73d23a4-c351-4cda-aae8-c30d4a40ef0d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="query",
    ),
    # Provider: CareerBuilder (careerbuilder.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8b47e032-5be6-4ebb-8019-db5564a8a3b5"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="keywords",
    ),
    # Provider: University of Colorado Boulder (colorado.edu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("846117a8-c2b4-49d4-98d7-5f1a452865e3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="cse",
    ),
    # Provider: Clubic (clubic.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5069a18f-7423-4a16-b380-7cf173103db9"),
        url_pattern=re_compile(r"^https?://[^/]+/rechercher/\?"),
        parameter="q",
    ),
    # Provider: Search Multy (searchmulty.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ea3d56e5-3bc8-47b8-8a2b-ea8520b3a188"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: 20 Minutes (20minutes.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("644aee58-5293-4e13-bfe4-4b7e060bfa1f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: The Spruce (thespruce.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("95b0ef5d-524c-4363-a561-8c38bdf59358"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: npm (npmjs.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("01d257c4-7e9e-4568-9264-cfd20224b8d6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Ars Technica (arstechnica.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("20db5672-c078-45ec-b4da-045640261521"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: ProQuest (proquest.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("4cc8b413-3a37-4945-98e5-89e5a4c64940"),
        url_pattern=re_compile(r"^https?://[^/]+/results/[^/]+/[0-9]+"),
        segment=2,
    ),
    # Provider: Balenciaga (balenciaga.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("599fbe68-6798-46d8-b5e9-5dde475a6581"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: BoyFriendTv (boyfriendtv.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("e7628616-5f0d-455d-a70c-9fe0d156e7f0"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Deutsche Bank (deutsche-bank.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1a7181fb-183f-4531-9436-6ccd9f3967bb"),
        url_pattern=re_compile(
            r"^https?://[^/]+/pk/service-und-kontakt/kontakt/suche\.html\?"
        ),
        parameter="query",
    ),
    # Provider: Slidesgo (slidesgo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("59856d35-1875-4a02-8398-85c982ed256f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Puma (us.puma.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("df40c25e-a088-42e9-aaf0-a2a08fc708dc"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[a-z]+/search\?"),
        parameter="q",
    ),
    # Provider: NudeVista (nudevista.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a05fa0d8-1031-41c1-bebb-48be2ff847dd"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: United States Patent and Trademark Office (uspto.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c4b3eb9-886d-4a93-8c3a-b7b15cc21974"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Sketchfab (sketchfab.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b8b59d65-d391-4b55-8552-c0bbac055a3f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Vodafone (vodafone.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ead9ae58-d37a-4a89-8c69-0e995fe144ec"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/suche\.html\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("ead9ae58-d37a-4a89-8c69-0e995fe144ec"),
        url_pattern=re_compile(r"^https?://[^/]+/global-search-results\?"),
        parameter="search",
    ),
    # Provider: PornHat (pornhat.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("23bcdea8-3f3e-43dc-9ca7-2da9c16eef8a"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Fur Affinity (furaffinity.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cc3d3adb-84cf-489c-bbe5-54251ad35985"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Cisco Networking Academy (netacad.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("af2ad80d-c03c-4eab-af86-6dfbc3d0b4e8"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node/[^/]+"),
        segment=3,
    ),
    # Provider: NiPic.com (nipic.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c908f6f-8d57-4e25-b011-fa192dc84e5b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: Check24 (check24.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("155c901b-8757-47ae-82b5-6050e5d8ded3"),
        url_pattern=re_compile(r"^https?://[^/]+/suche\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("155c901b-8757-47ae-82b5-6050e5d8ded3"),
        url_pattern=re_compile(r"^https?://[^/]+/vergleich\?"),
        parameter="kp",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("155c901b-8757-47ae-82b5-6050e5d8ded3"),
        url_pattern=re_compile(r"^https?://[^/]+/strom/vergleich/"),
        parameter="totalconsumption",
    ),
    # Provider: Fashion Nova (fashionnova.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("47d05717-f34e-4b1b-9109-8c73340be59e"),
        url_pattern=re_compile(r"^https?://[^/]+/pages/search-results/[^/]+"),
        segment=3,
    ),
    # Provider: PlayGround.ru (playground.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0804bb0c-f634-4ec3-8ba4-5a1411d2cc64"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Virgool (virgool.io)
    QueryParameterUrlQueryParser(
        provider_id=UUID("771187df-c804-4512-9764-1c25794524f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Joe Monster (joemonster.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d74f0524-3c3b-4ca8-8c7e-29724329005e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: Qwant (qwant.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("66e6df7a-eb63-4d0d-ad42-9a1a2f778cfe"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: THAIRATH (thairath.co.th)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b66154b8-595a-4d65-8496-1d2ef07d612b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: PowerSchool (powerschool.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("93b46460-d539-4e3c-b813-15b22e084cc3"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("93b46460-d539-4e3c-b813-15b22e084cc3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Pearson VUE (pearsonvue.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c4c0fa5-b9fa-4e62-9886-860a305f296a"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\.aspx\?"),
        parameter="searchtext",
    ),
    # Provider: The Denver Post (denverpost.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0c5ee8dc-8d59-461f-af42-55636db3512d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Celine (celine.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d2bef699-f580-4b69-ab14-59a63db74b88"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("d2bef699-f580-4b69-ab14-59a63db74b88"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+-[a-z]+/search\?"),
        parameter="q",
    ),
    # Provider: State Bank of India (sbi.co.in)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1e03bb45-3f2d-4031-aef4-52a67da17e89"),
        url_pattern=re_compile(r"^https?://[^/]+/web/personal-banking"),
        parameter="_com_liferay_portal_search_web_portlet_SearchPortlet_keywords",
    ),
    # Provider: SecNews (secnews.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9c9e737a-4517-431a-a4c3-8b0cab060140"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9c9e737a-4517-431a-a4c3-8b0cab060140"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Ministère de l'Intérieur et des Outre-mer (interieur.gouv.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fca823dd-aa70-4dbd-a66b-48acdbedb553"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche\?"),
        parameter="search",
    ),
    # Provider: Turkish Revenue Administration (gib.gov.tr)
    PathSegmentUrlQueryParser(
        provider_id=UUID("90679401-944e-47ec-bd85-308288cb1930"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node/[^/]+"),
        segment=3,
    ),
    # Provider: Zalando (zalando.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bedfc3aa-2f64-4303-a63f-3905c26e6c14"),
        url_pattern=re_compile(r"^https?://[^/]+/.*/.*q"),
        parameter="q",
    ),
    # Provider: JB Hi-Fi (jbhifi.com.au)
    QueryParameterUrlQueryParser(
        provider_id=UUID("601e395a-1f76-45ef-9679-21db78e786ba"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Chefkoch (chefkoch.de)
    PathSegmentUrlQueryParser(
        provider_id=UUID("c26d50f6-64f8-40e5-9ae2-c5240c353974"),
        url_pattern=re_compile(r"^https?://[^/]+/rs/s[0-9]+/[^/]+/"),
        segment=3,
    ),
    # Provider: Micro Center (microcenter.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9bb94e4e-bf20-41a5-85b8-b29509a3980e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search_results\.aspx"),
        parameter="Ntt",
    ),
    # Provider: U.S. Securities and Exchange Commission (sec.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fd6decbc-de52-41e5-9ec6-55c8bf4f2a96"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Azərbaycan Respublikasının Dövlət İmtahan Mərkəzi (dim.gov.az)
    QueryParameterUrlQueryParser(
        provider_id=UUID("232d2521-6b66-4889-8e1b-aa02ab6ecf27"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: TV9 Telugu (tv9telugu.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("826c5dd3-71b1-4bb7-987a-d37f38117d81"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: قصة عشق (3isk.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("3cbaa4e2-c08e-4a26-a692-8879950b2598"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
        space_pattern=re_compile(r"\+"),
    ),
    # Provider: Science (science.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ab2d9ff0-538e-4b60-b11c-7098366ed819"),
        url_pattern=re_compile(r"^https?://[^/]+/action/doSearch\?"),
        parameter="AllField",
    ),
    # Provider: Dicio (dicio.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c0a8357-6f14-4356-abed-4d7517805e4c"),
        url_pattern=re_compile(r"^https?://[^/]+/pesquisa\.php\?"),
        parameter="q",
    ),
    # Provider: 文春オンライン (bunshun.jp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("090d9a0d-3e5a-4834-ba71-0d469b9be72a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="fulltext",
    ),
    # Provider: Sedo (sedo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3a317000-55ce-4084-8852-c34feb17c826"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="keyword",
    ),
    # Provider: 广州房地产 (fzg360.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("091c298f-59a6-4575-8064-a8482c777557"),
        url_pattern=re_compile(r"^https?://[^/]+/news/lists\?"),
        parameter="keyword",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("091c298f-59a6-4575-8064-a8482c777557"),
        url_pattern=re_compile(
            r"^https?://[^/]+/news/lists/keyword/[^/]+/page/[0-9]+\.html"
        ),
        segment=4,
    ),
    # Provider: Simplilearn (simplilearn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ed5dccb4-4323-4f5f-9812-300172e9ee86"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="tag",
    ),
    # Provider: ΤΟ ΒΗΜΑ (tovima.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9144d71c-fc09-4f81-bed4-ec9a70324015"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Redwap (redwap.me)
    PathSegmentUrlQueryParser(
        provider_id=UUID("26e0a523-3353-4385-b7c8-69b887618bbb"),
        url_pattern=re_compile(r"^https?://[^/]+/to/[^/]+"),
        segment=2,
        space_pattern=re_compile(r"-"),
    ),
    # Provider: ManualsLib (manualslib.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("59585d0e-d541-46e5-8053-fca52e6e64e7"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[^/]+.html"),
        segment=2,
    ),
    # Provider: Groww (groww.in)
    QueryParameterUrlQueryParser(
        provider_id=UUID("179cd50e-419c-47ac-a892-8d1619c0878f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: FossHub (fosshub.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3454819d-72ec-4b1e-a1fa-9f0346a2d325"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="search-query",
    ),
    # Provider: TinEye (tineye.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("8d7f7bfa-f362-4af0-bb56-6cb192b1ba94"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: IXL (ixl.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6dc6cf27-db8a-4186-87ca-424f6385a24b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Investor's Business Daily (investors.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4635ca80-6cf2-4101-a599-e16f500a9bde"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results/"),
        parameter="query",
    ),
    # Provider: JavBus (javbus.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("a32be5bd-cf27-4718-8f4e-6f139d7e3deb"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Iranian Labour News Agency (ilna.news)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ab674154-798b-4beb-b77c-d3d527503c9e"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/newsstudios/search"),
        parameter="q",
    ),
    # Provider: Library of Congress (loc.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a84af1ec-3f71-46da-aa6e-5d142987ae95"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(search|audio|books|film-and-videos|manuscripts|maps|notated-music|newspapers|photos|web-archives)"
        ),
        parameter="q",
    ),
    # Provider: Banco Bradesco (bradesco.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2bce5838-27f8-4b85-8998-8b2300e54c8a"),
        url_pattern=re_compile(r"^https?://[^/]+/html/classic/resultado-busca/"),
        parameter="termsearched",
    ),
    # Provider: #TheFappening (thefappeningblog.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("6d228bb2-e5ba-40a1-bada-082cdabf851d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: MSD Manuals (msdmanuals.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("50732f3e-0826-41e0-808c-15b376709870"),
        url_pattern=re_compile(r"^https?://[^/]+/.*SearchResults\?"),
        parameter="query",
    ),
    # Provider: Fuq.com (fuq.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("efb01398-7ed7-4c47-af4b-6a25e315fba9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("efb01398-7ed7-4c47-af4b-6a25e315fba9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: SarvGyan (sarvgyan.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5c7befd5-3401-4f42-a677-07c52eea401b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("5c7befd5-3401-4f42-a677-07c52eea401b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/\?"),
        parameter="s",
    ),
    # Provider: AnyPorn (anyporn.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b164d972-8a94-4da0-8881-d6f013bd8de2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: SimplyHired (simplyhired.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("89728fb8-5c3d-41fd-b5cc-0b07561ba9b0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: FapHouse (xhamsterpremium.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("35a591a5-d419-4481-9f0c-5a4e512fe4be"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(c|p)/(amateur|xhamster-category)/(videos|click)\?"
        ),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("35a591a5-d419-4481-9f0c-5a4e512fe4be"),
        url_pattern=re_compile(r"^https?://[^/]+/categories\?"),
        parameter="q",
    ),
    # Provider: Podbean (podbean.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3e020023-359b-4e47-91f8-e44542d694a5"),
        url_pattern=re_compile(r"^https?://[^/]+/site/search/index\?"),
        parameter="v",
    ),
    # Provider: Newgrounds (newgrounds.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ad4b7521-7f5f-4300-ab7d-a2f01e7fc910"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="terms",
    ),
    # Provider: Tebyan.NET (tebyan.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("04f99189-55a8-4aeb-8a12-7894ab465a0d"),
        url_pattern=re_compile(r"^https?://[^/]+/newindex\.aspx\?"),
        parameter="Keyword",
    ),
    # Provider: Daily Pakistan (dailypakistan.com.pk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1190e7d6-450f-42fe-bd6e-5e6c5e0f6013"),
        url_pattern=re_compile(r"^https?://[^/]+/\?cx"),
        parameter="q",
    ),
    # Provider: bigbasket (bigbasket.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a5821288-5394-423c-87f1-23af9d38c955"),
        url_pattern=re_compile(r"^https?://[^/]+/ps/\?"),
        parameter="q",
    ),
    # Provider: iWank TV (iwank.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("7b550685-e0e9-4030-b825-68d8cb8b485b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Instant Gaming (instant-gaming.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bcf30841-c443-4e79-b5f2-466772889b0a"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/\?"),
        parameter="q",
    ),
    # Provider:  Kongfz (kongfz.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a837f299-5f5c-405a-a1a0-4f45f80a4b0e"),
        url_pattern=re_compile(r"^https?://[^/]+/product_result/\?"),
        parameter="key",
    ),
    # Provider: Babyshop (babyshop.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4024ca33-9987-43be-94a2-22368cb56765"),
        url_pattern=re_compile(r"^https?://[^/]+/search/searchbytext\?"),
        parameter="key",
    ),
    # Provider: e621 (e621.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("160f245d-4694-433a-a37f-0fbd8f1f2e0c"),
        url_pattern=re_compile(r"^https?://[^/]+/posts\?"),
        parameter="tags",
    ),
    # Provider: Interactive Brokers (interactivebrokers.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("77cc8fa4-e988-4a4e-9144-53a258e5dfbd"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/index\.php\?"),
        parameter="query",
    ),
    # Provider: Bottega Veneta (bottegaveneta.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2bd4432e-3fb2-4cda-a099-c229fbac3d5c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2bd4432e-3fb2-4cda-a099-c229fbac3d5c"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+-[a-z]+/search\?"),
        parameter="q",
    ),
    # Provider: Movistar Plus+ (movistarplus.es)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4c77e661-ebde-4a85-8cfd-4f93b54d541f"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: CLUB-K (club-k.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5bcb7623-a98e-416b-a8e6-ee748f170328"),
        url_pattern=re_compile(r"^https?://[^/]+/index"),
        parameter="searchword",
    ),
    # Provider: Traveler Master (travelermaster.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("42b1b2ad-edbf-4280-904b-f4c7f3ff44a6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("42b1b2ad-edbf-4280-904b-f4c7f3ff44a6"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: ElecFans (elecfans.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("669c53aa-5718-4eab-9f39-accdc8b266e3"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="keyword",
    ),
    # Provider: Tailor Brands (tailorbrands.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e8442408-f6df-4abe-b4ff-7c5ab3c6f367"),
        url_pattern=re_compile(r"^https?://[^/]+/hc/[a-z]+-[a-z]+/search\?"),
        parameter="query",
    ),
    # Provider: RussianFood (russianfood.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("220615bc-4668-49c8-96fa-c6a063a2f2c6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/simple/index\.php\?"),
        parameter="sskw_title",
    ),
    # Provider: LIFE (life.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d94a0745-f998-4359-bde6-4b4588586023"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: Tua Saúde (tuasaude.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c60c8052-9e3c-48d0-a549-636aa89af4fc"),
        url_pattern=re_compile(r"^https?://[^/]+/busca/\?"),
        parameter="s",
    ),
    # Provider: Iconfinder (iconfinder.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f4b633d5-d88b-4296-a723-ca6265175a39"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: TMDB (themoviedb.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2238fb75-68f6-452c-a2f7-986cce78bb32"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: JioMart (jiomart.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a72b3bab-8c53-4330-9a4a-26e36dd0df53"),
        url_pattern=re_compile(r"^https?://[^/]+/catalogsearch/result\?"),
        parameter="q",
    ),
    # Provider: DHL (dhl.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2b4bcd85-2f09-4be9-81b4-ea1b84714f5a"),
        url_pattern=re_compile(r"^https?://[^/]+/de/privatkunden/suche\.html\?"),
        parameter="q",
    ),
    # Provider: Duo (duosecurity.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("faf0d263-d3e4-4403-adcf-fc308cb26854"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: PCWorld (pcworld.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("aada27c7-823d-4932-9033-583ca685d641"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Jiwu (jiwu.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("2ac9483a-5ec3-468f-928a-df7eab6c3dab"),
        url_pattern=re_compile(r"^https?://[^/]+/loupan/list-key[^/]\.html"),
        segment=2,
        remove_pattern=re_compile(r"^list-key|\.html$"),
    ),
    # Provider: Afternic (afternic.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e73199dd-629a-47b0-bde2-3b726ee21455"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="k",
    ),
    # Provider: NotebookCheck (notebookcheck.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7120c7f6-92de-476d-8cd3-10800fc8e0ff"),
        url_pattern=re_compile(r"^https?://[^/]+/Google-Search"),
        parameter="q",
    ),
    # Provider: Altibbi (altibbi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2da5cc76-c62d-43f6-8000-e8d697f07689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/questions\?"),
        parameter="q",
    ),
    # Provider: ZAFUL (zaful.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("55a1e624-32fe-45d3-89d5-25b697e6bf9a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: iG (ig.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1414ff73-56d6-4c16-8e38-40ff05bb4b3e"),
        url_pattern=re_compile(r"^https?://[^/]+/buscar"),
        parameter="q",
    ),
    # Provider: FOCUS online (focus.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0a99975-17c2-4c3e-b65f-5a8bc6cab82b"),
        url_pattern=re_compile(r"^https?://[^/]+/suche"),
        parameter="q",
    ),
    # Provider: LATAM Airlines (latam.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4f61f684-5b01-46b7-b1a8-dadec97f5ee9"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[a-z]+/[^/]+\?"),
        parameter="destination",
    ),
    # Provider: AnySex (anysex.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("30121aa8-cd20-4fc8-806c-ca5cd0aafac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("30121aa8-cd20-4fc8-806c-ca5cd0aafac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[0-9]+/\?"),
        parameter="q",
    ),
    # Provider: Geihui (geihui.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fd657aee-05a9-499c-b9b4-1f413e180195"),
        url_pattern=re_compile(r"^https?://[^/]+/searchlog\?"),
        parameter="k",
    ),
    # Provider: Patagonia (patagonia.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5d9bdcf-34e3-4308-b685-744fe8d8586d"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]/[a-z]/search/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5d9bdcf-34e3-4308-b685-744fe8d8586d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: VeryCD (verycd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("75fde330-0d1e-4142-8b5d-3c3d1d5e1505"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="kw",
    ),
    # Provider: SteamDB (steamdb.info)
    QueryParameterUrlQueryParser(
        provider_id=UUID("46a7ff7e-21aa-4ce6-aa5d-2245e890f9cc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: AniMixPlay (animixplay.to)
    QueryParameterUrlQueryParser(
        provider_id=UUID("04c83555-1c17-4cf8-95cb-ed237b89dc7d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: Bonanza (bonanza.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3c4b3e42-869b-4833-b2b5-a947e5752d4c"),
        url_pattern=re_compile(r"^https?://[^/]+/items/search\?"),
        parameter="q[search_term]",
    ),
    # Provider: MQL5 (mql5.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("65362caf-d7e6-4d2c-9678-d636622538b5"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search"),
        parameter="!keyword",
    ),
    # Provider: YouPorn (keezmovies.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("39a9b7ad-d223-4555-aa48-402617b1ac7d"),
        url_pattern=re_compile(r"^https?://[^/]+/video\?"),
        parameter="search",
    ),
    # Provider: 9to5Mac (9to5mac.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ac75cebc-810a-4e73-904b-5e58030a46d2"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("ac75cebc-810a-4e73-904b-5e58030a46d2"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: USAGov (usa.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f8511351-145c-49f0-a357-2970d58e4462"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Étudiant.gouv (etudiant.gouv.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c3a481b7-57e9-46fd-97a6-408916828081"),
        url_pattern=re_compile(r"^https?://[a-z]+/recherche\?"),
        parameter="keywords",
    ),
    # Provider: Al-Maraabi Medias (al-maraabimedias.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d5f49941-eed9-444a-b382-85fa68969e37"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
        remove_pattern=re_compile(r"\+"),
    ),
    # Provider: U.S. Department of Justice (justice.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bd846aca-1170-47fc-9425-0fcda3616e11"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Alison (alison.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b2a98af7-4b12-4df0-ad7c-c67eeb6b925f"),
        url_pattern=re_compile(r"^https?://[^/]+/(courses|careers-search)\?"),
        parameter="query",
    ),
    # Provider: Darty (darty.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("06a18e03-1bbf-4d19-b7b3-9d476d7ced18"),
        url_pattern=re_compile(r"^https?://[^/]+/nav/recherche/[^/]+"),
        segment=3,
        remove_pattern=re_compile(r"\.html$"),
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("06a18e03-1bbf-4d19-b7b3-9d476d7ced18"),
        url_pattern=re_compile(r"^https?://[^/]+/nav/recherche\?"),
        parameter="text",
    ),
    # Provider: The Ringer (theringer.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e66088e3-89c2-4819-bace-6574ff14cd04"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Zimmertüren OCHS (tueren-fachhandel.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("26c9fc75-5f47-49f1-940f-cba62d62834a"),
        url_pattern=re_compile(r"^https?://[^/]+/catalogsearch/result\?"),
        parameter="q",
    ),
    # Provider: NESN (nesn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4f35d276-5198-4289-8eeb-5290524c0baa"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Zimbio (zimbio.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bcd95c84-590b-476f-8333-33ddbc519551"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Nik Salehi (niksalehi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e3430cbd-a6ab-4eee-85f5-5718a6f707c6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: ehow (ehow.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7e1d4dec-4b92-4b25-9321-54a404500bb3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: PornMD (pornmd.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f9349f92-1316-4056-8b7b-555e65c66646"),
        url_pattern=re_compile(r"^https?://[^/]+/(gay|straight|tranny)/[^/]+"),
        segment=2,
        space_pattern=re_compile(r"\+"),
    ),
    # Provider: しぃアンテナ (2ch-c.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5c7b08a7-c0cc-47e0-8b08-3382aee61b5d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="wd",
    ),
    # Provider: ستاره پارسی (setareparsi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2848acd9-fad3-4271-888c-826c5f606d23"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/\?"),
        parameter="query",
    ),
    # Provider: Tweak Town (tweaktown.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ce4aa51a-1724-4bd1-9677-50f98934126e"),
        url_pattern=re_compile(r"^https?://[^/]+/cse/\?"),
        parameter="q",
    ),
    # Provider: Soft Famous (softfamous.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9dab192f-16a6-4572-94cc-68fa888b957e"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: HS编码查询 (hsbianma.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b54cc512-eb0c-4585-8822-52f5f3a5bf5a"),
        url_pattern=re_compile(r"^https?://[^/]+/[Ss]earch"),
        parameter="keywords",
    ),
    # Provider: 早报 (zaobao.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("cdf2dd02-9ce5-441a-ac5d-b44d766bcf03"),
        url_pattern=re_compile(r"^https?://[^/]+/search/site/[^/]+"),
        segment=3,
    ),
    # Provider: GiveMeSport (givemesport.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("75dbe70c-7e8c-4284-a863-40f1d44297d1"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("75dbe70c-7e8c-4284-a863-40f1d44297d1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+\?"),
        parameter="s",
    ),
    # Provider: Internshala (internshala.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("492e2ccf-6053-42dc-81f8-4b7877a33634"),
        url_pattern=re_compile(r"^https?://[^/]+/(internships|jobs)/keywords-[^/]+/"),
        segment=2,
        remove_pattern=re_compile(r"^keywords-"),
    ),
    # Provider: Jogos 360 (jogos360.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bca1691b-0feb-40cc-98f2-aaba2aeaed44"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: Belgium.be (fgov.be)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9fa587a9-21ee-4547-9277-704587f8a8fb"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="keywords",
    ),
    # Provider: 오늘의유머 (todayhumor.co.kr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("514f72b9-c0b6-439c-8955-cc353bd7e738"),
        url_pattern=re_compile(r"^https?://[^/]+/board/list\.php\?"),
        parameter="keyword",
    ),
    # Provider: Dice (dice.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cbbd5882-5eea-43bf-9b67-a1a0d70854db"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="q",
    ),
    # Provider: Nationwide Building Society (nationwide.co.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("692eae94-9832-4bcb-9843-5f0f1ad01264"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="term",
    ),
    # Provider: SunPorno (sunporno.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("e70ab0e5-f15e-409e-992c-c3e26fd6dc5f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Serebii.net (serebii.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("14ed7f5a-7e16-4810-b688-e5521e09489d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.shtml\?"),
        parameter="q",
    ),
    # Provider: Irrawaddy (irrawaddy.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("51906884-f742-4ec0-90b9-d51fe33d60e2"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: خبر ورزشی (khabarvarzeshi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("48cb0cd7-35e1-4800-a23e-997a9835a77a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Arcalive (arca.live)
    QueryParameterUrlQueryParser(
        provider_id=UUID("198a7743-5a99-4e42-be03-4178c90d7c97"),
        url_pattern=re_compile(r"^https?://[^/]+/b/breaking\?"),
        parameter="keyword",
    ),
    # Provider: JAV HD Porn (javhdporn.net)
    PathSegmentUrlQueryParser(
        provider_id=UUID("231b8492-f522-4ffa-a80d-2a75cf76cef1"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: LetPub编辑 (letpub.com.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0da5575-f218-41a0-b897-e7054dc30d28"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.php\?"),
        parameter="searchname",
    ),
    # Provider: Área VIP (areavip.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("21fdae62-990e-41b4-bca4-126a5c5779c7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: EZTV (eztv.re)
    QueryParameterUrlQueryParser(
        provider_id=UUID("014a1236-e1d0-4d46-8392-e4066f2917fc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q1",
    ),
    # Provider: OpenDNS (opendns.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("af4be1f9-d453-4c8c-93a7-c4f8e6fc42ce"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="cludoquery",
    ),
    # Provider: Brave (brave.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e3be3140-7f78-4de1-a43b-6c75d345e4c4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: DreamHost (dreamhost.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9bb2256c-b0fe-43e3-85e8-425c5cb9b367"),
        url_pattern=re_compile(r"^https?://[^/]+/domains/\?"),
        parameter="domain",
    ),
    # Provider: CK365 (ck365.cn)
    PathSegmentUrlQueryParser(
        provider_id=UUID("294e275f-689e-4b62-af94-986e62c3fda8"),
        url_pattern=re_compile(r"^https?://[^/]+/news/search(-xzg-)?kw-[^-]-\.html"),
        segment=2,
        remove_pattern=re_compile(
            "^search(-xzg-)?kw-|(-fields-[0-9])?(-page-[0-9])?-?\.html$"
        ),
    ),
    # Provider: The Gospel Coalition (thegospelcoalition.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("16fe52c5-6b70-4d8a-ada0-dfc5e6062e43"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: iQIYI (iq.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("18418b83-cc73-4502-8af5-2b8b3b9ddf3e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Western Governors University (wgu.edu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0673e75f-baa6-4365-b4ad-04cab6c5d8ad"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html"),
        parameter="cludoquery",
    ),
    # Provider: Levi's (levi.com.cn)
    PathSegmentUrlQueryParser(
        provider_id=UUID("1ced0855-8d1d-4505-bce8-d5f518b74a01"),
        url_pattern=re_compile(r"^https?://[^/]+/[A-Z]/[a-z]+_[A-Z]+/search/[^/]+"),
        segment=4,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("1ced0855-8d1d-4505-bce8-d5f518b74a01"),
        url_pattern=re_compile(r"^https?://[^/]+/search/result\?"),
        parameter="keyword",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("1ced0855-8d1d-4505-bce8-d5f518b74a01"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: يلا شوت الجديد (yalla-shoot-new.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ee09cbfa-904f-43c7-9bd4-61145edf22ba"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Radio Times (radiotimes.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("156d3e19-bb02-4073-96cc-a3ad67abd76f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("156d3e19-bb02-4073-96cc-a3ad67abd76f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/news/page/[0-9]+/\?"),
        parameter="q",
    ),
    # Provider: DEV Community (dev.to)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2c8190b4-6226-4f56-80b9-d86a51929d3a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: موقع برستيج (brstej.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a41f74d7-fb1c-4d42-ab0e-80304d7042f9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="keywords",
    ),
    # Provider: 欧乐影院 (olevod.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b4e6ec20-ca60-4e65-a3a7-2005b455a945"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.php/[^/]+/search.html\?"),
        parameter="wd",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("b4e6ec20-ca60-4e65-a3a7-2005b455a945"),
        url_pattern=re_compile(
            r"^https?://[^/]+/index\.php/[^/]+/search/page/[0-9]+/wd/[^/]+\.html"
        ),
        segment=7,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: Kinsta (kinsta.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("97228c7c-449c-4773-bf49-e3f0c4dd5dbb"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Aftodioikisi.gr (aftodioikisi.gr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("df0db395-d7f9-4e32-af97-065dc80c4733"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("df0db395-d7f9-4e32-af97-065dc80c4733"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Stardew Valley Wiki (stardewvalleywiki.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("98341525-4c5c-445b-890a-9d272c9018e2"),
        url_pattern=re_compile(r"^https?://[^/]+/mediawiki/index\.php\?"),
        parameter="search",
    ),
    # Provider: Thomasnet (thomasnet.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c920856e-587f-4ea6-adb9-b7348e01db93"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="searchterm",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c920856e-587f-4ea6-adb9-b7348e01db93"),
        url_pattern=re_compile(
            r"^https?://[^/]+/search/(industry-insights|white-paper-guides|product-news|company-news)/"
        ),
        parameter="q",
    ),
    # Provider: Dafiti (dafiti.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5533a9d5-0172-448a-8af6-1804d29732a7"),
        url_pattern=re_compile(r"^https?://[^/]+/catalog/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("5533a9d5-0172-448a-8af6-1804d29732a7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: Linkvertise (linkvertise.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("2852fdb7-8243-4dda-a522-3ba445a24eb1"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: 999.md (999.md)
    QueryParameterUrlQueryParser(
        provider_id=UUID("11c61ce1-cedb-482e-b1b0-4e53aa5525e1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Académie de Versailles (ac-versailles.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b2a0848d-3974-410e-b80a-728ba6ecff8f"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche"),
        parameter="keywords",
    ),
    # Provider: Manganato (manganato.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d9abf7ba-9cfb-4dd8-ae30-d0b91e021a5d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/story/[^/]+"),
        segment=3,
    ),
    # Provider: H&R Block (hrblock.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("f1f53bd2-40b1-4920-b9e8-aa71c279b117"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Kizi (kizi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4908058e-98db-48cd-aa45-2fe0de8cc75a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="term",
    ),
    # Provider: Jobartis (jobartis.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("e2543f76-712e-4373-b66b-730d133d17d6"),
        url_pattern=re_compile(r"^https?://[^/]+/vagas-emprego/[^/]+"),
        segment=2,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e2543f76-712e-4373-b66b-730d133d17d6"),
        url_pattern=re_compile(r"^https?://[^/]+/vagas-emprego\?"),
        parameter="q[content_matches_tsquery]",
    ),
    # Provider: The Associated Press (ap.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6edb0f84-ceac-4b74-88b5-08e6dca51f64"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.wz\?"),
        parameter="q",
    ),
    # Provider: فتوکده (photokade.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("873db19a-45ea-424c-89b5-ee22bd2e4367"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("873db19a-45ea-424c-89b5-ee22bd2e4367"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: HDrezka (hdrezka.me)
    QueryParameterUrlQueryParser(
        provider_id=UUID("842851b8-57c2-4523-8005-af3ac3e47652"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: ActBlue (actblue.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9ed9815d-fde0-44b9-bee4-6b3644ebd2ff"),
        url_pattern=re_compile(r"^https?://[^/]+/directory\?"),
        parameter="query",
    ),
    # Provider: LetMeJerk (letmejerk.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("56693bc3-0d40-46b5-ac95-5466fa202e31"),
        url_pattern=re_compile(r"^https?://[^/]+/se/[^/]+"),
        segment=2,
    ),
    # Provider: CJ Dropshipping (cjdropshipping.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("e15f1c19-5590-422a-8a16-0f489e3216ca"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"\.html$"),
    ),
    # Provider: Chittorgarh (chittorgarh.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e8db96c3-b419-47fc-8d49-e7693d44ac64"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.asp\?"),
        parameter="text",
    ),
    # Provider: ГидОнлайн (gidonline.io)
    QueryParameterUrlQueryParser(
        provider_id=UUID("809ebb97-805b-42c0-a8fc-8358a0b82412"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Subf2m (subf2m.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1636c381-298d-4078-a7f4-ce17bcfa68e9"),
        url_pattern=re_compile(r"^https?://[^/]+/subtitles/searchbytitle\?"),
        parameter="query",
    ),
    # Provider: TigerDirect (tigerdirect.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("58fd63ad-8dff-4cd8-8996-ae3b87d99bb0"),
        url_pattern=re_compile(r"^https?://[^/]+/applications/(C|c)ategory"),
        parameter="srkey",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("58fd63ad-8dff-4cd8-8996-ae3b87d99bb0"),
        url_pattern=re_compile(r"^https?://[^/]+/applications/SearchTools"),
        parameter="keywords",
    ),
    # Provider: Fatos Desconhecidos (fatosdesconhecidos.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7748cdf3-198c-43ae-8fb8-24f776d920a5"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: 動漫花園資源網 (dmhy.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bab585fe-04f7-445c-afc0-9f88dd1ffe80"),
        url_pattern=re_compile(r"^https?://[^/]+/topics/list\?"),
        parameter="keyword",
    ),
    # Provider: Agence nationale des titres sécurisés (ants.gouv.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5694b63c-b800-416b-8742-7fdfa597a1a1"),
        url_pattern=re_compile(r"^https?://[^/]+/rechercher\?"),
        parameter="q",
    ),
    # Provider: منیبان (moniban.news)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e00da4ec-26f7-455c-b42d-fbe525f7e907"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/"),
        parameter="query",
    ),
    # Provider: Tour de France (letour.fr)
    PathSegmentUrlQueryParser(
        provider_id=UUID("98fc3b47-39b4-44b7-a877-bca4c344b1bb"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("98fc3b47-39b4-44b7-a877-bca4c344b1bb"),
        url_pattern=re_compile(r"^https?://[^/]+/fr/rechercher/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("98fc3b47-39b4-44b7-a877-bca4c344b1bb"),
        url_pattern=re_compile(r"^https?://[^/]+/de/suche/[^/]+"),
        segment=3,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("98fc3b47-39b4-44b7-a877-bca4c344b1bb"),
        url_pattern=re_compile(r"^https?://[^/]+/es/busqueda/[^/]+"),
        segment=3,
    ),
    # Provider: EMPFlix (empflix.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4473c856-9a24-4c27-954f-de8240b21e3a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="what",
    ),
    # Provider: Asura Scans (asura.gg)
    QueryParameterUrlQueryParser(
        provider_id=UUID("47230112-5794-4fa1-8a6a-01e60ac03341"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: hi.gt (hi.gt)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6f955cd5-7dca-46b3-8053-77c55083fa70"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("6f955cd5-7dca-46b3-8053-77c55083fa70"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 快吧游戏 (kuai8.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("55b2f892-a52d-48b7-86ed-4e7dc3c6869c"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="keyword",
    ),
    # Provider: 国家自然科学基金委员会 (nsfc.gov.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ae21e786-c1aa-4538-8fdf-b94f36963ef1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.htm\?"),
        parameter="q",
    ),
    # Provider: Federal Trade Commission (ftc.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9d6923ad-9fcd-4a9a-bb03-a13a9de17ab9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: المرصد (al-marsd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c209606e-ab2d-4764-af4a-e6847f748ef7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Pear Deck (peardeck.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("947e12bc-56f0-4af7-9fb9-ef5ffaf0b605"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Wikimapia (wikimapia.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("86fbf437-21e7-4350-8739-073bee7da46a"),
        url_pattern=re_compile(r"^https?://[^/]+/"),
        parameter="search",
    ),
    # Provider:  Discover Bank (discovercard.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("66a9d0ed-e20f-4bb6-9028-becb52e6dffe"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Aldar.ma (aldar.ma)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a1a3d10f-460a-4144-95d8-b475e3a008d6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Gimy TV (gimy.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7b1f5f4-934b-43c8-8072-8ce53056663e"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="wd",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("c7b1f5f4-934b-43c8-8072-8ce53056663e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"(-+[0-9]-+)\.html$"),
    ),
    # Provider: JRA日本中央競馬会 (jra.go.jp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("56b0ef36-b4b5-4d8d-87d5-0e8dface495a"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: ایمنا (imna.ir)
    QueryParameterUrlQueryParser(
        provider_id=UUID("499a7f14-e992-4c20-9a0b-f0999cca6eda"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: BAUHAUS (bauhaus.info)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1c492cdf-66f3-498d-9f99-b704fc24ee0f"),
        url_pattern=re_compile(r"^https?://[^/]+/suche/produkte\?"),
        parameter="text",
    ),
    # Provider: پایگاه خبری جماران (jamaran.news)
    QueryParameterUrlQueryParser(
        provider_id=UUID("40878f4a-3609-45c7-a021-6af885e9400c"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/search\?"),
        parameter="q",
        remove_pattern=re_compile(r"\+"),
    ),
    # Provider: United States Senate (senate.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("952fd42b-b2a4-46c9-ba81-99c872d8ab92"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search"),
        parameter="q",
    ),
    # Provider: Hunter (hunter.io)
    PathSegmentUrlQueryParser(
        provider_id=UUID("3c629811-34cc-4e50-aee0-c45befdddec4"),
        url_pattern=re_compile(r"^https?://[^/]+/try/search/[^/]+"),
        segment=3,
    ),
    # Provider: Secretaria de Estado de Educação de Minas Gerais (educacao.mg.gov.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6da7f362-c870-4cf6-9969-64c1f0759ff1"),
        url_pattern=re_compile(r"^https?://[^/]+/component/search/\?"),
        parameter="all",
    ),
    # Provider: WebCrawler (webcrawler.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ca614ed7-7c57-464f-9f7e-0e3e36f849da"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="q",
    ),
    # Provider: MoviesJoy (moviesjoy.to)
    PathSegmentUrlQueryParser(
        provider_id=UUID("5b4a92ad-46b6-4ee5-a13d-4ea1e1d25b2f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: 17货源 (17zwd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("69f6d361-8e1d-42e3-9db4-ba6e0d8888e6"),
        url_pattern=re_compile(r"^https?://[^/]+/sks\.htm\?"),
        parameter="so",
    ),
    # Provider: PRWeb (prweb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("696acb0c-c481-45a3-a8d6-b456fde2129a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.aspx\?"),
        parameter="search-releases",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("696acb0c-c481-45a3-a8d6-b456fde2129a"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\.aspx\?"),
        parameter="Search-releases",
    ),
    # Provider: المشهد اليمني (almashhad-alyemeni.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8f5ebd98-87d8-4897-8f2c-07cec9671e6b"),
        url_pattern=re_compile(r"^https?://[^/]+/section"),
        parameter="keyword",
    ),
    # Provider: Fortinet (fortinet.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1286ec72-fe6f-4bdb-a6b8-b3089f62a707"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: 电影港 (dygang.cc)
    QueryParameterUrlQueryParser(
        provider_id=UUID("56939575-e90a-492a-8685-df12469b1553"),
        url_pattern=re_compile(r"^https?://[^/]+/e/search/result/\?"),
        parameter="searchid",
    ),
    # Provider: YIFY Subtitles (yts-subs.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("8e54437d-2e26-4276-8bd6-b64af9adfd9e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: ActiveCampaign (activecampaign.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("71b17655-f64d-4610-b7ed-2eb6fef016e0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Upworthy (upworthy.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b4099d71-a0fb-419c-b611-0aa7b18b5252"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: draw.io (drawio.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5a4f00f6-dbb7-4593-b822-39c803e07652"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: Повар.ру (povar.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6915ef60-fd7e-408a-a225-23447a8fb7a9"),
        url_pattern=re_compile(r"^https?://[^/]+/xmlsearch\?"),
        parameter="query",
    ),
    # Provider: Santander (santander.co.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c5931062-d364-481a-a727-254cb1172ae4"),
        url_pattern=re_compile(r"^https?://[^/]+/s/search\.html\?"),
        parameter="query",
    ),
    # Provider: Ping Identity (pingidentity.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("9c7b638e-e064-4ee1-a09b-b3ce82e92e99"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search-results\.html"),
        parameter="q",
    ),
    # Provider: НТВ.Ru (ntv.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a09b2970-91e6-4ea7-8b6a-d89196186a17"),
        url_pattern=re_compile(r"^https?://[^/]+/finder/\?"),
        parameter="keytext",
    ),
    # Provider: InvestorPlace (investorplace.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("16728571-5a71-4790-abc8-43de01db9764"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: FreeOnes (freeones.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8bafca69-c2d8-4b85-b3dc-168030c5c875"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(search|suche)\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("8bafca69-c2d8-4b85-b3dc-168030c5c875"),
        url_pattern=re_compile(r"^https?://[^/]+/(photos|babes|videos|cams)\?"),
        parameter="q",
    ),
    # Provider: AGE动漫 (agemys.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7f4dfd14-b1bf-4286-a354-1f98602e7f8b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Gogoanime (gogoanime.fi)
    QueryParameterUrlQueryParser(
        provider_id=UUID("25c75bd9-145e-4bef-8125-b361e91d4832"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="keyword",
    ),
    # Provider: Légifrance (legifrance.gouv.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0657eade-da9a-48ae-b132-263551c04cb7"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="query",
    ),
    # Provider: ROZEE (rozee.pk)
    PathSegmentUrlQueryParser(
        provider_id=UUID("601b194f-83d0-445c-98dc-57c7ed9a1ae3"),
        url_pattern=re_compile(r"^https?://[^/]+/job/jsearch/q/[^/]+"),
        segment=4,
    ),
    # Provider: Gay Male Tube (gaymaletube.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("5c638567-14e2-41a1-ab1f-bf0436fd426b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/a/[^/]+\?"),
        segment=3,
    ),
    # Provider: ScienceAlert (sciencealert.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("74a400d9-14cf-4c96-b37a-16b53c372cd8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: VAVEL (vavel.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b829f8d1-e439-4669-8d14-8ffdf8825d67"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="query",
    ),
    # Provider: BestJavPorn (bestjavporn.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("34468ac0-17d8-4208-b999-f7a1fdbef8f0"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: VijestiBa (vijesti.ba)
    QueryParameterUrlQueryParser(
        provider_id=UUID("121e12a4-258c-43c7-bf8d-648b9d5deafb"),
        url_pattern=re_compile(r"^https?://[^/]+/pretraga\?"),
        parameter="keyword",
    ),
    # Provider: JOQ Albania (joq.al)
    QueryParameterUrlQueryParser(
        provider_id=UUID("428f9f33-cd35-493e-8a1e-2b2eb4f80915"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: WoWProgress (wowprogress.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5f71c55f-fd47-4cf6-851c-312bfa82a70d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: المواطن (elmwatin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0879f31d-e840-4dd5-ac87-6b100195cac6"),
        url_pattern=re_compile(r"^https?://[^/]+/list\.aspx\?"),
        parameter="w",
    ),
    # Provider: Decolar (decolar.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("010bc4cd-e750-4537-b4ea-9f1ae095534b"),
        url_pattern=re_compile(
            r"^https?://[^/]+/shop/flights/results/roundtrip/[^/]+/[^/]+"
        ),
        segment=6,
    ),
    # Provider: Yummly (yummly.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ecdf21a9-f2b2-413d-8f27-68eaa2980672"),
        url_pattern=re_compile(r"^https?://[^/]+/recipes\?"),
        parameter="q",
    ),
    # Provider: Hongkiat (hongkiat.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b4b74976-b043-48d2-942a-1f6943b3416b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("b4b74976-b043-48d2-942a-1f6943b3416b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: MyBookie (mybookie.ag)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6c7a0bfb-2c57-43b9-8503-32880d26fb7b"),
        url_pattern=re_compile(r"^https?://[^/]+/sportsbook/\?"),
        parameter="sportsbook_search_term",
    ),
    # Provider: Manga Raw (mangaraw.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("54dc3b01-8316-4526-8396-b455edf5ac44"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Gazeta do Povo (gazetadopovo.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("73b0e565-bc20-4fba-963a-ce498b1ce6f2"),
        url_pattern=re_compile(r"^https?://[^/]+/busca"),
        parameter="q",
    ),
    # Provider: 留园网 (6park.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2faeba1b-de53-482a-a5d6-a56df7aec7c7"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="keyword",
    ),
    # Provider: Perez Hilton (perezhilton.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("815b4535-d42a-499a-b2c7-4fc09aad6a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("815b4535-d42a-499a-b2c7-4fc09aad6a8b"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Smashing Magazine (smashingmagazine.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5154ee87-398e-475a-9aa8-c45cf5e939ff"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Ero Video (ero-video.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1b090369-2f18-4bc7-8c91-e4dea41e3f9e"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: IFLScience (iflscience.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7a49ec69-7eef-4e5d-8ee1-e9813eec739e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: PornTube (porntube.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("df350b9c-4017-46ef-b219-bbe74d53e24a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: SpyFu (spyfu.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a6d78837-e1e7-4b00-9faa-b46b1c5adbe1"),
        url_pattern=re_compile(r"^https?://[^/]+/overview/domain\?"),
        parameter="query",
    ),
    # Provider: American Physical Society (aps.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5852c266-493e-493e-aef4-ee8c72e68e2d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: American Military News (americanmilitarynews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("92c40ea3-f34f-4fe7-97f1-3fafbdf091bd"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("92c40ea3-f34f-4fe7-97f1-3fafbdf091bd"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Alot (alot.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b0dff7be-a08d-4355-b176-a9914c13ed6a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: 美国之音中文网 (voachinese.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("454c52f4-382f-4fc5-9233-cca81b5715b5"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="k",
    ),
    # Provider: eAnswers (eanswers.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a5c56e50-bb0c-4097-a453-c2828147b258"),
        url_pattern=re_compile(r"^https?://[^/]+/results/v0/search\?"),
        parameter="q",
    ),
    # Provider: Bue de Musica (buedemusica.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c1a5a3d7-fa59-464b-b3c3-08a152ef7ec9"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c1a5a3d7-fa59-464b-b3c3-08a152ef7ec9"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Arch Linux (archlinux.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d6bd0924-be4d-4b5d-b3d7-54cbc89e475d"),
        url_pattern=re_compile(r"^https?://[^/]+/packages"),
        parameter="q",
    ),
    # Provider: InsideEVs (insideevs.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5cb2babb-c107-402f-8975-2e6fed429e19"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="q",
    ),
    # Provider: Porn HD Videos (pornhdvideos.net)
    PathSegmentUrlQueryParser(
        provider_id=UUID("cbb54c43-2b0f-4b78-aac6-76e674eafa5f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: SEOClerks (seoclerk.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("994de6d6-3931-4af4-a2c1-286197d64d9f"),
        url_pattern=re_compile(r"^https?://[^/]+/marketplace\?"),
        parameter="query",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("994de6d6-3931-4af4-a2c1-286197d64d9f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: 大БКРС (bkrs.info)
    QueryParameterUrlQueryParser(
        provider_id=UUID("54b43b1e-0911-48a5-b0cc-44af0e0b56a1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: RVCJ (rvcj.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4faaedcf-3b24-42bf-8933-66f1fe9fc05d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: CCN (ccn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("71a377ac-2de2-498d-881f-292bb91809a1"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("71a377ac-2de2-498d-881f-292bb91809a1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: 禁漫天堂 (jmcomic.mobi)
    QueryParameterUrlQueryParser(
        provider_id=UUID("973fa72a-ac39-4071-b8ec-036fe4a51433"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="search_query",
    ),
    # Provider: Moretify (moretify.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2679a83f-9230-4745-982a-991a24b7bb99"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Pornez.net (pornez.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("085e931f-8c39-4b41-91d2-41d5391652c8"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: YuppTV (yupptv.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("0d8749a7-2fbe-4f57-95af-1b68cdb55726"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Search Engine Land (searchengineland.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d7b39362-63c1-485b-b682-02f3e3e9089d"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("d7b39362-63c1-485b-b682-02f3e3e9089d"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Pronto.com (pronto.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1f984e0a-8de7-48ce-a265-fcf191919b82"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\?"),
        parameter="q",
    ),
    # Provider: UCloud优刻得 (ucloud.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7b800c20-08ca-4b29-93b6-73e8489fd1d5"),
        url_pattern=re_compile(r"^https?://[^/]+/site/search\.html\?"),
        parameter="k",
    ),
    # Provider: rolloid (rolloid.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8baf6399-830e-44c4-9c6b-1317b06c4dbf"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Movierulz (5movierulz.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("24182d53-4e55-4a11-8452-3f4fdd07d6f4"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Goodporn.to (goodporn.to)
    PathSegmentUrlQueryParser(
        provider_id=UUID("370dc725-08c0-488c-b759-5929f1d0e473"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: 悟空找房 (wkzf.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("07ddf655-5d06-431e-83b8-eee3afed95e6"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/esf/[^/]+$"),
        segment=3,
    ),
    # Provider: Movies2watch (movies2watch.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d0e30f77-6422-4d50-82ed-e08f1fb9dbdc"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Auchan (auchan.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("961cdee8-1fd7-4dfe-83f7-d90b6042d729"),
        url_pattern=re_compile(r"^https?://[^/]+/recherche\?"),
        parameter="text",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("961cdee8-1fd7-4dfe-83f7-d90b6042d729"),
        url_pattern=re_compile(r"^https?://[^/]+/.*\?redirect_keywords"),
        parameter="redirect_keywords",
    ),
    # Provider: Futebol Play HD (futebolplayhd.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("821f6fa2-ea04-41ea-bf17-b109ca50096b"),
        url_pattern=re_compile(r"^https?://[^/]+/buscar/[^/]+"),
        segment=2,
    ),
    # Provider: 应届生 (yingjiesheng.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("95026b4e-687c-470f-9bed-3b885ac359b6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="word",
    ),
    # Provider: KickassTorrents (kat.cr)
    PathSegmentUrlQueryParser(
        provider_id=UUID("6bd2e696-3d6c-4160-86c9-d67077caff67"),
        url_pattern=re_compile(r"^https?://[^/]+/usearch/[^/]+"),
        segment=2,
    ),
    # Provider: بنك زون (bank-zone.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("ce3e2604-d0e4-4ba5-9477-35afd17add11"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: IC交易网 (ic.net.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7abf5efb-f7a0-4488-8eb1-ed697d65dd77"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="key",
    ),
    # Provider: شاهد فور يو (shahed4u.onl)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d6aeabd8-d963-4610-9b6a-b0850064dc82"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="s",
    ),
    # Provider: Rule 34 (rule34video.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("b0ab35bf-56c0-4f8a-af8e-3f4a6f0aa6da"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: 稿定 (gaoding.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d92a661b-e529-4513-922f-75246403f463"),
        url_pattern=re_compile(r"^https?://[^/]+/contents/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"_pn[0-9]+$"),
    ),
    # Provider: The Vintage News (thevintagenews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a2237d78-cdd0-4476-a886-92a309c89993"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a2237d78-cdd0-4476-a886-92a309c89993"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: ORIENT (orient.tm)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2497b49b-4e0f-4e75-b789-16d469dab969"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Salesloft (salesloft.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b578b023-9e72-4f5c-9a84-b0c4479dcd44"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: KBH Games (kbhgames.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a569f86c-dc75-40d9-a107-4aebdbe69708"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a569f86c-dc75-40d9-a107-4aebdbe69708"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Schema.org (schema.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("929bd0b5-f86c-4597-8d8f-6c857203127c"),
        url_pattern=re_compile(r"^https?://[^/]+/docs/search_results\.html\?"),
        parameter="q",
    ),
    # Provider: Kmart (kmart.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dbe8ea18-172e-42dc-abaa-1c82d69a8a05"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="search",
    ),
    # Provider: InfoCert (infocert.it)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e6a60332-e1ac-410c-a06e-741b316b654a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Fanpop (fanpop.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1097060d-7676-43b0-b6fa-4ebd632e74e5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: sexBJcam (sexbjcam.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a2b06b8a-0547-4eef-b7e6-85f0101a1b73"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Hearthstone Top Decks (hearthstonetopdecks.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("682ce07c-60a7-46c5-a4c2-f0639eb39b5b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("682ce07c-60a7-46c5-a4c2-f0639eb39b5b"),
        url_pattern=re_compile(r"^https?://[^/]+/(cards|decks)/\?"),
        parameter="st",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("682ce07c-60a7-46c5-a4c2-f0639eb39b5b"),
        url_pattern=re_compile(r"^https?://[^/]+/(cards|decks)/page/[0-9]+/\?"),
        parameter="st",
    ),
    # Provider: National Institute of Open Schooling (nios.ac.in)
    QueryParameterUrlQueryParser(
        provider_id=UUID("81659305-67b1-49d4-b760-a80e24cca6db"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.aspx\?"),
        parameter="q",
    ),
    # Provider: المستقبل الاقتصادي (mostkbal.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c4cc8db3-b372-4439-ad1a-c96de222e4dc"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\?"),
        parameter="q",
    ),
    # Provider: SearchLock (searchlock.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3df606b7-2fea-4e22-9670-53ea29b6b4d5"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: tagDiv (tagdiv.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0662ac89-c677-473f-887b-8750c9dd13d3"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("0662ac89-c677-473f-887b-8750c9dd13d3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: LivingSocial (livingsocial.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("31a21d99-f2c7-4d31-8b1f-1a2a8632cb22"),
        url_pattern=re_compile(r"^https?://[^/]+/browse/[^/]+\?"),
        parameter="query",
    ),
    # Provider: 知末 (znzmo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c220068a-ad4b-491f-9063-5acb1628f2bd"),
        url_pattern=re_compile(
            r"^https?://[^/]+/(general|3dmoxing|sumoxing|tietu|sgt|wenben|xgt)\.html\?"
        ),
        parameter="keyword",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("c220068a-ad4b-491f-9063-5acb1628f2bd"),
        url_pattern=re_compile(r"^https?://[^/]+/searchCase/[^/]+\?"),
        segment=2,
    ),
    # Provider: University of Zambia (unza.zm)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6e73ff3b-1604-488b-8303-b08f492d2155"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node\?"),
        parameter="keys",
    ),
    # Provider: Futemax (futemax.live)
    PathSegmentUrlQueryParser(
        provider_id=UUID("78961060-5542-44e2-b617-7bdf7e05eef3"),
        url_pattern=re_compile(r"^https?://[^/]+/buscar/[^/]+"),
        segment=2,
    ),
    # Provider: SexKbj (sexkbj.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f4b82c86-c0f3-4eec-a572-aa61fa631a37"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("f4b82c86-c0f3-4eec-a572-aa61fa631a37"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Angola24Horas (angola24horas.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ae174983-a297-44ef-94b3-ce34f78252f2"),
        url_pattern=re_compile(r"^https?://[^/]+/mais/[^/]+/pesquisar\?"),
        parameter="searchword",
    ),
    # Provider: 全球塑胶网 (51pla.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/buyinfo/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/company/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/price/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/product/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("e4c7553c-81ed-4b88-9777-5764ed65f028"),
        url_pattern=re_compile(r"^https?://[^/]+/spec/search\?"),
        parameter="q",
    ),
    # Provider: QIP (mcls.xyz)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7fa0b4a4-a3e4-4e5c-9879-d8723727a20b"),
        url_pattern=re_compile(r"^https?://[^/]+/results\.php\?"),
        parameter="wd",
    ),
    # Provider: Jacquie Lawson (jacquielawson.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2f4b5ee3-aa5b-43ef-8648-648025b803d4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Asianload (asianhdplay.pro)
    QueryParameterUrlQueryParser(
        provider_id=UUID("eceaf23a-512a-4670-8f2d-09fa9abe9363"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="keyword",
    ),
    # Provider: Notjustok (notjustok.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2ab9ced2-0350-42d8-8aa7-ad2ade39904b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: PPTV HD 36 (pptvhd36.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8b61a987-e399-4e8a-a75c-3f38df601a42"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: SideReel (sidereel.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d2c1ea05-5bf6-4884-8fed-799802a1215e"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[^/]+"),
        segment=3,
    ),
    # Provider: Sopitas.com (sopitas.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d87279cb-3fe3-4e0d-bc4b-6610f3996099"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: SearchAlgo (searchalgo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2905ade4-8dbc-4658-84bb-95d1e59bf79e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="q",
    ),
    # Provider: The Institute for Health Metrics and Evaluation (healthdata.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ab4dc1f-186a-49eb-85aa-5de655e95933"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search_terms",
    ),
    # Provider: เว็บดูหนังออนไลน์ i-MovieHD (imovie-hd.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("935891b0-f1cb-4cd9-9348-27da3033ee14"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: پیشنهاد ویژه (pishnahadevizheh.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("936e6dd5-d991-4ef4-a4ca-238fb5584d40"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/newsstudios/archive/\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("936e6dd5-d991-4ef4-a4ca-238fb5584d40"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/\?"),
        parameter="query",
    ),
    # Provider: خبرگزاری موج (mojnews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4bc98471-167d-4cc2-9cb6-31ef0d33330a"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/newsstudios/search\?"),
        parameter="gsc.q",
    ),
    # Provider: 中工网 (workercn.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fa82b3a4-eb40-44ab-b460-7c1db829fa97"),
        url_pattern=re_compile(r"^https?://[^/]+/search/result.shtml\?"),
        parameter="query",
    ),
    # Provider: WeaPlay (weadown.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4c8978cb-58c8-4caa-acbd-5f4bdd3ac140"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("4c8978cb-58c8-4caa-acbd-5f4bdd3ac140"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Hentai Haven (hentaihaven.xxx)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f30bb838-8463-42e6-842e-2a1c23f9bcba"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: WebHostingTalk (webhostingtalk.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7c47f364-b486-460d-9feb-3c8cc29c3759"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="searchid",
    ),
    # Provider: DonTorrent (dontorrent.fun)
    PathSegmentUrlQueryParser(
        provider_id=UUID("0c7057e0-9491-4f9e-9657-b6fc62760399"),
        url_pattern=re_compile(r"^https?://[^/]+/buscar/[^/]+"),
        segment=2,
    ),
    # Provider: z3.fm (z3.fm)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d82bc7ec-69a3-4ace-a1c0-512539b0ba06"),
        url_pattern=re_compile(r"^https?://[^/]+/mp3/search\?"),
        parameter="keywords",
    ),
    # Provider: هير نيوز (her-news.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("53182eac-a03f-4fa1-87cd-2b5fd29e37b0"),
        url_pattern=re_compile(r"^https?://[^/]+/list\.aspx\?"),
        parameter="w",
    ),
    # Provider: خوندنی (khoondanionline.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3240b96e-42e3-4959-9850-35cc65682eea"),
        url_pattern=re_compile(r"^https?://[^/]+/fa/newsstudios/archive/\?"),
        parameter="query",
        remove_pattern=re_compile(r"\+"),
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3240b96e-42e3-4959-9850-35cc65682eea"),
        url_pattern=re_compile(r"^https?://[^/]+/newsstudios/archive/\?"),
        parameter="query",
    ),
    # Provider: The Pirate Bay (pirateproxy.lat)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5b0d6f76-f59f-41f5-9dcc-be6ce4caa7a9"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="q",
    ),
    # Provider: aufeminin.com (aufeminin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5cee89de-b0b1-4bfa-acc3-aabfa10e1377"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="kw",
    ),
    # Provider: الرياض نيوز (alriyadh.news)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0deb9ea7-ec65-4fa4-b53f-1a1c0bd61583"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: L’Assurance retraite (lassuranceretraite.fr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6f5f632f-d24a-4618-b66d-2ac83cbf9b71"),
        url_pattern=re_compile(r"^https?://[^/]+/.*/resultat-de-recherche\.html\?"),
        parameter="searchedText",
    ),
    # Provider: IN.com (in.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0cb6c26f-e9ea-4fad-8210-51271378b4a2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Sharp (jp.sharp)
    QueryParameterUrlQueryParser(
        provider_id=UUID("74a5a3c8-783f-4ba1-9f8d-1d5dbfdcd41d"),
        url_pattern=re_compile(r"^https?://[^/]+/search/index\.html"),
        parameter="q",
    ),
    # Provider: JavDB (javdb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("464b3f84-541e-45bf-a5aa-8eb1969ffef6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: PornerBros (pornerbros.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("34d6c064-a76e-4696-b3a4-26ea15b712b3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 1+1 Video (1plus1.video)
    QueryParameterUrlQueryParser(
        provider_id=UUID("91968204-fdc5-466b-8f24-2f4a820c2d2c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="query",
    ),
    # Provider: Porn Medium (pornmedium.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ee34e08-b4bf-4174-bcc9-9c18d629e7b8"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: search.ch (search.ch)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b940b181-da03-481c-a5de-3b3860dd1b45"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: 北京教育考试院 (bjeea.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8793daba-99ca-4cb2-9090-f36bad4efb67"),
        url_pattern=re_compile(r"^https?://[^/]+/plus/search\.php\?"),
        parameter="q",
        remove_pattern=re_compile(r"\+"),
    ),
    # Provider: أكادير انفو (agadirinfo.ma)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0785df41-367b-40ab-ba06-60a0ce22a4cb"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: هبة سبور (hibasport.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f9f8dfd8-69aa-4dee-8c7f-c6d1c7f0c4ca"),
        url_pattern=re_compile(r"^https?://[^/]+/?"),
        parameter="s",
        remove_pattern=re_compile(r"\+"),
    ),
    # Provider: dogpile (dogpile.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("af246cce-08a8-447a-8a48-8af7266d5981"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="q",
    ),
    # Provider: Amateur 8 (amateur8.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d441e21f-0f15-4721-bf82-34b8d595bfdf"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Pron.tv (mypron.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("32b9c760-7aa4-499f-a062-3a4f8f0ffb6c"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/search/[^/]+"),
        segment=3,
    ),
    # Provider: JustPorno.TV (justporno.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("c9b39ad1-f23a-4a8e-be13-db0fd828fa20"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(girls|boys|tranny)/[^/]"),
        segment=3,
    ),
    # Provider: Ligue Imóvel (ligueimovel.ao)
    QueryParameterUrlQueryParser(
        provider_id=UUID("24036afe-1c74-4c23-b352-9be4d70693ac"),
        url_pattern=re_compile(r"^https?://[^/]+/pesqusiar-imovel/\?"),
        parameter="keyword",
    ),
    # Provider: 123movies (123movies.fun)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b70e078d-c6c1-4807-bf14-194d22b41758"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="q",
    ),
    # Provider: Mature Tube here (maturetubehere.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("59d99097-16fb-468b-a29f-88579784ad34"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/\?"),
        segment=2,
    ),
    # Provider: PornTop.com (porntop.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("09373ee0-5fd0-48a9-93a0-edcb9d9f31b4"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: خبرنامه (khabarnama.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0f5f4238-2587-42fa-aa38-c1f7e18fee67"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Naija News (naijanews.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7d326758-4efe-4523-a58a-1121ed097165"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("7d326758-4efe-4523-a58a-1121ed097165"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: SEXSEQ (sexseq.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("48ac3be4-3906-49b0-a4e9-e8b4401603c6"),
        url_pattern=re_compile(r"^https?://[^/]+/trends/[^/]+"),
        segment=2,
    ),
    # Provider: Gaming Wonderland (gamingwonderland.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cae65ab0-e336-47c4-9670-01b56184a16b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Jomys (jomys.xyz)
    QueryParameterUrlQueryParser(
        provider_id=UUID("222b2c1d-a658-4938-81da-b217e09074c5"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.php\?"),
        parameter="search",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("222b2c1d-a658-4938-81da-b217e09074c5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: 中国搜索 (chinaso.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/all"),
        parameter="allResults",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/block"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/game"),
        parameter="gameResults",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/image\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/social"),
        parameter="socialResults",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/story"),
        parameter="storyResults",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/video\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("a0b4ea88-77f7-4d22-b627-907e79e2bf60"),
        url_pattern=re_compile(r"^https?://[^/]+/newssearch/young\?"),
        parameter="q",
    ),
    # Provider: 漫猫动漫 (comicat.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("57c6b6fd-d915-4b8e-98fd-9c83d20a0743"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="keyword",
    ),
    # Provider: Manga Fox (fanfox.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("84774e22-f12e-4372-93d1-14ced15ec2de"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="title",
    ),
    # Provider: Hell Porno (hellporno.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dccf0a94-ba06-498d-a221-3165b07bcea9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("dccf0a94-ba06-498d-a221-3165b07bcea9"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[0-9]+/\?"),
        parameter="q",
    ),
    # Provider: Sarcasm (sarcasm.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1bde6ae8-906c-4906-b12b-ca2a582894f5"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: 俺のエロ本 (oreno-erohon.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3eff1424-bebf-430e-af61-fa29c5dcf934"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("3eff1424-bebf-430e-af61-fa29c5dcf934"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Putlocker (putlockers.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1ae9fcaf-3b4d-463e-9fb6-ea088c1e23a8"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="s",
    ),
    # Provider: 中华人民共和国教育部 (moe.gov.cn)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d3aecc47-6597-4e66-b09c-f1063b3c5b1d"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="qt",
    ),
    # Provider: IBTimes (ibtimes.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dcd1db5c-31c9-4fa8-886f-f0d93c11003f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/site\?"),
        parameter="q",
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("dcd1db5c-31c9-4fa8-886f-f0d93c11003f"),
        url_pattern=re_compile(r"^https?://[^/]+/search/site/[^/]+"),
        segment=3,
    ),
    # Provider: BlackFriday.com (blackfriday.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("32059869-8f93-43ad-ad27-c27afada5350"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results\?"),
        parameter="q",
    ),
    # Provider: 返利 (fanli.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("724b44c1-2b0b-483e-83a4-d7b294467535"),
        url_pattern=re_compile(r"^https?://[^/]+/client/search"),
        parameter="keyword",
    ),
    # Provider: CES (ces.tech)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ee8864ce-a822-4be7-82f3-9f81d856e7f8"),
        url_pattern=re_compile(r"^https?://[^/]+/search-results\.apsx\?"),
        parameter="searchtext",
    ),
    # Provider: ESPN (espnfc.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f10506fa-58df-426d-b93e-7d840c107de8"),
        url_pattern=re_compile(r"^https?://[^/]+/search/_/q/[^/]+"),
        segment=4,
    ),
    # Provider: The Western Journal (westernjournalism.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8f53efb7-a0bf-4800-a6dd-92c1beae2f5f"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: أسواق للمعلومات (aswaqinformation.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("23c20c00-5a78-4d2b-a09f-4c09929df494"),
        url_pattern=re_compile(r"^https?://[^/]+/section"),
        parameter="keyword",
    ),
    # Provider: Fanpage (fanpage.gr)
    PathSegmentUrlQueryParser(
        provider_id=UUID("80b1810e-9871-436e-b34e-4efe4607b33c"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: EliteTorrent (elitetorrent.io)
    QueryParameterUrlQueryParser(
        provider_id=UUID("658a7b66-b14f-4ceb-a191-9a0b764e9d9e"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: HostGator (hostgator.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("006a61ef-c58e-4cc5-90f9-867bd16318a9"),
        url_pattern=re_compile(r"^https?://[^/]+/busca\?"),
        parameter="s",
    ),
    # Provider: Web Stagram (stagram.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("55b6e643-ae8b-4b96-8a63-817a2ca1af24"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: الصفوة (sfwaa.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("07fc61d4-7a89-44b1-8cfd-d6f7986771a1"),
        url_pattern=re_compile(r"^https?://[^/]+/section"),
        parameter="keyword",
    ),
    # Provider: MMA Mania (mmamania.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("615534b9-49a0-40a6-af82-226dd549549c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: ASG.TO (asg.to)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cc0e6857-7647-4bb1-8a8c-0b09dbf2cee3"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: BlackBerry (blackberry.com)
    FragmentParameterUrlQueryParser(
        provider_id=UUID("5c6957ed-50a3-4cb2-8a36-8bce9b757b08"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[a-z]+/search#q"),
        parameter="q",
    ),
    # Provider: Bloody Elbow (bloodyelbow.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("54aed98f-7dee-468b-8e07-c7e23b0676d4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: PlugRush (plugrush.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f8c5e565-a3da-4d47-b858-5b689a316d74"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("f8c5e565-a3da-4d47-b858-5b689a316d74"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: SEOBook (seobook.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("763f786a-8165-490e-95b7-761af63433bc"),
        url_pattern=re_compile(r"^https?://[^/]+/sitesearch/"),
        parameter="q",
    ),
    # Provider: ByRutor.comByRutor.com (byrutor.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4850b309-3660-4fa7-99ac-f4dec1d538b1"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="story",
    ),
    # Provider: Justindianporn.me (justindianporn.me)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bd5edd10-228a-4e33-a0dc-992d445fd508"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Músicas para Missa (musicasparamissa.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a10538cb-a154-4533-af51-88bd35e17cfd"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Recommendation Letters (recommendationletters.pro)
    QueryParameterUrlQueryParser(
        provider_id=UUID("63f0b6d4-da27-4807-a208-1f2817d7d56c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: 123 Greetings (123greetings.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("eb9e8c9b-31d1-4b57-88a0-50854d757f8b"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search/search\.pl\?"),
        parameter="query",
    ),
    # Provider: Kwork (kwork.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6b051f83-0b97-4c9d-97f2-a7da12e44c43"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Единая Россия (er.ru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c2ecfa24-e9a8-4565-86de-7181e4a9869a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c2ecfa24-e9a8-4565-86de-7181e4a9869a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: India Herald (apherald.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("f288d3aa-8f16-4220-baa7-cdfda216f3a6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[a-z]+/[^/]+"),
        segment=3,
    ),
    # Provider: TLnet (teamliquid.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9077f762-e359-4e24-979e-7fe10e5fda9f"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: JobStreet (jobstreet.com.sg)
    PathSegmentUrlQueryParser(
        provider_id=UUID("02b4a425-deba-4d4d-b54a-e30372ccb4b2"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/job-search/[^/]+"),
        segment=3,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("02b4a425-deba-4d4d-b54a-e30372ccb4b2"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/companies/browse-reviews\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("02b4a425-deba-4d4d-b54a-e30372ccb4b2"),
        url_pattern=re_compile(r"^https?://[^/]+/career-resources/search\?"),
        parameter="q",
    ),
    # Provider: AngoVagas (angovagas.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9335de96-a119-4723-a5b6-89f45d9c0151"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9335de96-a119-4723-a5b6-89f45d9c0151"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Searchengines.guru (searchengines.guru)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b9d24136-eca3-4f8e-a350-dbf18c7d7d9f"),
        url_pattern=re_compile(r"^https?://[^/]+/(en|ru)/search"),
        parameter="keyword",
    ),
    # Provider: Cooch.tv (cooch.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("4e6c9864-a484-452e-b6d1-ab099aa7d4f4"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/[^/]+/[0-9]+\.html"),
        segment=3,
    ),
    # Provider: Canal Tutorial (canaltutorial.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("24b6d8a5-ed91-45ef-99fd-dad8ca4dfbc1"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("24b6d8a5-ed91-45ef-99fd-dad8ca4dfbc1"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: هنتاي تايم (hentai-time.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("da31e49e-9afe-4643-a9ce-46b0321bd2d6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("da31e49e-9afe-4643-a9ce-46b0321bd2d6"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: World News (wn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("74c7cdaa-32b9-4d6c-ae92-56ce997e16b0"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="search_string",
    ),
    # Provider: Shodan (shodan.io)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7b1ae7ee-e273-48ab-ac8a-47a3cd0e5e48"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: WooCommerce (woothemes.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9ea9b48e-ab51-4cbb-bde5-eec8f04b1533"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Open Site Explorer (opensiteexplorer.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("eb1c148d-91f8-4bec-a887-268b86f0eaba"),
        url_pattern=re_compile(r"^https?://[^/]+/links"),
        parameter="site",
    ),
    # Provider: xxxhdvideo.mobi (xxxhdvideo.mobi)
    PathSegmentUrlQueryParser(
        provider_id=UUID("d51d0954-7454-41d8-838d-d6f1afe4cd4c"),
        url_pattern=re_compile(r"^https?://[^/]+/sex/[^/]+"),
        segment=2,
    ),
    # Provider: 中天電視 (ctitv.com.tw)
    QueryParameterUrlQueryParser(
        provider_id=UUID("01d6d4f5-6e18-4c2d-8a4c-1f1be902c0a0"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("01d6d4f5-6e18-4c2d-8a4c-1f1be902c0a0"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Türkmenistan Habar (turkmenistanhabar.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7088e592-c4dd-4160-8b96-7676e5462fb7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Liftable (liftable.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("043c803d-9028-43e4-9a4f-6fb6beb4faa7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("043c803d-9028-43e4-9a4f-6fb6beb4faa7"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider:  IMzog (imzog.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("80345c90-c3ea-4232-a7c5-1e6a5f13e6ae"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+"),
        segment=3,
    ),
    # Provider: 4udear (4udear.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("568c3487-042a-4352-b4a8-1ccd49df1c9f"),
        url_pattern=re_compile(r"^https?://[^/]+/se/search\?"),
        parameter="query",
    ),
    # Provider: Layarkaca21 (dunia21.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7ebf3c45-47d4-47a2-b0f2-418fc55a2909"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Majestic (majesticseo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0d85fd51-e5ad-45fb-aa08-19c3d605d950"),
        url_pattern=re_compile(r"^https?://[^/]+/reports/site-explorer\?"),
        parameter="q",
    ),
    # Provider: ViralNova (viralnova.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("176886ca-2705-4784-b9ec-336910841d80"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("176886ca-2705-4784-b9ec-336910841d80"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Metacrawler (metacrawler.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5dcb661f-4094-490e-89d3-58d8e8010d65"),
        url_pattern=re_compile(r"^https?://[^/]+/serp\?"),
        parameter="q",
    ),
    # Provider: Tickld (tickld.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("38c31683-0b8c-48b3-9fd9-e38defa20fb2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        segment=2,
    ),
    # Provider: Websta (websta.me)
    QueryParameterUrlQueryParser(
        provider_id=UUID("da02c58e-e127-41f4-86a3-98e74060de37"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("da02c58e-e127-41f4-86a3-98e74060de37"),
        url_pattern=re_compile(r"^https?l://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: XGap (xgap.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("95ed525b-e3c4-407f-8231-4094c9791066"),
        url_pattern=re_compile(r"^https?://[^/]+/en/search/[^/]+/[0-9]+\.html"),
        segment=3,
    ),
    # Provider: أنا حوا (anahwa.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("79011d3c-3bfa-415b-9be6-d7b8f9fc00fb"),
        url_pattern=re_compile(r"^https?://[^/]+/section"),
        parameter="keyword",
    ),
    # Provider: mBank (mbank.com.pl)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ac4db475-1ef3-4960-aac6-11b04f72e28f"),
        url_pattern=re_compile(r"^https?://[^/]+/szukaj"),
        parameter="query",
    ),
    # Provider: Сергей Мавроди (sergey-mavrodi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("56443876-8b10-415f-ac31-818759ae092e"),
        url_pattern=re_compile(r"^https?://[^/]+/spage/\?"),
        parameter="search_q",
    ),
    # Provider: Nhà Đất Số (nhadatso.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9554d90d-19cf-45f3-a76f-c8707833a918"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: skat.dk (skat.dk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("aeda1dc1-8c3a-4a7c-acc0-4a5c5c868957"),
        url_pattern=re_compile(r"^https?://[^/]+/data\.aspx\?"),
        parameter="cludoquery",
    ),
    # Provider: Foros del Web (forosdelweb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9810c4b-a34b-4d97-a03b-df2e15516ec8"),
        url_pattern=re_compile(r"^https?://[^/]+/misc\.php\?"),
        parameter="q",
    ),
    # Provider: SEB (seb.se)
    QueryParameterUrlQueryParser(
        provider_id=UUID("66cec6f9-fe3c-4d0d-ac1e-59e1b96e02d3"),
        url_pattern=re_compile(r"^https?://[^/]+/systemsidor/sok\?"),
        parameter="s",
    ),
    # Provider: Kiddle (kiddle.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f0b94471-dbf4-4cb0-ae1d-f489e8b39fc1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\.php\?"),
        parameter="q",
    ),
    # Provider: eCRATER (ecrater.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("72d69cbf-f7f2-4bd6-86f5-e108df7faf53"),
        url_pattern=re_compile(r"^https?://[^/]+/filter\.php\?"),
        parameter="keywords",
    ),
    # Provider: Eurovision Song Contest (eurovision.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("baeb5c1b-e668-4bdd-bc56-2beb43788b8f"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search",
    ),
    # Provider: Sportsala (sportsala.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("608207c6-fa62-4133-b3cf-0c292fdf39a3"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("608207c6-fa62-4133-b3cf-0c292fdf39a3"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Egotastic (egotastic.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9ca1229d-a7fa-4d8c-a0fd-5c8a4bdc74dc"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Ah Me (ah-me.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("83027581-7f28-4e93-9749-5c4ddaac3af6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/page[0-9]+\.html"),
        segment=2,
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("83027581-7f28-4e93-9749-5c4ddaac3af6"),
        url_pattern=re_compile(r"^https?://[^/]+/pics/search/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: Uploading.com (uploading.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4366d9eb-8016-4b7f-9ebc-6d75f355ba48"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: stock.xchng (sxc.hu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("490daf6a-dfc6-4478-bed9-a9ecaec189bb"),
        url_pattern=re_compile(r"^https?://[^/]+/browse\.phtml\?"),
        parameter="txt",
    ),
    # Provider: ELLE (ellechina.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("dee5874c-4351-46a2-9287-c4b2e8ed31d7"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Lycos (lycos.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("13f8aa6c-8113-4b87-b116-88a988214826"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("13f8aa6c-8113-4b87-b116-88a988214826"),
        url_pattern=re_compile(r"^https?://[^/]+/web/\?"),
        parameter="q",
    ),
    # Provider: EMBL-EBI (ebi.ac.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("45acd561-a093-4196-83a3-f3e88a27996c"),
        url_pattern=re_compile(r"^https?://[^/]+/ebisearch/search"),
        parameter="query",
    ),
    # Provider: Mayo Clinic (mayoclinic.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("67a8bb04-9df6-42d2-bb37-d569235f386b"),
        url_pattern=re_compile(r"^https?://[^/]+/search/search-results\?"),
        parameter="q",
    ),
    # Provider: Shopping.com (shopping.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ea817c7-02bc-46e3-999a-229061f04ab9"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="keyword",
    ),
    # Provider: Manga Raw (manga9.co)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a7dafc24-3bf1-4ee0-a13c-e0d23fc905ec"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Hyves Games (hyves.nl)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6b254ca9-13ab-4c1d-a9a9-27181c97621a"),
        url_pattern=re_compile(r"^https?://[^/]+/zoeken/\?"),
        parameter="s",
    ),
    # Provider: CiteAb (citeab.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c5293e-1252-4592-8692-3bd70b381b19"),
        url_pattern=re_compile(r"^https?://[^/]+/antibodies/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c5293e-1252-4592-8692-3bd70b381b19"),
        url_pattern=re_compile(r"^https?://[^/]+/biochemicals/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c5293e-1252-4592-8692-3bd70b381b19"),
        url_pattern=re_compile(r"^https?://[^/]+/experimental-models/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c5293e-1252-4592-8692-3bd70b381b19"),
        url_pattern=re_compile(r"^https?://[^/]+/kits/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7c5293e-1252-4592-8692-3bd70b381b19"),
        url_pattern=re_compile(r"^https?://[^/]+/proteins/search\?"),
        parameter="q",
    ),
    # Provider: Porn 24 TV (porn24.tv)
    PathSegmentUrlQueryParser(
        provider_id=UUID("24577ff5-b90c-4417-a1f3-df3d177800ee"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+/[0-9]+\.html"),
        segment=3,
    ),
    # Provider: Pornhost (pornhost.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("ff7883ef-f22f-4151-aa7f-3f4b2193311d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="search",
    ),
    # Provider: TubeREL (tuberel.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("597039e4-1117-40b8-8877-b3e7a8402dde"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search/[^/]+"),
        segment=3,
    ),
    # Provider: السبورة (alsbbora.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3137763d-5b52-4673-ba8b-3a9d44d99689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/"),
        parameter="w",
    ),
    # Provider: Nyaa (nyaa.eu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("3cfcdf39-87e6-4302-b303-84bcd3b67c81"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="term",
    ),
    # Provider: Goveme (govome.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("62604dcf-2807-4888-8a5a-6d23c909b959"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: forexmetatradexdx.info (forexmetatradexdx.info)
    QueryParameterUrlQueryParser(
        provider_id=UUID("923ecc11-82d2-4735-940d-1bd0be63552b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: 樱花动漫 (yhdmw.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("89930ee5-1c5f-46a5-8ca2-61b8e393dafc"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+search"),
        parameter="wd",
    ),
    # Provider: 生意社 (100ppi.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("bd6d2ab7-fe2c-4197-8788-040d22217bb6"),
        url_pattern=re_compile(r"^https?://[^/]+/mprice/\?"),
        parameter="terms",
    ),
    # Provider: FilmStreaming2 (filmstreaming2.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("261e61f0-cd29-4baa-af75-3d13657f68f5"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.json\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("261e61f0-cd29-4baa-af75-3d13657f68f5"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: 楚天视界 (ct10000.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a8973cf2-a22c-4f9f-911c-86032ccf7baa"),
        url_pattern=re_compile(r"^https?://[^/]+/s\.html\?"),
        parameter="key",
    ),
    # Provider: WapWon (wapwon.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("7c9c069c-28dc-4c4c-92e6-04b113fa505d"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/"),
        segment=1,
    ),
    # Provider: AvaxHome (avaxhome.ws)
    QueryParameterUrlQueryParser(
        provider_id=UUID("99b9818b-0980-4c0f-b84f-7afdfbc798fc"),
        url_pattern=re_compile(r"^https?://[^/]+/avaxhome_search\?"),
        parameter="q",
    ),
    # Provider: The Royal Household (royal.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("785ef9bd-9385-4e1e-a0c8-eed1b80a6664"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="tags[]",
    ),
    # Provider: 愛經驗 (how01.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1e87c232-3d1b-4044-81a3-3369ff9ed85e"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: برامج جي سوفت (jsoftj.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a7eee715-8f8f-45cb-9088-bf8c3f6bc67b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: TV Links (tv-links.eu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c4e594b6-4df0-4bb7-83b5-66a8e3e3584b"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: SlidePlayer (slideplayer.com.br)
    QueryParameterUrlQueryParser(
        provider_id=UUID("a28f1776-0461-4df2-9445-e11db8b2a689"),
        url_pattern=re_compile(r"^https?://[^/]+/search/\?"),
        parameter="q",
    ),
    # Provider: Lenine Tudo (leninetudo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("30a66935-9361-4f0a-8742-a4d26e903d99"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: zooplus (zooplus.hu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("731c5c13-9e57-45ca-a0e0-affabcac9448"),
        url_pattern=re_compile(r"^https?://[^/]+/search/results\?"),
        parameter="q",
    ),
    # Provider: Autoproyecto (autoproyecto.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("94ce6cb1-2a0e-49b0-bd60-f773625832a8"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("94ce6cb1-2a0e-49b0-bd60-f773625832a8"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: MarkosWeb (markosweb.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5c60e797-b0b9-4d8b-8b88-e79c027a0912"),
        url_pattern=re_compile(r"^https?://[^/]+/s"),
        parameter="qsc.q",
    ),
    # Provider: پارسی جو (parsijoo.ir)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fc72f433-1823-40fb-8656-553cd5fe8111"),
        url_pattern=re_compile(r"^https?://[^/]+/*.\?"),
        parameter="q",
    ),
    # Provider: مخزن (m5zn.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c2f50eb0-14d4-41bf-ae15-7a2d276f253f"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("c2f50eb0-14d4-41bf-ae15-7a2d276f253f"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: 抠抠网 (oomall.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f32af085-2180-40c8-8436-f32c90eec0d2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: Kelkoo (kelkoo.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d4a76357-195d-40e0-9fa2-4cc467ed7b00"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("d4a76357-195d-40e0-9fa2-4cc467ed7b00"),
        url_pattern=re_compile(r"^https?://[^/]+/suche\?"),
        parameter="anfrage",
    ),
    # Provider: Shentai (shentai.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9daa83ed-a31c-4903-92d5-1592610d6b10"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9daa83ed-a31c-4903-92d5-1592610d6b10"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Hot Sale (hotsale.com.ar)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1ec7c017-4661-4238-8679-c484b50a4fc8"),
        url_pattern=re_compile(r"^https?://[^/]+/ofertas"),
        parameter="q",
    ),
    # Provider: جورنال مصر (misrjournal.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("44d3efce-2a39-44fe-ac2b-0ae03611bcc6"),
        url_pattern=re_compile(r"^https?://[^/]+/search/node\?"),
        parameter="keys",
    ),
    # Provider: Shopzilla (shopzilla.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("75c28e9c-da09-47e2-abaf-9e13ccf87a29"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/products/[^/]+"),
        segment=3,
        space_pattern=re_compile(r"-"),
    ),
    PathSegmentUrlQueryParser(
        provider_id=UUID("75c28e9c-da09-47e2-abaf-9e13ccf87a29"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/[^/]+/products/"),
        segment=2,
        space_pattern=re_compile(r"-"),
    ),
    # Provider: PriceGrabber (pricegrabber.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("fb204525-e2a8-4d8e-8c03-8e736b497c37"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/products/"),
        segment=1,
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("fb204525-e2a8-4d8e-8c03-8e736b497c37"),
        url_pattern=re_compile(r"^https?://[^/]+/classify\?"),
        parameter="keyword",
    ),
    # Provider: Blinkx (blinkx.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("af537770-cf02-4d98-a402-467cfd69a0c6"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/[^/]+"),
        segment=2,
    ),
    # Provider: Tu.Tv (tu.tv)
    QueryParameterUrlQueryParser(
        provider_id=UUID("adbbbf6c-1416-4511-a141-8cb3f3c022bf"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: GlobalSpec (globalspec.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/article/search"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/all"),
        parameter="query",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("9a6170ec-9498-4904-9f5c-ee8e85cb9ac2"),
        url_pattern=re_compile(r"^https?://[^/]+/search/reference"),
        parameter="query",
    ),
    # Provider: Petal Search (petalsearch.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c9223006-4a0e-479f-8445-7847a48ea9ed"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: Suite 101 (suite101.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("18034ff2-77b0-4b4f-96c6-ef0d9ef5e1a2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.cfm\?"),
        parameter="q",
    ),
    # Provider: Watch Series (watchseries.cr)
    QueryParameterUrlQueryParser(
        provider_id=UUID("872fe46f-0328-48e8-85b9-93997d2f8123"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="s",
    ),
    # Provider: Comboios de Portugal (cp.pt)
    QueryParameterUrlQueryParser(
        provider_id=UUID("465eccde-a010-443b-9c67-29bfd1064594"),
        url_pattern=re_compile(r"^https?://[^/]+/passageiros/pt/resultados-pesquisa\?"),
        parameter="q",
    ),
    # Provider: Badjojo (badjojo.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9753b480-b174-4bdd-a7b9-385b28a38fe7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: 1001Jogos.pt (1001jogos.pt)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9cf63eb7-4c1a-40cd-9f65-bfd5ace57695"),
        url_pattern=re_compile(r"^https?://[^/]+/procurar"),
        parameter="q",
    ),
    # Provider: International Consortium of Investigative Journalists (icij.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("7f3d4d7e-8db4-4c5f-b4ad-0abaaf2662ca"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("7f3d4d7e-8db4-4c5f-b4ad-0abaaf2662ca"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Türkmenistanyň Dokma Senagaty Ministrligi (textile.gov.tm)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2854b56b-2a38-4418-9ea2-9d1d4318f7ae"),
        url_pattern=re_compile(r"^https?://[^/]+/site/search\?"),
        parameter="SearchForm[title]",
    ),
    # Provider: Earth Day (earthday.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("26a0fd62-d39c-45ee-8e8b-606590666ed7"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Adzuna (adzuna.co.uk)
    QueryParameterUrlQueryParser(
        provider_id=UUID("6ea49e2e-163c-4dd8-a8aa-bc6b75cf2274"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs/search\?"),
        parameter="q",
    ),
    # Provider: grumbleoh.com (grumbleoh.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4db35c85-7645-4491-9f53-2f10ffd580d2"),
        url_pattern=re_compile(r"^https?://[^/]+/watch.[0-9]+\.js\?"),
        parameter="kw",
    ),
    # Provider: My Beauty Land (mybeautylands.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c7a88060-8704-4fe5-890d-e4c82732af42"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="search_query",
    ),
    # Provider: PriceRunner (pricerunner.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cb6db8d9-bec3-4d60-b037-a5f8c4b28d34"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        parameter="q",
    ),
    # Provider: You.com (you.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1fc32965-56f9-464e-9cc5-4127f2f4e868"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: business.com (business.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("423222e9-be74-4db8-8777-7e45ba90a9fa"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Vietxx.Org (vietxx.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("164291f8-bfb7-4051-b7e2-be9e94db9313"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: The Gudda (thegudda.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("433d38b3-a881-41a6-921c-2641c6bbc14c"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("433d38b3-a881-41a6-921c-2641c6bbc14c"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: lo.st (lo.st)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9037c07-f558-4d73-96b3-9b5579b924df"),
        url_pattern=re_compile(r"^https?://[^/]+/cgi-bin/eolost\.cgi\?"),
        parameter="x_query",
    ),
    # Provider: Heroturko (heroturko.org)
    PathSegmentUrlQueryParser(
        provider_id=UUID("e76b459a-2d2d-4ab1-8753-09eb477bd9c3"),
        url_pattern=re_compile(r"^https?://[^/]+/[0-9]+/[^/]+"),
        segment=2,
    ),
    # Provider: Kino.to (kino.to)
    QueryParameterUrlQueryParser(
        provider_id=UUID("104950cf-da26-457c-9b12-6957092be2e7"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\.html\?"),
        parameter="q",
    ),
    # Provider: Sourcecodester.com (sourcecodester.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b3856872-c146-4080-8827-5332f95c36c0"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: XXXComics.org (xxxcomics.org)
    QueryParameterUrlQueryParser(
        provider_id=UUID("fae911a1-1fbe-4088-b63e-579e1740e786"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: BTCMANAGER (btcmanager.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4b04b5e9-970e-441d-b1b3-d429eb91282f"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Jet Boobs (jetboobs.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("69422465-7293-4352-b0f1-6c758e3ba113"),
        url_pattern=re_compile(r"^https?://[^/]+/en/[0-9]+/[^/]+/[0-9]+\.html"),
        segment=3,
    ),
    # Provider: Wazap! (wazap.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1a9fcf03-39a6-42a0-ab49-1b53b1a57f41"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.wz\?"),
        parameter="q",
    ),
    # Provider: Trendy Mall (trendymalldeals.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("80206b75-5939-4c6f-9b72-bcefffa3025c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="query",
    ),
    # Provider: My Chic Consulting (mychicconsulting.es)
    QueryParameterUrlQueryParser(
        provider_id=UUID("aa896c31-3ca1-471d-a869-caa10bff530f"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("aa896c31-3ca1-471d-a869-caa10bff530f"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: Picsearch (picsearch.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("9adbcc54-b742-421d-85e3-0923144732c3"),
        url_pattern=re_compile(r"^https?://[^/]+/index\.cgi\?"),
        parameter="q",
    ),
    # Provider: KidzSearch (kidzsearch.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("83aa1880-9a2c-4f04-92c1-9afb205c9eed"),
        url_pattern=re_compile(
            r"^https?://[^/]+/kz(?:image|video|facts|wiki|news|game|app)?search\.php\?"
        ),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("83aa1880-9a2c-4f04-92c1-9afb205c9eed"),
        url_pattern=re_compile(r"^https?://[^/]+/kidztube/search\.php\?"),
        parameter="keywords",
    ),
    # Provider: Najdi.si (najdi.si)
    PathSegmentUrlQueryParser(
        provider_id=UUID("19b3764d-7184-453e-b43d-5785360d426d"),
        url_pattern=re_compile(r"^https?://[^/]+/najdi/[^/]+"),
        segment=2,
    ),
    # Provider: MetaGer (metager.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0f805bab-0cf3-4ad5-bf05-311dfe5056b6"),
        url_pattern=re_compile(r"^https?://[^/]+/meta/meta\.ger3\?"),
        parameter="eingabe",
    ),
    # Provider: Omgili (omgili.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("b3796e78-3a06-448d-8227-9b3ad4c7cadb"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Gigablast (gigablast.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("8fbcbf4f-e571-4c03-abbd-77a857344105"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: Mojeek (mojeek.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("74ee3c4a-1cb5-4d0f-928e-f42f8c0200a4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: args.me (args.me)
    QueryParameterUrlQueryParser(
        provider_id=UUID("05fb19ff-b8c4-4b47-b18a-4493e2df57f4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="query",
    ),
    # Provider: Bielefeld Academic Search Engine (base-search.net)
    QueryParameterUrlQueryParser(
        provider_id=UUID("f89ecd33-9ced-493e-939d-3e99d578bee4"),
        url_pattern=re_compile(r"^https?://[^/]+/Search/Results\?"),
        parameter="lookfor",
    ),
    # Provider: ChatNoir (chatnoir.eu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("e9a0e2d3-390f-4832-9805-40067771b1bf"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="q",
    ),
    # Provider: ChemRefer (chemrefer.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4ed8432b-a6ca-4e1f-af05-84dafbce05bc"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    # Provider: Egerin (egerin.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("df552e5f-5a82-441f-8fc9-302ed58b1401"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Fireball (fireball.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("5f61ae00-36d5-4991-a5a7-5d1c9594bbe1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("5f61ae00-36d5-4991-a5a7-5d1c9594bbe1"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search\?"),
        parameter="q",
    ),
    # Provider: Digital Genie (genieknows.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("2fcabf98-a825-4cf6-8df2-b2be82ca705a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("2fcabf98-a825-4cf6-8df2-b2be82ca705a"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: leit.is (leit.is)
    QueryParameterUrlQueryParser(
        provider_id=UUID("98cf9ba4-a44e-4075-ac18-4d9f09767276"),
        url_pattern=re_compile(r"^https?://[^/]+/(leita|company_search)\?"),
        parameter="search",
    ),
    # Provider: Miner (miner.hu)
    QueryParameterUrlQueryParser(
        provider_id=UUID("13fc4e4d-b2fb-441d-a434-647989fafc7a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="s",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("13fc4e4d-b2fb-441d-a434-647989fafc7a"),
        url_pattern=re_compile(r"^https?://[^/]+/page/[0-9]+/\?"),
        parameter="s",
    ),
    # Provider: mySimon (mysimon.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("cb2cd314-9890-4fed-9643-5cbfaffbc698"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\?"),
        parameter="q",
    ),
    # Provider: National Center for Biotechnology Information (ncbi.nlm.nih.gov)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0c37f9b7-f038-46a5-a591-d23a725c4a31"),
        url_pattern=re_compile(r"^https?://[^/]+/.*term="),
        parameter="term",
    ),
    # Provider: News & Moods (newsandmoods.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("13569568-6af0-471f-8e97-035051699db7"),
        url_pattern=re_compile(r"^https?://[^/]+/news\/search\?"),
        parameter="sstring",
    ),
    # Provider: Newslookup (newslookup.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("d00f4edc-801d-4aee-99ca-289636ac7b7e"),
        url_pattern=re_compile(r"^https?://[^/]+/results\?"),
        parameter="q",
    ),
    # Provider: NexTag (nextag.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("89b8efa1-8a1e-4928-958b-8f7fad8efacc"),
        url_pattern=re_compile(r"^https?://[^/]+/shopping\/products\?"),
        parameter="search",
    ),
    # Provider: Podscope (podscope.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("54d95e98-12d6-4cd8-9ca7-8b9c36166ee6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="q",
    ),
    # Provider: Qmamu (qmamu.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("0b7660d4-8f9d-449f-b8da-569d1e1600fe"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: RecipeBridge (recipebridge.com)
    PathSegmentUrlQueryParser(
        provider_id=UUID("8fd6c11b-e87c-4b56-873d-eb90d1a13af1"),
        url_pattern=re_compile(r"^https?://[^/]+/r/[^/]+"),
        segment=2,
        remove_pattern=re_compile(r"-recipes$"),
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("8fd6c11b-e87c-4b56-873d-eb90d1a13af1"),
        url_pattern=re_compile(r"^https?://[^/]+/recipes\?"),
        parameter="q",
    ),
    # Provider: Songza (songza.fm)
    QueryParameterUrlQueryParser(
        provider_id=UUID("4d53223f-0df5-4a3a-9106-0f64ba6bf6bc"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="q",
    ),
    # Provider: Swisscows (swisscows.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("1da41fe2-3edd-408a-9459-4efadf32a80b"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(web|news|video|music)\?"),
        parameter="query",
    ),
    # Provider: DBLP (dblp.uni-trier.de)
    QueryParameterUrlQueryParser(
        provider_id=UUID("c012c0b5-c493-48e8-a309-5bccdf96260b"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="q",
    ),
    # Provider: TripAdvisor (tripadvisor.com)
    QueryParameterUrlQueryParser(
        provider_id=UUID("59dea5e0-eb0d-43d3-b1c1-70c22fbc25e1"),
        url_pattern=re_compile(r"^https?://[^/]+/Search\?"),
        parameter="q",
    ),
    QueryParameterUrlQueryParser(
        provider_id=UUID("59dea5e0-eb0d-43d3-b1c1-70c22fbc25e1"),
        url_pattern=re_compile(r"^https?://[^/]+/SearchForums\?"),
        parameter="q",
    ),
)
