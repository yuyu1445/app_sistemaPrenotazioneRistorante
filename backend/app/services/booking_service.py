from __future__ import annotations

import time as time_module
from datetime import date, time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import Reservation, ReservationStatus, RestaurantTable, TableStatus

_LOCKED_ERROR = "database is locked"


def begin_immediate(db: Session) -> None:
    db.rollback()
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")


def run_with_retry(db: Session, operation, retries: int = 3, base_delay: float = 0.05):
    for attempt in range(retries):
        try:
            return operation()
        except OperationalError as exc:
            db.rollback()
            if _LOCKED_ERROR not in str(exc).lower() or attempt == retries - 1:
                raise
            time_module.sleep(base_delay * (attempt + 1))


def is_table_available(
    db: Session,
    table_id: int,
    reservation_date: date,
    time_start: time,
    time_end: time,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    query = select(Reservation.id).where(
        Reservation.table_id == table_id,
        Reservation.reservation_date == reservation_date,
        Reservation.status != ReservationStatus.CANCELLED,
        Reservation.reservation_time < time_end,
        Reservation.reservation_end_time > time_start,
    )
    if exclude_reservation_id is not None:
        query = query.where(Reservation.id != exclude_reservation_id)
    return db.execute(query).first() is None


def find_available_table(
    db: Session,
    reservation_date: date,
    time_start: time,
    time_end: time,
    guest_count: int,
) -> Optional[RestaurantTable]:
    query = (
        select(RestaurantTable)
        .where(
            RestaurantTable.capacity_max >= guest_count,
            RestaurantTable.status.notin_([TableStatus.OCCUPIED, TableStatus.OUT_OF_SERVICE]),
        )
        .order_by(RestaurantTable.capacity_max, RestaurantTable.table_number)
    )
    for table in db.execute(query).scalars().all():
        if is_table_available(db, table.id, reservation_date, time_start, time_end):
            return table
    return None


def build_table_availability(
    db: Session,
    reservation_date: date,
    time_start: time,
    time_end: time,
    guest_count: int,
) -> list[dict]:
    tables = db.execute(select(RestaurantTable).order_by(RestaurantTable.table_number)).scalars().all()
    availability: list[dict] = []

    for table in tables:
        capacity_ok = table.capacity_max >= guest_count
        status_blocked = table.status in {TableStatus.OCCUPIED, TableStatus.OUT_OF_SERVICE}
        conflicts = is_table_available(db, table.id, reservation_date, time_start, time_end) is False

        available = False
        selectable = False
        label = "Non disponibile"
        badge = "unavailable"

        if not capacity_ok:
            label = "Capienza insufficiente"
        elif status_blocked:
            label = "Non prenotabile"
        elif conflicts:
            label = "Gia prenotato"
        else:
            available = True
            selectable = True
            if table.status == TableStatus.RESERVED:
                label = "Disponibile (riservato)"
                badge = "warning"
            else:
                label = "Disponibile"
                badge = "available"

        availability.append(
            {
                "id": table.id,
                "table_number": table.table_number,
                "capacity_max": table.capacity_max,
                "status": table.status,
                "available": available,
                "selectable": selectable,
                "label": label,
                "badge": badge,
            }
        )

    return availability
