from typing import Iterator
from orm import Provider, Archive, Capture, SERP


# class Serp(UuidBaseDocument):
#     last_modified: DefaultDate
#     archive: InnerArchive
#     provider: InnerProvider
#     capture: InnerCapture
#     url_query: Text
#     url_query_parser: InnerParser | None = None
#     url_page: Integer | None = None
#     url_page_parser: InnerParser | None = None
#     url_offset: Integer | None = None
#     url_offset_parser: InnerParser | None = None
#     # url_language: Keyword | None = None
#     # url_language_parser: InnerParser | None = None
#     warc_location: WarcLocation | None = None
#     warc_downloader: InnerDownloader | None = None
#     warc_query: Text | None = None
#     warc_query_parser: InnerParser | None = None
#     warc_web_search_result_blocks: Sequence[WebSearchResultBlockId] | None = None
#     warc_web_search_result_blocks_parser: InnerParser | None = None
#     warc_special_contents_result_blocks: (
#         Sequence[SpecialContentsResultBlockId] | None
#     ) = None
#     warc_special_contents_result_blocks_parser: InnerParser | None = None

#     class Index:
#         settings = {
#             "number_of_shards": 40,
#             "number_of_replicas": 2,
#         }



# class WebSearchResultBlock(UuidBaseDocument):
#     last_modified: DefaultDate
#     archive: InnerArchive
#     provider: InnerProvider
#     serp_capture: InnerCapture
#     serp: InnerSerp
#     content: Text
#     rank: Integer
#     url: HttpUrl | None = None
#     title: Text | None = None
#     text: Text | None = None
#     parser: InnerParser | None = None
#     should_fetch_captures: bool = True
#     last_fetched_captures: Date | None = None
#     capture_before_serp: InnerCapture | None = None
#     warc_location_before_serp: WarcLocation | None = None
#     warc_downloader_before_serp: InnerDownloader | None = None
#     capture_after_serp: InnerCapture | None = None
#     warc_location_after_serp: WarcLocation | None = None
#     warc_downloader_after_serp: InnerDownloader | None = None

#     class Index:
#         settings = {
#             "number_of_shards": 20,
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
    
    for websearchresultblock in serp.warc_web_search_result_blocks:
        yield(entity, "schema:hasPart", f"https://aql.webis.de/websearchresultblock/{websearchresultblock.id}") # iterate over all websearchresultblocks of a serp
        
    for specialcontentsresultblock in serp.warc_special_contents_result_blocks:
        yield(entity, "schema:hasPart", f"https://aql.webis.de/specialcontentsresultblock/{specialcontentsresultblock.id}") # iterate over all specialcontentsresultblocks of a serp
        
    #TODO how to model superclass of resultblock? we dont have a python class for it
        
        # Model result block as superclass in python first, then in knowledgegraph