from typing import Annotated

from cyclopts import Parameter
from validators import domain as validate_domain


def _validate_domain(domain: str) -> str:
    valid = validate_domain(domain)
    if not valid:
        if isinstance(valid, bool):
            raise ValueError(f"Not a valid domain: {domain}")
        else:
            raise valid
    return domain


Domain = Annotated[str, Parameter(validator=_validate_domain)]
