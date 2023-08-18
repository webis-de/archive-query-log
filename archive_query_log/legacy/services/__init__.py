from pathlib import Path
from typing import Mapping

from marshmallow import ValidationError
from yaml import safe_load

from archive_query_log.legacy.model import Service


def read_services(
        path: Path, ignore_parsing_errors=True
) -> Mapping[str, Service]:
    with path.open("r") as file:
        services_dict = safe_load(file)
        services = []

        for service_dict in services_dict:
            try:
                service = Service.schema(unknown="exclude").load(service_dict)
                services += [(service.name, service)]
            except ValidationError as e:
                if not ignore_parsing_errors:
                    raise ValueError(
                        f"Could not parse service {service_dict}") from e
        if not ignore_parsing_errors:
            service_names = set()
            for name, service in services:
                if name in service_names:
                    raise ValueError(f"Duplicate service name {name}")
                service_names.add(name)
        return {
            name: service
            for name, service in services
        }
