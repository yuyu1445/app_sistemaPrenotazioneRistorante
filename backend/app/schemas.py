from __future__ import annotations

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, conint

from app.models import ReservationStatus, TableStatus


class BookingCreate(BaseModel):
    customer_id: int = Field(..., gt=0)
    table_id: Optional[int] = Field(None, gt=0)
    reservation_date: date
    time_start: time
    time_end: time
    guest_count: conint(ge=1)


class BookingUpdate(BaseModel):
    customer_id: Optional[int] = Field(None, gt=0)
    table_id: Optional[int] = Field(None, gt=0)
    reservation_date: Optional[date] = None
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    guest_count: Optional[conint(ge=1)] = None
    status: Optional[ReservationStatus] = None


class BookingOut(BaseModel):
    id: int
    customer_id: int
    table_id: int
    reservation_date: date
    day_of_week: int
    time_start: time
    time_end: time
    guest_count: int
    status: ReservationStatus


class AvailabilityOut(BaseModel):
    id: int
    table_number: int
    capacity_max: int
    status: TableStatus
    available: bool
    selectable: bool
    label: str
    badge: str


class TableStatusUpdate(BaseModel):
    status: TableStatus


class CustomerCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=5, max_length=50)
    email: EmailStr


class CustomerOut(BaseModel):
    id: int
    full_name: str
    phone: str
    email: EmailStr
    username: Optional[str] = None


# === Schemi Autenticazione ===

class CustomerRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=5, max_length=50)
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user: dict


class UserProfile(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    user_type: str
    role: Optional[str] = None


# === Schemi Prenotazioni Cliente ===

class MyBookingOut(BaseModel):
    id: int
    table_id: int
    table_number: int
    reservation_date: date
    day_of_week: int
    time_start: time
    time_end: time
    guest_count: int
    status: ReservationStatus
    can_cancel: bool
    created_at: str
