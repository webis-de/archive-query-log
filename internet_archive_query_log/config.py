from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    prefix: str
    query_parameter: str
