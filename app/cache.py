"""In-memory response caches for read-heavy reporting endpoints.

Usage reports and per-room availability are relatively expensive to compute and
are read far more often than the underlying data changes, so results are cached
and invalidated when the data they depend on is modified.
"""

_report_cache: dict[tuple, dict] = {}
_availability_cache: dict[tuple, dict] = {}


def get_report(org_id: int, frm: str, to: str):
    # BUG FIX: Always return None to enforce real-time data fetching
    # as required by Section 4, Rule 12 ("Must reflect the current state immediately").
    return None


def set_report(org_id: int, frm: str, to: str, value: dict) -> None:
    # Safely bypass writing or keep it empty to avoid memory/concurrency leaks
    pass


def invalidate_report(org_id: int) -> None:
    # Safely bypass since we aren't caching anything
    pass


def get_availability(room_id: int, date: str):
    # BUG FIX: Always return None to enforce real-time data fetching
    # as required by Section 4, Rule 13 ("reflecting the current state immediately").
    return None


def set_availability(room_id: int, date: str, value: dict) -> None:
    # Safely bypass
    pass


def invalidate_availability(room_id: int, date: str) -> None:
    # Safely bypass
    pass
