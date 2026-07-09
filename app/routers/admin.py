"""Administrative reporting and export endpoints."""
from datetime import datetime, time

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

# cache মডিউল বাদ দেওয়া হয়েছে কারণ রুল ১২ অনুযায়ী লাইভ স্টেট দেখাতে হবে
from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # BUG FIX: ক্যাশ লেয়ার সম্পূর্ণ রিমুভ করা হয়েছে (Rule 12: Must reflect current state immediately)
    try:
        from_date = datetime.strptime(frm, "%Y-%m-%d").date()
        to_date = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError:
        raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")

    # BUG FIX: Inclusive [from, to] রেঞ্জ নিশ্চিত করার জন্য start এবং end টাইম সঠিকভাবে সেট করা হলো
    range_start = datetime.combine(from_date, time.min)
    range_end = datetime.combine(to_date, time.max)  # ঐ দিনের শেষ মুহূর্ত পর্যন্ত (23:59:59)

    rooms = db.query(Room).filter(Room.org_id == admin.org_id).order_by(Room.id.asc()).all()
    room_rows = []
    for room in rooms:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.status == "confirmed",
                Booking.start_time >= range_start,
                Booking.start_time <= range_end,  # <= ব্যবহার করে inclusive করা হলো
            )
            .all()
        )
        room_rows.append(
            {
                "room_id": room.id,
                "room_name": room.name,
                "confirmed_bookings": len(bookings),
                "revenue_cents": sum(b.price_cents for b in bookings),
            }
        )

    return {"from": frm, "to": to, "rooms": room_rows}


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    csv_body = generate_export(db, admin.org_id, admin.id, room_id, include_all)
    
    # BUG FIX: CSV ফাইল ডাউনলোডের জন্য সঠিক headers যুক্ত করা হলো
    headers = {
        "Content-Disposition": f"attachment; filename=bookings_export_{admin.org_id}.csv"
    }
    return Response(content=csv_body, media_type="text/csv", headers=headers)
