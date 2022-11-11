from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Query:
    text: str
    url: str
    timestamp: datetime

    @property
    def archive_url(self) -> str:
        timestamp = self.timestamp.strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}/{self.url}"