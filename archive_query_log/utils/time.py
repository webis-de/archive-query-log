from datetime import datetime, timezone, timedelta

EPOCH = datetime.fromtimestamp(0)

UTC = timezone.utc

CET = timezone(timedelta(hours=1))
"""
Central European Time (CET)
"""


def utc_now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)
