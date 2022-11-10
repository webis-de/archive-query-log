from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import final, Optional
from urllib.parse import SplitResult, parse_qsl, unquote


class QueryParser(ABC):
    @abstractmethod
    def parse_query(self, url: SplitResult) -> Optional[str]:
        ...


@final
@dataclass(frozen=True)
class QueryParameter(QueryParser):
    key: str

    def parse_query(self, url: SplitResult) -> Optional[str]:
        for key, value in parse_qsl(url.query):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class FragmentParameter(QueryParser):
    key: str

    def parse_query(self, url: SplitResult) -> Optional[str]:
        for key, value in parse_qsl(url.fragment):
            if key == self.key:
                return value
        return None


@final
@dataclass(frozen=True)
class PathSuffix(QueryParser):
    prefix: str

    def parse_query(self, url: SplitResult) -> Optional[str]:
        if not url.path.startswith(self.prefix):
            return None
        return unquote(url.path.removeprefix(self.prefix))
