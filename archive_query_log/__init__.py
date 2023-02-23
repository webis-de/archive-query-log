from logging import getLogger
from pathlib import Path

__version__ = "0.1.0"

PROJECT_DIRECTORY_PATH = Path(__file__).parent.parent
DATA_DIRECTORY_PATH = PROJECT_DIRECTORY_PATH / "data"
# DATA_DIRECTORY_PATH = Path("/mnt/ceph/storage/TODO")

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

LOGGER = getLogger(__name__)
