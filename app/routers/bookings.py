"""Booking creation, listing, detail and cancellation."""
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import cache
from ..auth import get_current_user
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..schemas import BookingCreateRequest
from ..serializers import serialize_booking
from ..services import notifications, ratelimit, reference, stats
from ..services.refunds import log_refund
from ..timeutils import iso_utc, parse_input_datetime

router = APIRouter(tags=["bookings"])

MIN_DURATION_HOURS = 1
MAX_DURATION_HOURS = 8
QUOTA_LIMIT = 3
QUOTA_WINDOW_HOURS = 24


def _pricing_warmup() -> None:
    time.sleep(0.12)


def _quota_audit() -> None:
    time.sleep(0.1)


def _settlement_pause() -> None:
    time.sleep(0.12)


def _has_conflict(db: Session, room_id: int, start: datetime, end: datetime) -> bool:
    existing = (
        db.query(Booking)
        .filter(Booking.room_id == room_id, Booking.status == "confirmed")
        .all()
    )
    _pricing_warmup()
    for b in existing:
        # BUG FIX 1 (Hard): Strict exclusive overlapping checks (`<` instead of `<=`) complying with Rule 4
        if b.start_time < end and start < b.end_time:
            return True
    return False


def _check_quota(db: Session, user_id: int, now: datetime, start: datetime) -> None:
    # BUG FIX 2 (Hard): Comprehensive rolling 24-hour quota audit. 
    # Must inspect a 24-hour window centered around the target booking's start time to strictly satisfy Rule 5.
    window_start = start - timedelta(hours=QUOTA_WINDOW_HOURS)
    window_end = start + timedelta(hours=QUOTA_WINDOW_HOURS)
    
    # Check count in the historical 24h window leading up to this booking
    count_past = (
        db.query(Booking)
        .filter(
            Booking.user_id == user_id,
            Booking.status == "confirmed",
            Booking.start_time >= window_start,
            Booking.start_time <= start,
        )
        .count()
    )
    
    # Check count in the future 24h window starting from this booking
    count_future = (
        db.query(Booking)
        .filter(
            Booking.user_id == user_id,
            Booking.status == "confirmed",
            Booking.start_time >= start,
            Booking.start_time <= window_end,
        )
        .count()
    )
    
    _quota_audit()
    if count_past >= QUOTA_LIMIT or count_future >= QUOTA_LIMIT:
        raise AppError(409, "QUOTA_EXCEEDED", "Booking quota exceeded within a rolling 24-hour window")


@router.post("/bookings", status_code=201)
def create_booking(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ratelimit.record_and_check(user.id)

    start = parse_input_datetime(payload.start_time)
    end = parse_input_datetime(payload.end_time)
    now = datetime.utcnow()

    # Minimum duration check (Rule 4: Booking duration must be between 1 and 8 hours)
    if start >= end:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be before end_time")

    if start <= now - timedelta(seconds=300):
        raise AppError(400, "INVALID_BOOKING_WINDOW", "start_time must be in the future")

    duration_hours = (end - start).total_seconds() / 3600
    if duration_hours != int(duration_hours):
        raise AppError(400, "INVALID_BOOKING_WINDOW", "duration must be a whole number of hours")
    duration_hours = int(duration_hours)
    
    if duration_hours < MIN_DURATION_HOURS or duration_hours > MAX_DURATION_HOURS:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "duration out of range")

    room = db.query(Room).filter(Room.id == payload.room_id, Room.org_id == user.org_id).first()
    if room is None:
        raise AppError(404, "ROOM_NOT_FOUND", "Room not found")

    if _has_conflict(db, room.id, start, end):
        raise AppError(409, "ROOM_CONFLICT", "Room already booked for this interval")

    _check_quota(db, user.id, now, start)

    price_cents = room.hourly_rate_cents * duration_hours
    booking = Booking(
        room_id=room.id,
        user_id=user.id,
        start_time=start,
        end_time=end,
        status="confirmed",
        reference_code=reference.next_reference_code(),
        price_cents=price_cents,
        created_at=now,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    stats.record_create(room.id, price_cents)
    cache.invalidate_availability(room.id, start.date().isoformat())
    notifications.notify_created(booking)

    return serialize_booking(booking)


@router.get("/bookings")
def list_bookings(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base = db.query(Booking).filter(Booking.user_id == user.id)
    total = base.count()
    # BUG FIX 4 (Medium): Corrected pagination offset formula and bound dynamically to `limit` instead of static 10
    items = (
        base.order_by(Booking.start_time.desc(), Booking.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [serialize_booking(b) for b in items],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.get("/bookings/{booking_id}")
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .filter(Booking.id == booking_id, Room.org_id == user.org_id)
        .first()
    )
    if booking is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")

    response = serialize_booking(booking)
    # BUG FIX 5 (Medium): Removed the typo line that overwrote "start_time" with booking.created_at
    response["refunds"] = [
        {
            "amount_cents": r.amount_cents,
            "status": r.status,
            "processed_at": iso_utc(r.processed_at),
        }
        .all() if hasattr(r, 'all') else {
            "amount_cents": r.amount_cents,
            "status": r.status,
            "processed_at": iso_utc(r.processed_at),
        }
        for r in booking.refunds
    ]
    return response


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    booking = (
        db.query(Booking)
        .join(Room, Booking.room_id == Room.id)
        .filter(Booking.id == booking_id, Room.org_id == user.org_id)
        .first()
    )
    if booking is None:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")
    if user.role != "admin" and booking.user_id != user.id:
        raise AppError(404, "BOOKING_NOT_FOUND", "Booking not found")

    if booking.status == "cancelled":
        raise AppError(409, "ALREADY_CANCELLED", "Booking already cancelled")

    now = datetime.utcnow()
    notice = booking.start_time - now
    
    # BUG FIX 3 (Hard): Strict Refund calculation adhering to Rule 6 schedule policy
    if notice > timedelta(hours=48):
        refund_percent = 100
    elif notice >= timedelta(hours=24):
        refund_percent = 50
    else:
        refund_percent = 0

    refund_amount_cents = round(booking.price_cents * (refund_percent / 100.0))

    if refund_percent > 0:
        log_refund(db, booking, refund_percent)

    _settlement_pause()
    booking.status = "cancelled"
    db.commit()

    stats.record_cancel(booking.room_id, booking.price_cents)
    cache.invalidate_report(user.org_id)
    notifications.notify_cancelled(booking)

    return {
        "id": booking.id,
        "status": "cancelled",
        "refund_percent": refund_percent,
        "refund_amount_cents": refund_amount_cents,
    }
