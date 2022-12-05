from pathlib import Path
from typing import Mapping

from yaml import safe_load

from web_archive_query_log.model import Service


def read_services(path: Path) -> Mapping[str, Service]:
    with path.open("r") as file:
        services_dict = safe_load(file)
        return {
            service.name: service
            for service in Service.schema().load(services_dict, many=True)
        }
