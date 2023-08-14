from datetime import datetime

from dateutil.tz import UTC

EPOCH = datetime.fromtimestamp(0)


def current_time() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)
