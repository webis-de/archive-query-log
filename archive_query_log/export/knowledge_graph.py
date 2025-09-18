from typing import Iterator
from orm import Provider, Archive, Capture

# class Provider(BaseDocument):
#     name: str = Text()
#     description: str = Text()
#     exclusion_reason: str = Text()
#     notes: str = Text()
#     domains: list[str] = Keyword()
#     url_path_prefixes: list[str] = Keyword()
#     priority: float | None = RankFeature(positive_score_impact=True)
#     should_build_sources: bool = Boolean()
#     last_built_sources: datetime = Date(
#         default_timezone="UTC",
#         format="strict_date_time_no_millis",
#     )

#     class Index:
#         settings = {
#             "number_of_shards": 1,
#             "number_of_replicas": 2,
#         }

# class Archive(BaseDocument):
#     name: str = Text()
#     description: str = Text()
#     cdx_api_url: str = Keyword()
#     memento_api_url: str = Keyword()
#     priority: float | None = RankFeature(positive_score_impact=True)
#     should_build_sources: bool = Boolean()
#     last_built_sources: datetime = Date(
#         default_timezone="UTC",
#         format="strict_date_time_no_millis",
#     )

#     class Index:
#         settings = {
#             "number_of_shards": 1,
#             "number_of_replicas": 2,
#         }

# class Capture(BaseDocument):
#     archive: InnerArchive = Object(InnerArchive)
#     provider: InnerProvider = Object(InnerProvider)
#     url: str = Keyword()
#     url_key: str = Keyword()
#     timestamp: datetime = Date(
#         default_timezone="UTC",
#         format="strict_date_time_no_millis",
#     )
#     status_code: int = Integer()
#     digest: str = Keyword()
#     mimetype: str | None = Keyword()
#     filename: str | None = Keyword()
#     offset: int | None = Integer()
#     length: int | None = Integer()
#     access: str | None = Keyword()
#     redirect_url: str | None = Keyword()
#     flags: list[str] | None = Keyword()
#     collection: str | None = Keyword()
#     source: str | None = Keyword()
#     source_collection: str | None = Keyword()
#     url_query_parser: InnerParser | None = Object(InnerParser)

#     class Index:
#         settings = {
#             "number_of_shards": 40,
#             "number_of_replicas": 2,
#         }

# class Serp(BaseDocument):
#     archive: InnerArchive = Object(InnerArchive)
#     provider: InnerProvider = Object(InnerProvider)
#     capture: InnerCapture = Object(InnerCapture)
#     url_query: str = Text()
#     url_query_parser: InnerParser | None = Object(InnerParser)
#     url_page: int | None = Integer()
#     url_page_parser: InnerParser | None = Object(InnerParser)
#     url_offset: int | None = Integer()
#     url_offset_parser: InnerParser | None = Object(InnerParser)
#     # url_language: str | None = Keyword()
#     # url_language_parser: InnerParser | None = Object(InnerParser)
#     warc_location: WarcLocation | None = Object(WarcLocation)
#     warc_downloader: InnerDownloader | None = Object(InnerDownloader)
#     warc_query: str | None = Text()
#     warc_query_parser: InnerParser | None = Object(InnerParser)
#     warc_snippets: list[SnippetId] | None = Nested(SnippetId)
#     warc_snippets_parser: InnerParser | None = Object(InnerParser)
#     warc_direct_answers: list[DirectAnswerId] | None = Nested(DirectAnswerId)
#     warc_direct_answers_parser: InnerParser | None = Object(InnerParser)

#     # rendered_warc_location: WarcLocation | None = Object(WarcLocation)
#     # rendered_warc_downloader: InnerDownloader | None = (
#     #     Object(InnerDownloader))

#     class Index:
#         settings = {
#             "number_of_shards": 40,
#             "number_of_replicas": 2,
#         }





def iter_turtle_triples(provider: Provider) -> Iterator[tuple[str, str, str]]:
    entity = f"https://aql.webis.de/provider/{provider.id}"
    
    yield(entity, "schema:identifier", provider.id)
    yield(entity, "schema:name", provider.name)

    for domain in provider.domains:
        yield (entity, "aql:domain", domain)
    for url in provider.url_path_prefixes:
        yield(entity, "schema:urlPathPrefix", url)
    #Missing aqlWikidataUrl -> to be exported with another method


def iter_turtle_triples(archive: Archive) -> Iterator[tuple[str, str, str]]:
    entity = f"https://aql.webis.de/archive/{archive.id}"
    
    yield(entity, "schema:identifier", archive.id)
    yield(entity, "schema:name", archive.name)
    yield(entity, "aql:mementoAPIBaseURL", archive.memento_api_url)
    yield(entity, "aql:cdxAPIBaseURL", archive.cdx_api_url)
    #Missing aqlWikidataUrl -> to be exported with another method
    
def iter_turtle_triples(capture: Capture) -> Iterator[tuple[str, str, str]]:
    entity = f"https://aql.webis.de/capture/{capture.id}"
    
    yield(entity, "schema:dateCreated", capture.timestamp.isoformat())
    yield(entity, "schema:url", capture.url)
    yield(entity, "http:statusCodeNumber", str(capture.status_code))
    yield(entity, "aql:digest", capture.digest)
    yield(entity, "schema:encodingFormat", capture.mimetype)
    if hasattr(capture, "archive") and hasattr(capture.archive, "memento_api_url"):
        memento_viewer_url = f"{capture.archive.memento_api_url}/{capture.timestamp.strftime('%Y%m%d%H%M%S')}/{capture.url}" # this links to the archive url where capture is archived
        yield(entity, "aql:mementoAPIViewerURL", memento_viewer_url)
        
        memento_raw_url = f"{capture.archive.memento_api_url}/{capture.timestamp.strftime('%Y%m%d%H%M%S')}id_/{capture.url}" # this links to the raw content of the capture (without rewritten links by the archive)
        yield(entity, "aql:mementoAPIRawURL", memento_raw_url)
    #TODO insert internet archive metadata/collection later
    yield(entity, "schema:archivedAt", f"https://aql.webis.de/archive/{capture.archive.id}")

def iter_turtle_triples(serp: SERP) -> Iterator[tuple[str, str, str]]:
    entity = f"https://aql.webis.de/serp/{serp.id}"
    
    yield(entity, "schema:identifier", serp.id)
    # yield(entity, "aql:trecTaskURLQuery", ) TODO what is the trec task? is this just hypothetical?
    yield(entity, "schema:publisher", f"https://aql.webis.de/provider/{serp.provider.id}")
    yield(entity, "schema:hasPart", ) #TODO result block. -> new naming in new branch?