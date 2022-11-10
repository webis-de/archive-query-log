from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    prefixes: set[str]
    query_parameter: str
