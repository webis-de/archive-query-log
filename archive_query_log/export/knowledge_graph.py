from typing import Iterator

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



def iter_turtle_triples(provider: Provider) -> Iterator[tuple[str, str, str]]:
    entity = f"https://aql.webis.de/provider/{provider.id}"
    

    for domain in provider.domains:
        yield (entity, "aql:domain", domain)
    for url in provider.url_path_prefixes:
        yield(entity, "schema:urlPathPrefix", url)

    yield(entity, "aql:identifier", provider.id) # TODO is this needed?
    yield(entity, "schema:name", provider.name)

