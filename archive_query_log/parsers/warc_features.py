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
from lxml.etree import _Element, tostring, XPath
from pydantic import AnyHttpUrl, BaseModel
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import (
    NAMESPACE_WARC_FEATURES_PARSER,
    NAMESPACE_FEATURE,
)
from archive_query_log.orm import (
    Serp,
    InnerParser,
    Feature,
    InnerSerp,
    FeatureId,
)
from archive_query_log.parsers.utils import content_digest
from archive_query_log.parsers.utils.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now
from archive_query_log.utils.warc import WarcStore


class FeatureData(BaseModel):
    id: UUID
    rank: int
    content: str
    url: AnyHttpUrl | None = None
    title: str | None = None
    text: str | None = None


class WarcFeaturesParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None

    @cached_property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_WARC_FEATURES_PARSER, self.model_dump_json())

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
    def parse(self, serp: Serp, warc_store: WarcStore) -> list[FeatureData] | None: ...


class XpathWarcFeaturesParser(WarcFeaturesParser):
    xpath: str
    url_xpath: str | None = None
    title_xpath: str | None = None
    text_xpath: str | None = None

    @cached_property
    def _xpath(self) -> XPath:
        return XPath(
            path=self.xpath,
            smart_strings=False,
        )

    @cached_property
    def _url_xpath(self) -> XPath | None:
        if self.url_xpath is None:
            return None
        return XPath(
            path=self.url_xpath,
            smart_strings=False,
        )

    @cached_property
    def _title_xpath(self) -> XPath | None:
        if self.title_xpath is None:
            return None
        return XPath(
            path=self.title_xpath,
            smart_strings=False,
        )

    @cached_property
    def _text_xpath(self) -> XPath | None:
        if self.text_xpath is None:
            return None
        return XPath(
            path=self.text_xpath,
            smart_strings=False,
        )

    def parse(self, serp: Serp, warc_store: WarcStore) -> list[FeatureData] | None:
        if serp.warc_location is None:
            return None

        with warc_store.read(serp.warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        elements = safe_xpath(tree, self._xpath, _Element)
        if len(elements) == 0:
            return None

        features = []
        element: _Element
        for i, element in enumerate(elements):
            url: str | None = None
            if self._url_xpath is not None:
                urls = safe_xpath(element, self._url_xpath, str)
                if len(urls) > 0:
                    url = urls[0].strip()
                    url = urljoin(serp.capture.url.encoded_string(), url)
            title: str | None = None
            if self._title_xpath is not None:
                titles = safe_xpath(element, self._title_xpath, str)
                if len(titles) > 0:
                    title = titles[0].strip()
            text: str | None = None
            if self._text_xpath is not None:
                texts = safe_xpath(element, self._text_xpath, str)
                if len(texts) > 0:
                    text = texts[0].strip()

            content: str = tostring(
                element,
                encoding=str,
                method="xml",
                pretty_print=False,
                with_tail=True,
            )
            feature_id_components = (
                str(serp.id),
                str(self.id),
                content_digest(content),
                str(i),
            )
            feature_id = uuid5(
                NAMESPACE_FEATURE,
                ":".join(feature_id_components),
            )
            features.append(
                FeatureData(
                    id=feature_id,
                    rank=i,
                    content=content,
                    url=AnyHttpUrl(url) if url is not None else None,
                    title=title,
                    text=text,
                )
            )
        return features


def parse_serp_warc_features_action(
    serp: Serp,
    warc_store: WarcStore,
    index_features: str,
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
        serp.warc_features_parser is not None
        and serp.warc_features_parser.should_parse is not None
        and not serp.warc_features_parser.should_parse
    ):
        return

    for parser in WARC_FEATURES_PARSERS:
        if not parser.is_applicable(serp):
            continue
        warc_features = parser.parse(serp, warc_store)
        if warc_features is None:
            # Parsing was not successful.
            continue
        for feature in warc_features:
            feature = Feature(
                index=index_features,
                id=feature.id,
                last_modified=utc_now(),
                archive=serp.archive,
                provider=serp.provider,
                serp_capture=serp.capture,
                serp=InnerSerp(
                    id=serp.id,
                ),
                rank=feature.rank,
                content=feature.content,
                url=feature.url,
                title=feature.title,
                text=feature.text,
                parser=InnerParser(
                    id=parser.id,
                    should_parse=False,
                    last_parsed=utc_now(),
                ),
            )
            yield feature.create_action()
        yield serp.update_action(
            warc_features=[
                FeatureId(
                    id=feature.id,
                    rank=feature.rank,
                )
                for feature in warc_features
            ],
            warc_features_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_features_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_features(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(warc_features_parser__should_parse=False)
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
            desc="Parsing WARC SERP features",
            unit="SERP",
        )
        actions = chain.from_iterable(
            parse_serp_warc_features_action(
                serp,
                config.s3.warc_store,
                config.es.index_features,
            )
            for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")


WARC_FEATURES_PARSERS: Sequence[WarcFeaturesParser] = (
    # Provider: Google (google.com)
    XpathWarcFeaturesParser(
        provider_id=UUID("f205fc44-d918-4b79-9a7f-c1373a6ff9f2"),
        url_pattern=re_compile(r"^https?://[^/]+/search\?"),
        xpath=".//*[contains(concat(' ',normalize-space(@class),' '),' kp-wholepage ')] | .//*[contains(concat(' ',normalize-space(@class),' '),' XqFnDf ')] | .//*[contains(concat(' ',normalize-space(@class),' '),' WC0BKe ')]",
        url_xpath=".//*[contains(concat(' ',normalize-space(@class),' '),' ruhjFe ')]/@href | .//*[contains(concat(' ',normalize-space(@class),' '),' setTDc ')]/div[(count(preceding-sibling::*)+1) = 1]/div[(count(preceding-sibling::*)+1) = 1]/div[(count(preceding-sibling::*)+1) = 1]/div[(count(preceding-sibling::*)+1) = 1]/span[(count(preceding-sibling::*)+1) = 1]/a[(count(preceding-sibling::*)+1) = 1]/@href",
        text_xpath=".//*[contains(concat(' ',normalize-space(@class),' '),' kno-rdesc ')]//text() | .//*[contains(concat(' ',normalize-space(@class),' '),' Z0LcW ')]//text() | .//*[contains(concat(' ',normalize-space(@class),' '),' V3FYCf ')]/div[(count(preceding-sibling::*)+1) = 1]/div[(count(preceding-sibling::*)+1) = 1]/span[(count(preceding-sibling::*)+1) = 1]/span[(count(preceding-sibling::*)+1) = 1]//text()",
    ),
)
