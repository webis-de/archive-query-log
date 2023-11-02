from typing import Iterator, TypeVar, Iterable
from warnings import warn

from elasticsearch import NotFoundError
from elasticsearch_dsl import Document

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
        else:
            raise e
