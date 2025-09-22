from typing import Annotated, Any

from cyclopts import Parameter
from validators import domain as validate_domain


def _domain_validator(type_, value: Any) -> None:
    if value is not None:
        valid = validate_domain(value)
        if not valid:
            if isinstance(valid, bool):
                raise ValueError(f"Not a valid domain: {value}")
            else:
                raise valid


Domain = Annotated[str, Parameter(validator=_domain_validator)]
