"""Shared response serialization for bookings."""
from .models import Booking
from .timeutils import iso_utc


def _ensure_z_designator(dt_str: str) -> str:
    """Helper to ensure the datetime string ends exactly with 'Z' as required by 
    Section 4, Rule 1 ('explicit UTC designator'). Replaces +00:00 with Z if present."""
    if not dt_str:
        return dt_str
    if dt_str.endswith("+00:00"):
        return dt_str[:-6] + "Z"
    if not dt_str.endswith("Z"):
        return dt_str + "Z"
    return dt_str


def serialize_booking(booking: Booking) -> dict:
    # BUG FIX: Wrapped the iso_utc output with _ensure_z_designator to absolutely 
    # guarantee the response contract matches Section 4, Rule 1 ("explicit UTC designator").
    return {
        "id": booking.id,
        "reference_code": booking.reference_code,
        "room_id": booking.room_id,
        "user_id": booking.user_id,
        "start_time": _ensure_z_designator(iso_utc(booking.start_time)),
        "end_time": _ensure_z_designator(iso_utc(booking.end_time)),
        "status": booking.status,
        "price_cents": booking.price_cents,
        "created_at": _ensure_z_designator(iso_utc(booking.created_at)),
    }
