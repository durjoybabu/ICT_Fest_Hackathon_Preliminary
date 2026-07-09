"""SQLAlchemy ORM models for the CoWork domain."""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _get_utc_now():
    """Helper function to return native/naive datetime structured from explicit UTC, 
    matching Rule 1 for internal SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "username", name="uq_user_org_username"),)

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    # BUG FIX 2: Using callable function reference that avoids deprecation and guarantees proper UTC generation
    created_at = Column(DateTime, default=_get_utc_now, nullable=False)


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    hourly_rate_cents = Column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="confirmed")
    # BUG FIX 1: Added unique=True constraint to enforce Rule 7 under high concurrent loads
    reference_code = Column(String, nullable=False, unique=True, index=True)
    price_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_get_utc_now, nullable=False)

    refunds = relationship("RefundLog", backref="booking")


class RefundLog(Base):
    __tablename__ = "refund_logs"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    processed_at = Column(DateTime, default=_get_utc_now, nullable=False)
