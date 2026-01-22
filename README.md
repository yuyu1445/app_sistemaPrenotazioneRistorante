# Sistema Prenotazioni Ristorante

Applicazione web full-stack per la gestione delle prenotazioni di un ristorante, con vista cliente per prenotare tavoli e vista staff per gestire le prenotazioni.

## Tecnologie

| Componente | Stack |
|------------|-------|
| **Backend** | FastAPI + SQLAlchemy + SQLite |
| **Frontend** | Vue 3 (CDN) + CSS custom |
| **Report** | Matplotlib + python-pptx |

## Struttura del progetto

```
test_finale/
├── backend/
│   ├── app/
│   │   ├── main.py              # Endpoint API FastAPI
│   │   ├── models.py            # Modelli ORM SQLAlchemy
│   │   ├── schemas.py           # Schemi Pydantic
│   │   ├── database.py          # Configurazione database
│   │   ├── seed.py              # Popolamento dati iniziali
│   │   └── services/
│   │       └── booking_service.py
│   └── ristorante.db            # Database SQLite (generato)
├── frontend/
│   ├── index.html               # Pagina principale Vue 3
│   ├── app.js                   # Logica applicazione Vue
│   ├── styles.css               # Stili CSS
│   └── package.json             # Configurazione npm
├── requirements.txt             # Dipendenze Python
├── genera_grafici_prenotazioni.py  # Script generazione grafici
├── crea_powerpoint.py           # Script creazione PowerPoint
└── README.md
```

## Requisiti

- **Python** 3.10+
- **Node.js** 18+ (opzionale, per server frontend)

## Installazione

### 1. Clona il repository

```bash
git clone <repository-url>
cd test_finale
```

### 2. Configura il Backend

```bash
# Crea ambiente virtuale (consigliato)
python -m venv .venv

# Attiva ambiente virtuale
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Installa dipendenze Python
pip install -r requirements.txt
```

### 3. Inizializza il Database

```bash
cd backend
python -m app.seed
```

Questo comando crea il database `ristorante.db` con:
- 12 tavoli (capacita 2-8 posti)
- 20 clienti di esempio
- Prenotazioni di esempio degli ultimi 90 giorni

### 4. Configura il Frontend (opzionale)

```bash
cd frontend
npm install
```

## Avvio dell'applicazione

### Avvia il Backend (API)

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

L'API sara disponibile su: `http://127.0.0.1:8000`

Documentazione API interattiva: `http://127.0.0.1:8000/docs`

### Avvia il Frontend

**Opzione 1: Con npm (consigliato)**
```bash
cd frontend
npm run dev
```

**Opzione 2: Con Python**
```bash
cd frontend
python -m http.server 5173
```

Il frontend sara disponibile su: `http://127.0.0.1:5173`

## Utilizzo

### Vista Cliente
1. Apri `http://127.0.0.1:5173`
2. Clicca "Prenota come cliente"
3. Seleziona data, orario e numero ospiti
4. Scegli un tavolo disponibile
5. Compila i dati personali e conferma

### Vista Staff
1. Apri `http://127.0.0.1:5173`
2. Clicca "Area staff"
3. Visualizza le prenotazioni del giorno
4. Conferma, completa o annulla prenotazioni
5. Filtra per stato (in attesa, confermata, completata, cancellata)

## Autenticazione

Il login avviene tramite `POST /auth/login` (staff e clienti), mentre i clienti possono registrarsi con `POST /auth/register`.

Account amministratori predefiniti:
- `admin` / `admin123`
- `staff1` / `staff123`
- `staff2` / `staff123`

## API Endpoints

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/tables` | Lista tutti i tavoli |
| PATCH | `/tables/{id}/status` | Aggiorna stato tavolo |
| GET | `/customers` | Lista tutti i clienti |
| POST | `/customers` | Crea nuovo cliente |
| GET | `/reservations` | Lista tutte le prenotazioni |
| GET | `/bookings` | Lista prenotazioni con filtri |
| POST | `/bookings` | Crea nuova prenotazione |
| PATCH | `/bookings/{id}` | Modifica prenotazione |
| DELETE | `/bookings/{id}` | Cancella prenotazione |
| GET | `/availability` | Verifica disponibilita tavoli |

## Generazione Report

### Genera grafici statistici

```bash
python genera_grafici_prenotazioni.py
```

Genera 3 grafici PNG:
- `grafico_occupazione_oraria.png` - Occupazione media per fascia oraria
- `grafico_giorni_settimana.png` - Prenotazioni per giorno della settimana
- `grafico_tendenze_3_mesi.png` - Trend prenotazioni ultimi 3 mesi

### Crea presentazione PowerPoint

```bash
python crea_powerpoint.py
```

Genera `Report_Prenotazioni.pptx` con:
- Slide titolo
- 3 slide con i grafici
- Slide conclusioni e insight

## Configurazione

### Endpoint API (Frontend)

Modifica in `frontend/index.html`:
```javascript
window.__API_BASE__ = 'http://127.0.0.1:8000';
```

### Durata prenotazione

Modifica in `frontend/index.html`:
```javascript
window.__BOOKING_DEFAULT_DURATION__ = 90; // minuti
```

### CORS (Backend)

Le origini consentite sono configurate in `backend/app/main.py`:
```python
allow_origins=[
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
```

## Stati delle prenotazioni

| Stato | Descrizione |
|-------|-------------|
| `in attesa` | Prenotazione ricevuta, in attesa di conferma |
| `confermata` | Prenotazione confermata dallo staff |
| `completata` | Cliente arrivato e servito |
| `cancellata` | Prenotazione annullata |

## Stati dei tavoli

| Stato | Descrizione |
|-------|-------------|
| `available` | Tavolo disponibile per prenotazioni |
| `occupied` | Tavolo attualmente occupato |
| `reserved` | Tavolo riservato (prenotabile con avviso) |
| `out_of_service` | Tavolo fuori servizio |

## Troubleshooting

### Errore "database is locked"
Il sistema gestisce automaticamente i conflitti di concorrenza con retry automatici.

### Frontend non si connette al backend
1. Verifica che il backend sia in esecuzione sulla porta 8000
2. Controlla che `window.__API_BASE__` sia configurato correttamente
3. Verifica che CORS sia abilitato per l'origine del frontend

### Database vuoto
Esegui lo script di seed:
```bash
cd backend
python -m app.seed
```
