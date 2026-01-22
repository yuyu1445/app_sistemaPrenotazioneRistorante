from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    DDL,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Time,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReservationStatus(str, enum.Enum):
    CONFIRMED = "confermata"
    PENDING = "in attesa"
    COMPLETED = "completata"
    CANCELLED = "cancellata"


class TableStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    OUT_OF_SERVICE = "out_of_service"


class RestaurantTable(Base):
    __tablename__ = "restaurant_table"
    __table_args__ = (
        CheckConstraint("capacity_max > 0", name="ck_table_capacity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    capacity_max: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TableStatus] = mapped_column(
        Enum(TableStatus, native_enum=False, create_constraint=True),
        default=TableStatus.AVAILABLE,
        nullable=False,
        index=True,
    )

    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation",
        back_populates="table",
        cascade="all, delete-orphan",
    )


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="waiter", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Reservation(Base):
    __tablename__ = "reservation"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_reservation_day_of_week"),
        CheckConstraint("guest_count > 0", name="ck_reservation_guest_count_positive"),
        CheckConstraint(
            "reservation_end_time > reservation_time",
            name="ck_reservation_end_time_after_start",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("restaurant_table.id"), nullable=False, index=True)
    reservation_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reservation_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    reservation_end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, native_enum=False, create_constraint=True),
        default=ReservationStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="reservations")
    table: Mapped[RestaurantTable] = relationship("RestaurantTable", back_populates="reservations")


event.listen(
    Reservation.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS trg_reservation_retention
        AFTER INSERT ON reservation
        BEGIN
            DELETE FROM reservation
            WHERE reservation_date < date('now', '-90 days');
        END;
        """
    ),
)
