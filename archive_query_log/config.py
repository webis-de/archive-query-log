from typing import Mapping

from archive_query_log import DATA_DIRECTORY_PATH
from archive_query_log.model import Service
from archive_query_log.services import read_services

# Load all services that have parsers and create the services for them.
SERVICES_PATH = DATA_DIRECTORY_PATH / "selected-services.yaml"
SERVICES: Mapping[str, Service] = read_services(SERVICES_PATH)
