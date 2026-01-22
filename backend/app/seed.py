from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import Base, Customer, Reservation, ReservationStatus, RestaurantTable, Staff, TableStatus
from app.auth import get_password_hash


TABLES = [
    {"table_number": 1, "capacity_max": 2},
    {"table_number": 2, "capacity_max": 2},
    {"table_number": 3, "capacity_max": 4},
    {"table_number": 4, "capacity_max": 4},
    {"table_number": 5, "capacity_max": 4},
    {"table_number": 6, "capacity_max": 6},
    {"table_number": 7, "capacity_max": 6},
    {"table_number": 8, "capacity_max": 8},
    {"table_number": 9, "capacity_max": 2},
    {"table_number": 10, "capacity_max": 4},
    {"table_number": 11, "capacity_max": 6},
    {"table_number": 12, "capacity_max": 8},
]

CUSTOMERS = [
    {"full_name": "Luca Bianchi", "phone": "+390001000001", "email": "luca.bianchi@example.com"},
    {"full_name": "Sara Rossi", "phone": "+390001000002", "email": "sara.rossi@example.com"},
    {"full_name": "Marco Conti", "phone": "+390001000003", "email": "marco.conti@example.com"},
    {"full_name": "Giulia Ferri", "phone": "+390001000004", "email": "giulia.ferri@example.com"},
    {"full_name": "Davide Greco", "phone": "+390001000005", "email": "davide.greco@example.com"},
    {"full_name": "Elena Russo", "phone": "+390001000006", "email": "elena.russo@example.com"},
    {"full_name": "Matteo Costa", "phone": "+390001000007", "email": "matteo.costa@example.com"},
    {"full_name": "Chiara Villa", "phone": "+390001000008", "email": "chiara.villa@example.com"},
    {"full_name": "Paolo Rinaldi", "phone": "+390001000009", "email": "paolo.rinaldi@example.com"},
    {"full_name": "Valentina Gallo", "phone": "+390001000010", "email": "valentina.gallo@example.com"},
    {"full_name": "Alessio Colombo", "phone": "+390001000011", "email": "alessio.colombo@example.com"},
    {"full_name": "Irene Moretti", "phone": "+390001000012", "email": "irene.moretti@example.com"},
    {"full_name": "Stefano Ricci", "phone": "+390001000013", "email": "stefano.ricci@example.com"},
    {"full_name": "Martina Riva", "phone": "+390001000014", "email": "martina.riva@example.com"},
    {"full_name": "Federico Marin", "phone": "+390001000015", "email": "federico.marin@example.com"},
    {"full_name": "Laura De Luca", "phone": "+390001000016", "email": "laura.deluca@example.com"},
    {"full_name": "Giorgio Sala", "phone": "+390001000017", "email": "giorgio.sala@example.com"},
    {"full_name": "Sofia Romano", "phone": "+390001000018", "email": "sofia.romano@example.com"},
    {"full_name": "Andrea Mancini", "phone": "+390001000019", "email": "andrea.mancini@example.com"},
    {"full_name": "Beatrice Fontana", "phone": "+390001000020", "email": "beatrice.fontana@example.com"},
]

STAFF_ACCOUNTS = [
    {"username": "admin", "password": "admin123", "full_name": "Amministratore", "role": "admin"},
    {"username": "staff", "password": "staff123", "full_name": "Staff Generico", "role": "waiter"},
    {"username": "staff1", "password": "staff123", "full_name": "Mario Rossi", "role": "waiter"},
    {"username": "staff2", "password": "staff123", "full_name": "Anna Verdi", "role": "waiter"},
]

TIME_SLOTS = [
    time(12, 0),
    time(12, 30),
    time(13, 0),
    time(13, 30),
    time(14, 0),
    time(19, 0),
    time(19, 30),
    time(20, 0),
    time(20, 30),
    time(21, 0),
    time(21, 30),
    time(22, 0),
]


def seed_tables(session) -> None:
    existing = session.scalars(select(RestaurantTable.id)).first()
    if existing is not None:
        return
    session.add_all(RestaurantTable(status=TableStatus.AVAILABLE, **row) for row in TABLES)


def seed_customers(session) -> None:
    existing = session.scalars(select(Customer.id)).first()
    if existing is not None:
        return
    session.add_all(Customer(**row) for row in CUSTOMERS)


def seed_staff(session) -> None:
    existing_usernames = set(session.scalars(select(Staff.username)).all())
    for account in STAFF_ACCOUNTS:
        if account["username"] in existing_usernames:
            continue
        staff = Staff(
            username=account["username"],
            password_hash=get_password_hash(account["password"]),
            full_name=account["full_name"],
            role=account["role"],
            is_active=True,
        )
        session.add(staff)


def _calculate_end_time(reservation_date: date, start_time: time, minutes: int = 90) -> time:
    return (datetime.combine(reservation_date, start_time) + timedelta(minutes=minutes)).time()


def _pick_status(reservation_date: date, today: date) -> ReservationStatus:
    if reservation_date < today:
        return random.choices(
            [ReservationStatus.COMPLETED, ReservationStatus.CANCELLED, ReservationStatus.CONFIRMED],
            weights=[0.7, 0.2, 0.1],
            k=1,
        )[0]
    return random.choices(
        [ReservationStatus.PENDING, ReservationStatus.CONFIRMED],
        weights=[0.6, 0.4],
        k=1,
    )[0]


def seed_reservations(session, days: int = 90) -> None:
    existing = session.scalars(select(Reservation.id)).first()
    if existing is not None:
        return

    tables = session.scalars(select(RestaurantTable)).all()
    customers = session.scalars(select(Customer)).all()
    if not tables or not customers:
        return

    today = date.today()
    used_slots: set[tuple[int, date, time]] = set()
    reservations: list[Reservation] = []

    for offset in range(days):
        reservation_date = today - timedelta(days=offset)
        daily_count = random.randint(2, 6)
        attempts = 0
        created = 0

        while created < daily_count and attempts < daily_count * 5:
            attempts += 1
            table = random.choice(tables)
            reservation_time = random.choice(TIME_SLOTS)
            slot_key = (table.id, reservation_date, reservation_time)
            if slot_key in used_slots:
                continue
            used_slots.add(slot_key)

            customer = random.choice(customers)
            guest_count = random.randint(1, table.capacity_max)
            reservations.append(
                Reservation(
                    customer_id=customer.id,
                    table_id=table.id,
                    reservation_date=reservation_date,
                    day_of_week=reservation_date.isoweekday(),
                    reservation_time=reservation_time,
                    reservation_end_time=_calculate_end_time(reservation_date, reservation_time),
                    guest_count=guest_count,
                    status=_pick_status(reservation_date, today),
                )
            )
            created += 1

    session.add_all(reservations)


def main() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        seed_tables(session)
        seed_customers(session)
        seed_staff(session)
        seed_reservations(session)
        session.commit()
        print("Database inizializzato con successo!")
        print("Account staff creati:")
        for account in STAFF_ACCOUNTS:
            print(f"  - Username: {account['username']}, Password: {account['password']}")


if __name__ == "__main__":
    main()
