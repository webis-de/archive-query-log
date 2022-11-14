from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested


@dataclass(frozen=True, slots=True)
class Query(DataClassJsonMixin):
    """
    Archived snapshot of a search engine query and the SERP it points to.
    """
    text: str
    url: str
    timestamp: int

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

    @property
    def archive_url(self) -> str:
        timestamp = self.datetime.strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}/{self.url}"

    @property
    def raw_archive_url(self) -> str:
        timestamp = self.datetime.strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}id_/{self.url}"


@dataclass(frozen=True, slots=True)
class Result(DataClassJsonMixin):
    """
    Single retrieved result from a query's archived SERP.
    """
    url: str
    title: str
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class Serp(Query, DataClassJsonMixin):
    """
    Search engine result page (SERP) corresponding to a query.
    """
    results: Sequence[Result] = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(Result.schema()))
        )
    )
