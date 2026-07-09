"""Helpers for parsing input datetimes and rendering UTC responses."""
from datetime import datetime, timezone


def parse_input_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime into a naive UTC datetime for storage.

    Inputs that carry a UTC offset are normalized to UTC; naive inputs are
    treated as UTC as-is.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        # BUG FIX 1: Convert the datetime to the correct UTC timezone first, 
        # then strip tzinfo for storage, satisfying Section 4, Rule 1.
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso_utc(dt: datetime) -> str:
    """Render a stored (naive UTC) datetime with an explicit UTC designator."""
    # BUG FIX 2: Replace Python's default '+00:00' with the explicit UTC designator 'Z'
    # as strictly required by Section 4, Rule 1.
    res = dt.replace(tzinfo=timezone.utc).isoformat()
    if res.endswith("+00:00"):
        res = res[:-6] + "Z"
    return res
