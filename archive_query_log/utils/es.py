from typing import Iterator, TypeVar, Iterable, Any
from warnings import warn

from elasticsearch import NotFoundError
from elasticsearch_dsl import Document, InnerDoc
from elasticsearch_dsl.utils import META_FIELDS

DocumentType = TypeVar("DocumentType", bound=Document)


def safe_iter_scan(it: Iterable[DocumentType]) -> Iterator[DocumentType]:
    try:
        for doc in it:
            yield doc
    except NotFoundError as e:
        if (e.info is not None and isinstance(e.info, dict) and
                "error" in e.info and
                isinstance(e.info["error"], dict) and
                "root_cause" in e.info["error"] and
                isinstance(e.info["error"]["root_cause"], list) and
                len(e.info["error"]["root_cause"]) > 0 and
                isinstance(e.info["error"]["root_cause"][0], dict) and
                "resource.id" in e.info["error"]["root_cause"][0] and
                e.info["error"]["root_cause"][0]["resource.id"] ==
                "search_phase_execution_exception"):
            warn(RuntimeWarning("Scan expired. Stopping iteration."))
            raise StopIteration() from e
        else:
            raise e


def _to_dict_if_needed(value: Any) -> Any:
    if isinstance(value, InnerDoc):
        return value.to_dict()
    return value


def update_action(
        document: Document,
        retry_on_conflict: int | None = 3,
        **fields,
) -> dict:
    action = {
        f"_{key}": document.meta[key]
        for key in META_FIELDS
        if key not in ("score")
        if key in document.meta and document.meta[key] is not None
    }
    action["_op_type"] = "update"
    # Create a partial document by instantiating a new object of the
    # document type and ignoring the meta fields (e.g., the document ID).
    action["doc"] = type(document)(**fields).to_dict(
        include_meta=False,
        skip_empty=True,
    )
    if retry_on_conflict is not None:
        action["_retry_on_conflict"] = retry_on_conflict
    return action
