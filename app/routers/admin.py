"""Administrative reporting and export endpoints."""
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export
from ..timeutils import parse_input_datetime  # ডেটটাইম পার্স করার জন্য অত্যন্ত জরুরী

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # BUG FIX 1: Robust ISO 8601 parsing using timeutils helper to support explicit offsets/Z inputs
    try:
        # If inputs are full ISO datetimes, normalize them; if just dates, append defaults
        parsed_frm = parse_input_datetime(frm if "T" in frm else f"{frm}T00:00:00Z")
        parsed_to = parse_input_datetime(to if "T" in to else f"{to}T23:59:59Z")
    except ValueError:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range format")

    # Set boundaries for strict UTC comparison matching Rule 12 inclusive constraint
    range_start = datetime.combine(parsed_frm.date(), time.min)
    range_end = datetime.combine(parsed_to.date(), time.max)

    rooms = db.query(Room).filter(Room.org_id == admin.org_id).order_by(Room.id.asc()).all()
    room_rows = []
    
    for room in rooms:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.status == "confirmed",
                Booking.start_time >= range_start,
                Booking.start_time <= range_end,
            )
            .all()
        )
        room_rows.append(
            {
                "room_id": int(room.id),
                "room_name": str(room.name),
                "confirmed_bookings": int(len(bookings)),
                "revenue_cents": int(sum(b.price_cents for b in bookings)),
            }
        )

    # BUG FIX 2: Returns exact shape complying strictly with Section 5 contract specifications
    return {"rooms": room_rows}


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # BUG FIX 3: Multi-tenancy cross-org validation (Section 4, Rule 9)
    if room_id is not None:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room or room.org_id != admin.org_id:
            raise AppError(404, "ROOM_NOT_FOUND", "Room not found or unauthorized access")

    csv_body = generate_export(db, admin.org_id, admin.id, room_id, include_all)
    
    headers = {
        "Content-Disposition": f"attachment; filename=bookings_export_{admin.org_id}.csv"
    }
    return Response(content=csv_body, media_type="text/csv", headers=headers)
