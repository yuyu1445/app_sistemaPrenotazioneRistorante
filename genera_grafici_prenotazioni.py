"""
Script per generare grafici delle prenotazioni per PowerPoint.
Genera 3 grafici:
1. Occupazione media dei tavoli per fascia oraria
2. Giorni della settimana con più prenotazioni
3. Tendenze di prenotazione negli ultimi 3 mesi
"""

import sqlite3
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict
import os

# Percorso del database
DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "ristorante.db")

# Configurazione stile grafici
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'accent': '#F18F01',
    'success': '#C73E1D',
    'gradient': ['#2E86AB', '#3498db', '#5dade2', '#85c1e9', '#aed6f1', '#d6eaf8', '#ebf5fb']
}

# Mapping giorni settimana (ISO: 1=Lunedì, 7=Domenica)
GIORNI_SETTIMANA = {
    1: 'Lunedì',
    2: 'Martedì',
    3: 'Mercoledì',
    4: 'Giovedì',
    5: 'Venerdì',
    6: 'Sabato',
    7: 'Domenica'
}

# Fasce orarie
FASCE_ORARIE = {
    '12:00-13:00': (12, 13),
    '13:00-14:00': (13, 14),
    '14:00-15:00': (14, 15),
    '19:00-20:00': (19, 20),
    '20:00-21:00': (20, 21),
    '21:00-22:00': (21, 22),
    '22:00-23:00': (22, 23)
}


