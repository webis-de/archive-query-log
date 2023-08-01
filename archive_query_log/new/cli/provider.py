from datetime import datetime
from uuid import uuid5, NAMESPACE_URL

from click import group, argument, option, echo

from archive_query_log.new.cli.validation import validate_domain
from archive_query_log.new.config import CONFIG
from archive_query_log.new.namespaces import NAMESPACE_ARCHIVE
from archive_query_log.new.utils.es import create_index


@group()
def archive():
    pass


@archive.command()
@argument("domain", type=str, callback=validate_domain)
@argument("cdx_api_url", type=str)
@argument("memento_api_url", type=str)
@option("--description", type=str)
def add(
        domain: str,
        cdx_api_url: str,
        memento_api_url: str,
        description: str | None,
):
    create_index(CONFIG.es_index_archives)
    archive_id = str(uuid5(NAMESPACE_ARCHIVE, domain))
    document = {
        "id": archive_id,
        "domain": domain,
        "description": description,
        "cdx_api_url": cdx_api_url,
        "memento_api_url": memento_api_url,
        "last_modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    echo(f"Add archive {archive_id}.")
    CONFIG.es.index(
        index=CONFIG.es_index_archives.name,
        id=archive_id,
        document=document,
    )
    echo(f"Refresh index {CONFIG.es_index_archives.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_archives.name)
    echo("Done.")
