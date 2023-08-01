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
    echo(f"Set index mapping for {CONFIG.es_index_archives.name}.")
    CONFIG.es.indices.put_mapping(
        index=CONFIG.es_index_archives.name,
        body=CONFIG.es_index_archives.mapping,
    )