def get_db_connection():
    """Connessione al database SQLite."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database non trovato: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_total_tables(conn):
    """Ottiene il numero totale di tavoli."""
    cursor = conn.execute("SELECT COUNT(*) FROM restaurant_table WHERE status != 'fuori_servizio'")
    return cursor.fetchone()[0]


def grafico_occupazione_fascia_oraria(conn, output_path="grafico_occupazione_oraria.png"):
    """
    Grafico 1: Occupazione media dei tavoli per fascia oraria.
    Mostra quanti tavoli sono mediamente occupati in ogni fascia oraria.
    """
    print("Generando grafico occupazione per fascia oraria...")

    total_tables = get_total_tables(conn)

    # Query per contare prenotazioni per ora
    query = """
        SELECT
            CAST(strftime('%H', reservation_time) AS INTEGER) as ora,
            COUNT(*) as num_prenotazioni,
            COUNT(DISTINCT reservation_date) as giorni_distinti
        FROM reservation
        WHERE status != 'cancellata'
        GROUP BY ora
        ORDER BY ora
    """

    cursor = conn.execute(query)
    risultati = cursor.fetchall()

    # Organizza dati per fascia oraria
    occupazione_per_fascia = {}

    for row in risultati:
        ora = row['ora']
        num_prenotazioni = row['num_prenotazioni']
        giorni = row['giorni_distinti'] if row['giorni_distinti'] > 0 else 1

        # Media prenotazioni per giorno in quell'ora
        media_giornaliera = num_prenotazioni / giorni
        percentuale_occupazione = (media_giornaliera / total_tables) * 100 if total_tables > 0 else 0

        # Assegna alla fascia oraria corrispondente
        for fascia, (inizio, fine) in FASCE_ORARIE.items():
            if inizio <= ora < fine:
                occupazione_per_fascia[fascia] = percentuale_occupazione
                break

    # Ordina le fasce orarie
    fasce_ordinate = ['12:00-13:00', '13:00-14:00', '14:00-15:00',
                      '19:00-20:00', '20:00-21:00', '21:00-22:00', '22:00-23:00']

    fasce = []
    valori = []
    for fascia in fasce_ordinate:
        if fascia in occupazione_per_fascia:
            fasce.append(fascia)
            valori.append(occupazione_per_fascia[fascia])

    if not fasce:
        print("  Nessun dato trovato per le fasce orarie. Uso dati di esempio.")
        fasce = fasce_ordinate
        valori = [45, 65, 40, 55, 85, 90, 60]  # Dati esempio

    # Crea il grafico
    fig, ax = plt.subplots(figsize=(12, 6))

    bars = ax.bar(fasce, valori, color=COLORS['gradient'][:len(fasce)], edgecolor='white', linewidth=1.5)

    # Aggiungi etichette sui bar
    for bar, val in zip(bars, valori):
        height = bar.get_height()
        ax.annotate(f'{val:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=11, fontweight='bold')

    ax.set_xlabel('Fascia Oraria', fontsize=12, fontweight='bold')
    ax.set_ylabel('Occupazione Media (%)', fontsize=12, fontweight='bold')
    ax.set_title('Occupazione Media dei Tavoli per Fascia Oraria', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim(0, 100)

    # Linea di riferimento al 50%
    ax.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Soglia 50%')
    ax.legend(loc='upper right')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Salvato: {output_path}")
    return output_path


def grafico_giorni_settimana(conn, output_path="grafico_giorni_settimana.png"):
    """
    Grafico 2: Giorni della settimana con più prenotazioni.
    Mostra la distribuzione delle prenotazioni per giorno della settimana.
    """
    print("Generando grafico prenotazioni per giorno della settimana...")

    query = """
        SELECT
            day_of_week,
            COUNT(*) as num_prenotazioni
        FROM reservation
        WHERE status != 'cancellata'
        GROUP BY day_of_week
        ORDER BY day_of_week
    """

    cursor = conn.execute(query)
    risultati = cursor.fetchall()

    # Prepara dati
    giorni = []
    prenotazioni = []

    for row in risultati:
        giorno_num = row['day_of_week']
        giorni.append(GIORNI_SETTIMANA.get(giorno_num, f'Giorno {giorno_num}'))
        prenotazioni.append(row['num_prenotazioni'])

    if not giorni:
        print("  Nessun dato trovato. Uso dati di esempio.")
        giorni = list(GIORNI_SETTIMANA.values())
        prenotazioni = [25, 30, 35, 40, 65, 80, 55]  # Dati esempio

    # Trova il giorno con più prenotazioni per evidenziarlo
    max_idx = prenotazioni.index(max(prenotazioni))
    colori = [COLORS['primary']] * len(giorni)
    colori[max_idx] = COLORS['accent']  # Evidenzia il massimo

    # Crea il grafico
    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.bar(giorni, prenotazioni, color=colori, edgecolor='white', linewidth=1.5)

    # Aggiungi etichette
    for bar, val in zip(bars, prenotazioni):
        height = bar.get_height()
        ax.annotate(f'{val}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=11, fontweight='bold')

    ax.set_xlabel('Giorno della Settimana', fontsize=12, fontweight='bold')
    ax.set_ylabel('Numero di Prenotazioni', fontsize=12, fontweight='bold')
    ax.set_title('Distribuzione Prenotazioni per Giorno della Settimana', fontsize=14, fontweight='bold', pad=20)

    # Aggiungi legenda per il giorno con più prenotazioni
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=COLORS['accent'], label=f'Giorno più richiesto: {giorni[max_idx]}')]
    ax.legend(handles=legend_elements, loc='upper left')

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Salvato: {output_path}")
    return output_path


def grafico_tendenze_3_mesi(conn, output_path="grafico_tendenze_3_mesi.png"):
    """
    Grafico 3: Tendenze di prenotazione negli ultimi 3 mesi.
    Mostra l'andamento settimanale delle prenotazioni.
    """
    print("Generando grafico tendenze ultimi 3 mesi...")

    # Calcola data 3 mesi fa
    oggi = datetime.now().date()
    tre_mesi_fa = oggi - timedelta(days=90)

    query = """
        SELECT
            reservation_date,
            COUNT(*) as num_prenotazioni
        FROM reservation
        WHERE status != 'cancellata'
          AND reservation_date >= ?
        GROUP BY reservation_date
        ORDER BY reservation_date
    """

    cursor = conn.execute(query, (tre_mesi_fa.isoformat(),))
    risultati = cursor.fetchall()

    # Raggruppa per settimana
    prenotazioni_settimanali = defaultdict(int)

    for row in risultati:
        data = datetime.strptime(row['reservation_date'], '%Y-%m-%d').date()
        # Calcola inizio settimana (lunedì)
        inizio_settimana = data - timedelta(days=data.weekday())
        prenotazioni_settimanali[inizio_settimana] += row['num_prenotazioni']

    if not prenotazioni_settimanali:
        print("  Nessun dato trovato per gli ultimi 3 mesi. Uso dati di esempio.")
        # Genera dati di esempio
        for i in range(12):
            settimana = oggi - timedelta(weeks=11-i)
            inizio_settimana = settimana - timedelta(days=settimana.weekday())
            prenotazioni_settimanali[inizio_settimana] = 20 + (i * 3) + (i % 3) * 5

    # Ordina per data
    settimane_ordinate = sorted(prenotazioni_settimanali.keys())
    date = settimane_ordinate
    valori = [prenotazioni_settimanali[s] for s in settimane_ordinate]

    # Crea il grafico
    fig, ax = plt.subplots(figsize=(14, 6))

    # Grafico a linea con area
    ax.fill_between(date, valori, alpha=0.3, color=COLORS['primary'])
    ax.plot(date, valori, color=COLORS['primary'], linewidth=2.5, marker='o', markersize=6)

    # Aggiungi linea di tendenza
    if len(date) > 1:
        import numpy as np
        x_numeric = list(range(len(date)))
        z = np.polyfit(x_numeric, valori, 1)
        p = np.poly1d(z)
        ax.plot(date, p(x_numeric), "--", color=COLORS['secondary'],
                linewidth=2, label=f'Tendenza ({"+crescente" if z[0] > 0 else "-decrescente"})')

    # Evidenzia massimo e minimo
    max_idx = valori.index(max(valori))
    min_idx = valori.index(min(valori))

    ax.scatter([date[max_idx]], [valori[max_idx]], color=COLORS['accent'],
               s=150, zorder=5, label=f'Picco: {valori[max_idx]} prenotazioni')
    ax.scatter([date[min_idx]], [valori[min_idx]], color=COLORS['success'],
               s=150, zorder=5, label=f'Minimo: {valori[min_idx]} prenotazioni')

    ax.set_xlabel('Settimana', fontsize=12, fontweight='bold')
    ax.set_ylabel('Numero di Prenotazioni', fontsize=12, fontweight='bold')
    ax.set_title('Tendenze di Prenotazione - Ultimi 3 Mesi (per settimana)', fontsize=14, fontweight='bold', pad=20)

    # Formatta asse X con date
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))

    plt.xticks(rotation=45, ha='right')
    ax.legend(loc='upper left')

    # Aggiungi griglia
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"  Salvato: {output_path}")
    return output_path


def main():
    """Genera tutti i grafici per il PowerPoint."""
    print("=" * 60)
    print("GENERAZIONE GRAFICI PRENOTAZIONI PER POWERPOINT")
    print("=" * 60)

    # Directory output
    output_dir = os.path.dirname(__file__)

    try:
        conn = get_db_connection()
        print(f"\nConnesso al database: {DB_PATH}")

        # Verifica dati disponibili
        cursor = conn.execute("SELECT COUNT(*) FROM reservation")
        total_reservations = cursor.fetchone()[0]
        print(f"Prenotazioni totali nel database: {total_reservations}")

        total_tables = get_total_tables(conn)
        print(f"Tavoli disponibili: {total_tables}\n")

        # Genera i grafici
        grafici_generati = []

        # Grafico 1: Occupazione per fascia oraria
        path1 = os.path.join(output_dir, "grafico_occupazione_oraria.png")
        grafico_occupazione_fascia_oraria(conn, path1)
        grafici_generati.append(path1)

        # Grafico 2: Giorni della settimana
        path2 = os.path.join(output_dir, "grafico_giorni_settimana.png")
        grafico_giorni_settimana(conn, path2)
        grafici_generati.append(path2)

        # Grafico 3: Tendenze 3 mesi
        path3 = os.path.join(output_dir, "grafico_tendenze_3_mesi.png")
        grafico_tendenze_3_mesi(conn, path3)
        grafici_generati.append(path3)

        conn.close()

        print("\n" + "=" * 60)
        print("GRAFICI GENERATI CON SUCCESSO!")
        print("=" * 60)
        print("\nFile creati:")
        for path in grafici_generati:
            print(f"  - {os.path.basename(path)}")
        print("\nOra puoi inserire questi grafici nel tuo PowerPoint.")

    except FileNotFoundError as e:
        print(f"\nERRORE: {e}")
        print("Assicurati che il database esista eseguendo prima l'applicazione.")
    except Exception as e:
        print(f"\nERRORE: {e}")
        raise


if __name__ == "__main__":
    main()
