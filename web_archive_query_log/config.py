from typing import Mapping

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.model import Service
from web_archive_query_log.services import read_services

# Load all services that have parsers and create the services for them.
_SERVICES_PATH = DATA_DIRECTORY_PATH / "services.yaml"
SERVICES: Mapping[str, Service] = read_services(_SERVICES_PATH)
