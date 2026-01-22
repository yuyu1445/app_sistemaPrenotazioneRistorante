from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal, ensure_customer_auth_columns
from app.models import Customer, Reservation, ReservationStatus, RestaurantTable, Staff, TableStatus
from app.schemas import (
    AvailabilityOut,
    BookingCreate,
    BookingOut,
    BookingUpdate,
    CustomerCreate,
    CustomerOut,
    CustomerRegister,
    LoginRequest,
    MyBookingOut,
    TableStatusUpdate,
    TokenResponse,
    UserProfile,
)
from app.services.booking_service import (
    begin_immediate,
    build_table_availability,
    find_available_table,
    is_table_available,
    run_with_retry,
)
from app.auth import (
    authenticate_customer,
    authenticate_staff,
    create_access_token,
    get_current_customer,
    get_current_staff,
    get_current_user,
    get_optional_customer,
    get_password_hash,
)

app = FastAPI(title="API Prenotazioni Ristorante")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def ensure_schema() -> None:
    ensure_customer_auth_columns()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _validate_time_range(time_start: time, time_end: time) -> None:
    if time_end <= time_start:
        raise HTTPException(
            status_code=422,
            detail="L'orario di fine deve essere successivo all'orario di inizio.",
        )


def _ensure_table_bookable(db: Session, table: RestaurantTable) -> None:
    if table.status in {TableStatus.OCCUPIED, TableStatus.OUT_OF_SERVICE}:
        db.rollback()
        raise HTTPException(status_code=409, detail="Il tavolo non e prenotabile nello stato attuale.")


def _reservation_to_booking_out(reservation: Reservation) -> BookingOut:
    return BookingOut(
        id=reservation.id,
        customer_id=reservation.customer_id,
        table_id=reservation.table_id,
        reservation_date=reservation.reservation_date,
        day_of_week=reservation.day_of_week,
        time_start=reservation.reservation_time,
        time_end=reservation.reservation_end_time,
        guest_count=reservation.guest_count,
        status=reservation.status,
    )


def _can_cancel_booking(reservation: Reservation) -> bool:
    time_since_creation = datetime.utcnow() - reservation.created_at
    return time_since_creation.total_seconds() <= 30 * 60  # 30 minuti


# === ENDPOINT AUTENTICAZIONE ===

