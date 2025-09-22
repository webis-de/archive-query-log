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
from archive_query_log.namespaces import NAMESPACE_URL_OFFSET_PARSER
from archive_query_log.orm import Serp, InnerParser
from archive_query_log.parsers.utils import clean_int
from archive_query_log.parsers.utils.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.utils.time import utc_now


class UrlOffsetParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    remove_pattern: Pattern | None = None
    space_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_URL_OFFSET_PARSER, self.model_dump_json())

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


class QueryParameterUrlOffsetParser(UrlOffsetParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        offset_string = parse_url_query_parameter(self.parameter, serp.capture.url)
        if offset_string is None:
            return None
        return clean_int(
            text=offset_string,
            remove_pattern=self.remove_pattern,
        )


class FragmentParameterUrlOffsetParser(UrlOffsetParser):
    parameter: str

    def parse(self, serp: Serp) -> int | None:
        offset_string = parse_url_fragment_parameter(self.parameter, serp.capture.url)
        if offset_string is None:
            return None
        return clean_int(
            text=offset_string,
            remove_pattern=self.remove_pattern,
        )


class PathSegmentUrlOffsetParser(UrlOffsetParser):
    segment: int

    def parse(self, serp: Serp) -> int | None:
        offset_string = parse_url_path_segment(self.segment, serp.capture.url)
        if offset_string is None:
            return None
        return clean_int(
            text=offset_string,
            remove_pattern=self.remove_pattern,
        )


def _parse_serp_url_offset_action(serp: Serp) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        serp.url_offset_parser is not None
        and serp.url_offset_parser.should_parse is not None
        and not serp.url_offset_parser.should_parse
    ):
        return

    for parser in URL_OFFSET_PARSERS:
        if not parser.is_applicable(serp):
            continue
        url_offset = parser.parse(serp)
        if url_offset is None:
            # Parsing was not successful.
            continue
        yield serp.update_action(
            url_offset=url_offset,
            url_offset_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        url_offset_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_offset(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(~Term(url_offset_parser__should_parse=False))
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
            desc="Parsing URL offset",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_url_offset_action(serp) for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")


# TODO: Add actual parsers.
URL_OFFSET_PARSERS: Sequence[UrlOffsetParser] = (
    # Provider: Google (google.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="start",
    ),
    # Provider: Google Scholar (scholar.google.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/scholar\?"),
        parameter="start",
    ),
    QueryParameterUrlOffsetParser(
        provider_id=UUID("f12d8077-5a7b-4a36-a28c-f7a3ad4f97ee"),
        url_pattern=re_compile(r"^https?://[^/]+/citations\?"),
        parameter="astart",
    ),
    # Provider: Baidu (baidu.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/s\?"),
        parameter="pn",
    ),
    QueryParameterUrlOffsetParser(
        provider_id=UUID("2cdfe387-b987-40f9-8a70-e50b378f71c1"),
        url_pattern=re_compile(r"^https?://[^/]+/f\?"),
        parameter="pn",
    ),
    # Provider: Yahoo! (yahoo.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("6c8f6e76-13e9-436b-8ea3-1645bce0032c"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="b",
    ),
    # Provider: Microsoft (microsoft.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("dae12f5e-3b1d-46ad-a8d8-1417b9c33128"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+-[a-z]+/search"),
        parameter="skip",
    ),
    # Provider: Microsoft Bing (bing.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("a0d3e9d1-6b95-46a4-b4d7-3f00de99ae7d"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="first",
    ),
    # Provider: Zoom (zoom.us)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("2e7be331-813d-46da-930b-5d2310fd5c81"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search"),
        parameter="first",
    ),
    # Provider: Naver (naver.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("273bf1e0-e2ec-4e3d-8843-51d8cb82abc1"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.naver\?"),
        parameter="start",
    ),
    # Provider: Indeed (indeed.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("8eb73577-58d7-4b8f-b5eb-0cca05b3c9fc"),
        url_pattern=re_compile(r"^https?://[^/]+/jobs\?"),
        parameter="start",
    ),
    # Provider: Booking.com (booking.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("c7c31f59-d709-4895-b406-42e5d0025e2a"),
        url_pattern=re_compile(r"^https?://[^/]+/searchresults"),
        parameter="offset",
    ),
    # Provider: Salesforce (salesforce.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("11c32f67-a615-4508-9b3a-45ca221f33b0"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="first",
    ),
    # Provider: Craigslist (craigslist.org)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("0161ce52-a862-492e-a6e7-08088554a892"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+"),
        parameter="s",
    ),
    # Provider: ResearchGate (researchgate.net)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("093ed74c-073a-47a2-b200-5b78386ca60d"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="offset",
    ),
    # Provider: wikiHow (wikihow.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("6ac3b5b2-5a16-41dd-99d6-c33e7a72f2fc"),
        url_pattern=re_compile(r"^https?://[^/]+/wikiHowTo\?"),
        parameter="start",
    ),
    # Provider: Wikimedia (wikisource.org)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("cbad7006-313a-4d36-8e2f-ecc1712213d9"),
        url_pattern=re_compile(r"^https?://[^/]+/w/index.php\?"),
        parameter="offset",
    ),
    # Provider: Blackboard (blackboard.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("dec84fa8-fa38-407c-9ada-043441a21786"),
        url_pattern=re_compile(r"^https?://[^/]+/site-search\?"),
        parameter="first",
    ),
    # Provider: Investopedia (investopedia.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("2ba78774-eb8f-4fe2-80d5-16379cb3fe30"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: Seznam (seznam.cz)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("22eba7be-a91c-4b21-80d3-0e837126f203"),
        url_pattern=re_compile(r"^https?://[^/]+/?((obrazky|videa|clanky)\/)?\?"),
        parameter="from",
    ),
    # Provider: Rediff.com (rediff.com)
    PathSegmentUrlOffsetParser(
        provider_id=UUID("203da776-b325-4ece-85ff-297ce1c75919"),
        url_pattern=re_compile(r"^https?://[^/]+/search/[^/]+/[0-9]+-[^/]+"),
        segment=3,
        remove_pattern=re_compile(r"-[^/]+$"),
    ),
    # Provider: goo (goo.ne.jp)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("183282c3-ff26-429b-ae25-f6dbfe90e94e"),
        url_pattern=re_compile(r"^https?://[^/]+/web\.jsp\?"),
        parameter="FR",
    ),
    QueryParameterUrlOffsetParser(
        provider_id=UUID("183282c3-ff26-429b-ae25-f6dbfe90e94e"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="FR",
    ),
    # Provider: Turkey e-government (turkiye.gov.tr)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("541bc6bc-661e-4207-bc18-42e44f50090f"),
        url_pattern=re_compile(r"^https?://[^/]+/arama\?"),
        parameter="sf",
    ),
    # Provider: Allrecipes (allrecipes.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("57c314b1-5625-449a-bb3c-b4fc4e3b1215"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: Smartsheet (smartsheet.com)
    FragmentParameterUrlOffsetParser(
        provider_id=UUID("f5dbd09d-f322-418a-bc3b-e8ddf6716eff"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="first",
    ),
    # Provider: 4shared (4shared.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("7dc71675-3245-432f-a6b9-cf5c4ba004e0"),
        url_pattern=re_compile(r"^https?://[^/]+/web/q"),
        parameter="offset",
    ),
    # Provider: Lifewire (lifewire.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("4ee41e2e-0ce0-4b05-b94a-86778d826d6a"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: Izvestia (iz.ru)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("f9132815-c4aa-4c54-b177-62e8971f5c93"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="from",
    ),
    # Provider: Idealo (idealo.de)
    PathSegmentUrlOffsetParser(
        provider_id=UUID("ab9b092a-9c68-4988-a82d-6360a85e59a0"),
        url_pattern=re_compile(
            r"^https?://[^/]+/preisvergleich/MainSearchProductCategory/100I16-[0-9]+\.html\?"
        ),
        segment=3,
        remove_pattern=re_compile(r"^100I16-|\.html$"),
    ),
    # Provider: The Balance (thebalancecareers.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("be1843b8-9091-46cc-bc00-af8b466889ee"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: BIGLOBE (biglobe.ne.jp)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("c1a407bd-97e4-416a-875b-45a278c85116"),
        url_pattern=re_compile(r"^https?://[^/]+/cgi-bin/search"),
        parameter="start",
    ),
    # Provider: ThoughtCo (thoughtco.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("bc6d9785-446e-4e4c-8875-fe9f9f5457b8"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="offset",
    ),
    # Provider: American Chemical Society (acs.org)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("1f30153c-ca85-4929-bce6-46e940c77df6"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="start",
    ),
    # Provider: @nifty (nifty.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("391725ae-2645-43da-843a-993bfe42c79c"),
        url_pattern=re_compile(r"^https?://[^/]+/websearch/search\?"),
        parameter="stpos",
    ),
    # Provider: Sky News عربية (skynewsarabia.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("15d49216-18c7-4378-975d-a798a287e804"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: Ubuntu (ubuntu.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("1461eb45-4e0d-44ce-801a-e985e382a735"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="start",
    ),
    # Provider: Navy Federal Credit Union (navyfederal.org)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("5ec6c1c1-a526-4ecf-85ba-bb59ab2cc5bc"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.html\?"),
        parameter="skipFrom",
    ),
    # Provider: opensubtitles.org (opensubtitles.org)
    PathSegmentUrlOffsetParser(
        provider_id=UUID("a42005e6-01cf-4bc0-aa7a-34a536c5dd27"),
        url_pattern=re_compile(
            r"^https?://[^/]+/[a-z]+/search2/sublanguageid-[a-z]+/moviename-[^/]+/offset-[0-9]+"
        ),
        segment=5,
        remove_pattern=re_compile(r"offset-"),
    ),
    # Provider: The Spruce (thespruce.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("95b0ef5d-524c-4363-a561-8c38bdf59358"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="offset",
    ),
    # Provider: Puma (puma.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("df40c25e-a088-42e9-aaf0-a2a08fc708dc"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[a-z]+/search\?"),
        parameter="offset",
    ),
    # Provider: NudeVista (nudevista.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("a05fa0d8-1031-41c1-bebb-48be2ff847dd"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="start",
    ),
    # Provider: CLUB-K (club-k.net)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("5bcb7623-a98e-416b-a8e6-ee748f170328"),
        url_pattern=re_compile(r"^https?://[^/]+/index"),
        parameter="limitstart",
    ),
    # Provider: Darty (darty.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("06a18e03-1bbf-4d19-b7b3-9d476d7ced18"),
        url_pattern=re_compile(r"^https?://[^/]+/nav/recherche\?"),
        parameter="o",
    ),
    # Provider: Levi's (levi.com.cn)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("1ced0855-8d1d-4505-bce8-d5f518b74a01"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="start",
    ),
    # Provider: يلا شوت الجديد (yalla-shoot-new.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("ee09cbfa-904f-43c7-9bd4-61145edf22ba"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="start",
    ),
    # Provider: H&R Block (hrblock.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("f1f53bd2-40b1-4920-b9e8-aa71c279b117"),
        url_pattern=re_compile(r"^https?://[^/]+/search"),
        parameter="firstResult",
    ),
    # Provider: BAUHAUS (bauhaus.info)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("1c492cdf-66f3-498d-9f99-b704fc24ee0f"),
        url_pattern=re_compile(r"^https?://[^/]+/suche/produkte\?"),
        parameter="shownProducts",
    ),
    # Provider: United States Senate (senate.gov)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("952fd42b-b2a4-46c9-ba81-99c872d8ab92"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/search"),
        parameter="start",
    ),
    # Provider: Santander (santander.co.uk)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("c5931062-d364-481a-a727-254cb1172ae4"),
        url_pattern=re_compile(r"^https?://[^/]+/s/search\.html\?"),
        parameter="start_rank",
    ),
    # Provider: Ping Identity (pingidentity.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("9c7b638e-e064-4ee1-a09b-b3ce82e92e99"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/search-results\.html"),
        parameter="first",
    ),
    # Provider: ROZEE (rozee.pk)
    PathSegmentUrlOffsetParser(
        provider_id=UUID("601b194f-83d0-445c-98dc-57c7ed9a1ae3"),
        url_pattern=re_compile(r"^https?://[^/]+/job/jsearch/q/[^/]+/fpn/[0-9]+"),
        segment=6,
    ),
    # Provider: VijestiBa (vijesti.ba)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("121e12a4-258c-43c7-bf8d-648b9d5deafb"),
        url_pattern=re_compile(r"^https?://[^/]+/pretraga\?"),
        parameter="od_",
    ),
    # Provider: 应届生 (yingjiesheng.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("95026b4e-687c-470f-9bed-3b885ac359b6"),
        url_pattern=re_compile(r"^https?://[^/]+/search\.php\?"),
        parameter="start",
    ),
    # Provider: InfoCert (infocert.it)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("e6a60332-e1ac-410c-a06e-741b316b654a"),
        url_pattern=re_compile(r"^https?://[^/]+/\?"),
        parameter="start",
    ),
    # Provider: Angola24Horas (angola24horas.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("ae174983-a297-44ef-94b3-ce34f78252f2"),
        url_pattern=re_compile(r"^https?://[^/]+/mais/[^/]+/pesquisar\?"),
        parameter="start",
    ),
    # Provider: BlackBerry (blackberry.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("5c6957ed-50a3-4cb2-8a36-8bce9b757b08"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/[a-z]+/search#q"),
        parameter="first",
    ),
    # Provider: SEB (seb.se)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("66cec6f9-fe3c-4d0d-ac1e-59e1b96e02d3"),
        url_pattern=re_compile(r"^https?://[^/]+/systemsidor/sok\?"),
        parameter="o",
    ),
    # Provider: Shopzilla (shopzilla.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("75c28e9c-da09-47e2-abaf-9e13ccf87a29"),
        url_pattern=re_compile(r"^https?://[^/]+/.*/products/\?"),
        parameter="start",
    ),
    # Provider: PriceGrabber (pricegrabber.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("fb204525-e2a8-4d8e-8c03-8e736b497c37"),
        url_pattern=re_compile(r"^https?://[^/]+/[^/]+/products/"),
        parameter="start",
    ),
    # Provider: Blinkx (blinkx.com)
    PathSegmentUrlOffsetParser(
        provider_id=UUID("af537770-cf02-4d98-a402-467cfd69a0c6"),
        url_pattern=re_compile(r"^https?://[^/]+/videos/[^/]+/[0-9]+"),
        segment=3,
    ),
    # Provider: MetaGer (metager.de)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("0f805bab-0cf3-4ad5-bf05-311dfe5056b6"),
        url_pattern=re_compile(r"^https?://[^/]+/meta/meta\.ger3\?"),
        parameter="next",
    ),
    # Provider: Gigablast (gigablast.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("8fbcbf4f-e571-4c03-abbd-77a857344105"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="s",
    ),
    # Provider: Mojeek (mojeek.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("74ee3c4a-1cb5-4d0f-928e-f42f8c0200a4"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        parameter="s",
    ),
    # Provider: News & Moods (newsandmoods.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("13569568-6af0-471f-8e97-035051699db7"),
        url_pattern=re_compile(r"^https?://[^/]+/news\/search\?"),
        parameter="start",
    ),
    # Provider: Swisscows (swisscows.com)
    QueryParameterUrlOffsetParser(
        provider_id=UUID("1da41fe2-3edd-408a-9459-4efadf32a80b"),
        url_pattern=re_compile(r"^https?://[^/]+/[a-z]+/(web|news|video|music)\?"),
        parameter="offset",
    ),
)
