from click import echo

from archive_query_log.new.config import EsIndex, CONFIG


def create_index(es_index: EsIndex) -> None:
    if not CONFIG.es.indices.exists(index=es_index.name):
        echo(f"Create index {es_index.name}.")
        CONFIG.es.indices.create(
            index=es_index.name,
            body={
                "settings": es_index.settings,
            },
        )
    echo(f"Set index mapping for {es_index.name}.")
    CONFIG.es.indices.put_mapping(
        index=es_index.name,
        body=es_index.mapping,
    )