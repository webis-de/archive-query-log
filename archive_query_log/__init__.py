from logging import getLogger
from pathlib import Path

from importlib_metadata import version

__version__ = version("archive_query_log")

PROJECT_DIRECTORY_PATH = Path(__file__).parent.parent
DATA_DIRECTORY_PATH = PROJECT_DIRECTORY_PATH / "data"

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

LOGGER = getLogger(__name__)
