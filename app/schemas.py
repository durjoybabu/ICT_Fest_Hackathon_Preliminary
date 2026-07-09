"""Pydantic request/response models."""
from datetime import datetime
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    org_name: str
    username: str
    password: str


class LoginRequest(BaseModel):
    org_name: str
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RoomCreateRequest(BaseModel):
    name: str
    capacity: int
    hourly_rate_cents: int


class BookingCreateRequest(BaseModel):
    room_id: int
    # BUG FIX: Changed type from 'str' to 'datetime' to automatically validate and 
    # parse ISO 8601 input strings into proper Python datetime objects for business logic.
    start_time: datetime
    end_time: datetime