@app.post("/auth/register", response_model=TokenResponse, status_code=201)
def register_customer(payload: CustomerRegister, db: Session = Depends(get_db)):
    existing_username = db.execute(
        select(Customer).where(Customer.username == payload.username)
    ).scalars().first()
    if existing_username:
        raise HTTPException(status_code=409, detail="Username gia in uso.")

    existing_email = db.execute(
        select(Customer).where(Customer.email == payload.email)
    ).scalars().first()
    if existing_email:
        raise HTTPException(status_code=409, detail="Email gia registrata.")

    existing_phone = db.execute(
        select(Customer).where(Customer.phone == payload.phone)
    ).scalars().first()
    if existing_phone:
        raise HTTPException(status_code=409, detail="Telefono gia registrato.")

    customer = Customer(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        is_active=True,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dati gia presenti nel sistema.")
    db.refresh(customer)

    access_token = create_access_token(
        data={"sub": str(customer.id), "user_type": "customer"}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_type="customer",
        user={
            "id": customer.id,
            "username": customer.username,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone": customer.phone,
        },
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    customer = authenticate_customer(db, payload.username, payload.password)
    if customer:
        access_token = create_access_token(
            data={"sub": str(customer.id), "user_type": "customer"}
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_type="customer",
            user={
                "id": customer.id,
                "username": customer.username,
                "full_name": customer.full_name,
                "email": customer.email,
                "phone": customer.phone,
            },
        )

    staff = authenticate_staff(db, payload.username, payload.password)
    if staff:
        access_token = create_access_token(
            data={"sub": str(staff.id), "user_type": "staff"}
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_type="staff",
            user={
                "id": staff.id,
                "username": staff.username,
                "full_name": staff.full_name,
                "role": staff.role,
            },
        )

    raise HTTPException(
        status_code=401,
        detail="Username o password non validi.",
    )


@app.get("/auth/me", response_model=UserProfile)
def get_profile(current_user: dict = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Non autenticato.")

    user = current_user["user"]
    user_type = current_user["type"]

    if user_type == "customer":
        return UserProfile(
            id=user.id,
            username=user.username or "",
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            user_type="customer",
        )
    else:
        return UserProfile(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            user_type="staff",
            role=user.role,
        )


# === ENDPOINT PRENOTAZIONI CLIENTE ===

@app.get("/my-bookings", response_model=list[MyBookingOut])
def get_my_bookings(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    reservations = db.execute(
        select(Reservation)
        .where(Reservation.customer_id == customer.id)
        .order_by(Reservation.reservation_date.desc(), Reservation.reservation_time.desc())
    ).scalars().all()

    result = []
    for r in reservations:
        table = db.get(RestaurantTable, r.table_id)
        result.append(MyBookingOut(
            id=r.id,
            table_id=r.table_id,
            table_number=table.table_number if table else 0,
            reservation_date=r.reservation_date,
            day_of_week=r.day_of_week,
            time_start=r.reservation_time,
            time_end=r.reservation_end_time,
            guest_count=r.guest_count,
            status=r.status,
            can_cancel=_can_cancel_booking(r) and r.status not in [ReservationStatus.CANCELLED, ReservationStatus.COMPLETED],
            created_at=r.created_at.isoformat(),
        ))

    return result


@app.delete("/my-bookings/{booking_id}")
def cancel_my_booking(
    booking_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, booking_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata.")

    if reservation.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Non puoi cancellare prenotazioni di altri clienti.")

    if reservation.status in [ReservationStatus.CANCELLED, ReservationStatus.COMPLETED]:
        raise HTTPException(status_code=400, detail="Questa prenotazione non puo essere cancellata.")

    if not _can_cancel_booking(reservation):
        raise HTTPException(
            status_code=400,
            detail="Puoi cancellare una prenotazione solo entro 30 minuti dalla creazione.",
        )

    reservation.status = ReservationStatus.CANCELLED
    db.commit()

    return {"message": "Prenotazione cancellata con successo."}


@app.get("/tables")
def list_tables(db: Session = Depends(get_db)):
    rows = db.execute(select(RestaurantTable).order_by(RestaurantTable.table_number)).scalars().all()
    return [
        {
            "id": r.id,
            "table_number": r.table_number,
            "capacity_max": r.capacity_max,
            "status": r.status.value,
        }
        for r in rows
    ]


@app.get("/availability", response_model=list[AvailabilityOut])
def list_availability(
    reservation_date: date,
    time_start: time,
    time_end: time,
    guest_count: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    _validate_time_range(time_start, time_end)
    return build_table_availability(db, reservation_date, time_start, time_end, guest_count)


@app.patch("/tables/{table_id}/status")
def update_table_status(table_id: int, payload: TableStatusUpdate, db: Session = Depends(get_db)):
    table = db.get(RestaurantTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Tavolo non trovato.")
    table.status = payload.status
    db.commit()
    db.refresh(table)
    return {"id": table.id, "status": table.status.value}


@app.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    rows = db.execute(select(Customer).order_by(Customer.full_name)).scalars().all()
    return [
        {"id": r.id, "full_name": r.full_name, "phone": r.phone, "email": r.email}
        for r in rows
    ]


@app.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, response: Response, db: Session = Depends(get_db)):
    existing = (
        db.execute(
            select(Customer).where(
                or_(Customer.email == payload.email, Customer.phone == payload.phone)
            )
        )
        .scalars()
        .first()
    )
    if existing:
        response.status_code = 200
        return existing

    customer = Customer(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.execute(
                select(Customer).where(
                    or_(Customer.email == payload.email, Customer.phone == payload.phone)
                )
            )
            .scalars()
            .first()
        )
        if existing:
            response.status_code = 200
            return existing
        raise HTTPException(status_code=409, detail="Cliente gia presente.")
    db.refresh(customer)
    return customer


@app.get("/reservations")
def list_reservations(db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Reservation).order_by(
                Reservation.reservation_date.desc(),
                Reservation.reservation_time.desc(),
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "customer_id": r.customer_id,
            "table_id": r.table_id,
            "reservation_date": r.reservation_date.isoformat(),
            "day_of_week": r.day_of_week,
            "reservation_time": r.reservation_time.isoformat(timespec="minutes"),
            "reservation_end_time": r.reservation_end_time.isoformat(timespec="minutes"),
            "guest_count": r.guest_count,
            "status": r.status.value,
        }
        for r in rows
    ]


@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(
    reservation_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[ReservationStatus] = None,
    customer_id: Optional[int] = None,
    customer_query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order: str = Query("date_desc"),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Intervallo date non valido.")

    query = select(Reservation)

    if order not in {"date_asc", "date_desc"}:
        raise HTTPException(status_code=422, detail="Parametro order non valido.")

    if reservation_date:
        query = query.where(Reservation.reservation_date == reservation_date)
    else:
        if date_from:
            query = query.where(Reservation.reservation_date >= date_from)
        if date_to:
            query = query.where(Reservation.reservation_date <= date_to)

    if status:
        query = query.where(Reservation.status == status)
    if customer_id:
        query = query.where(Reservation.customer_id == customer_id)
    if customer_query:
        query = query.join(Customer).where(
            or_(
                Customer.full_name.ilike(f"%{customer_query}%"),
                Customer.phone.ilike(f"%{customer_query}%"),
                Customer.email.ilike(f"%{customer_query}%"),
            )
        )

    if order == "date_asc":
        query = query.order_by(Reservation.reservation_date.asc(), Reservation.reservation_time.asc())
    else:
        query = query.order_by(desc(Reservation.reservation_date), desc(Reservation.reservation_time))

    rows = db.execute(query.offset(offset).limit(limit)).scalars().all()
    return [_reservation_to_booking_out(r) for r in rows]


@app.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    _validate_time_range(payload.time_start, payload.time_end)

    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")

    table: Optional[RestaurantTable] = None
    if payload.table_id is not None:
        table = db.get(RestaurantTable, payload.table_id)
        if table is None:
            raise HTTPException(status_code=404, detail="Tavolo non trovato.")
        if payload.guest_count > table.capacity_max:
            raise HTTPException(status_code=422, detail="Il numero di ospiti supera la capacita del tavolo.")

    def operation():
        begin_immediate(db)
        target_table = table

        if payload.table_id is not None:
            db.refresh(target_table)
            _ensure_table_bookable(db, target_table)
            if not is_table_available(
                db,
                target_table.id,
                payload.reservation_date,
                payload.time_start,
                payload.time_end,
            ):
                db.rollback()
                raise HTTPException(status_code=409, detail="Tavolo non disponibile nello slot richiesto.")
        else:
            target_table = find_available_table(
                db,
                payload.reservation_date,
                payload.time_start,
                payload.time_end,
                payload.guest_count,
            )
            if target_table is None:
                db.rollback()
                raise HTTPException(status_code=409, detail="Nessun tavolo disponibile nello slot richiesto.")

        reservation = Reservation(
            customer_id=payload.customer_id,
            table_id=target_table.id,
            reservation_date=payload.reservation_date,
            day_of_week=payload.reservation_date.isoweekday(),
            reservation_time=payload.time_start,
            reservation_end_time=payload.time_end,
            guest_count=payload.guest_count,
            status=ReservationStatus.PENDING,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
        return reservation

    reservation = run_with_retry(db, operation)
    return _reservation_to_booking_out(reservation)


@app.patch("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: int, payload: BookingUpdate, db: Session = Depends(get_db)):
    reservation = db.get(Reservation, booking_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata.")

    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Cliente non trovato.")

    new_date = payload.reservation_date or reservation.reservation_date
    new_start = payload.time_start or reservation.reservation_time
    new_end = payload.time_end or reservation.reservation_end_time
    _validate_time_range(new_start, new_end)

    slot_changed = any(
        value is not None
        for value in (
            payload.reservation_date,
            payload.time_start,
            payload.time_end,
            payload.table_id,
            payload.guest_count,
        )
    )
    should_check = slot_changed or payload.status == ReservationStatus.CONFIRMED

    new_table = reservation.table
    if payload.table_id is not None:
        new_table = db.get(RestaurantTable, payload.table_id)
        if new_table is None:
            raise HTTPException(status_code=404, detail="Tavolo non trovato.")

    new_guest_count = payload.guest_count if payload.guest_count is not None else reservation.guest_count
    if new_guest_count > new_table.capacity_max:
        raise HTTPException(status_code=422, detail="Il numero di ospiti supera la capacita del tavolo.")

    def operation():
        begin_immediate(db)
        if should_check:
            db.refresh(new_table)
            _ensure_table_bookable(db, new_table)
            if not is_table_available(
                db,
                new_table.id,
                new_date,
                new_start,
                new_end,
                exclude_reservation_id=reservation.id,
            ):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Conflitto di prenotazione sullo stesso tavolo e orario.",
                )

        reservation.customer_id = payload.customer_id or reservation.customer_id
        reservation.table_id = new_table.id
        reservation.reservation_date = new_date
        reservation.day_of_week = new_date.isoweekday()
        reservation.reservation_time = new_start
        reservation.reservation_end_time = new_end
        reservation.guest_count = new_guest_count
        if payload.status is not None:
            reservation.status = payload.status

        db.commit()
        db.refresh(reservation)
        return reservation

    reservation = run_with_retry(db, operation)
    return _reservation_to_booking_out(reservation)


@app.delete("/bookings/{booking_id}")
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    reservation = db.get(Reservation, booking_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata.")
    reservation.status = ReservationStatus.CANCELLED
    db.commit()
    return Response(status_code=204)
