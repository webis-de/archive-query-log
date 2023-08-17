from datetime import datetime

from dateutil.tz import UTC

EPOCH = datetime.fromtimestamp(0)


def utc_now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)
