import requests
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# 1. Validation de date

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# 2. Créer dossier de sauvegarde

def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir

# 3. Traitement des données JSON en DataFrame

def process_weather_data(data):
    records = []

    for record in data:
        date_time = record.get("date", "")
        if not date_time:
            continue

        records.append({
            "Date": date_time.split("T")[0],
            "Heure": date_time.split("T")[1][:5],
            "Température (°C)": round(record.get("tc"), 1) if record.get("tc") is not None else None,
            "Humidité (%)": record.get("u"),
            "Précipitations (mm)": record.get("rr1")
        })

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["Heure"] = pd.to_datetime(df["Heure"], format="%H:%M", errors="coerce").dt.strftime("%H:%M")
    df.sort_values(by=["Date", "Heure"], inplace=True)

    df["Température (°C)"] = df["Température (°C)"].interpolate(method="linear")
    df["Humidité (%)"] = df["Humidité (%)"].interpolate(method="linear")
    df.dropna(subset=["Température (°C)", "Humidité (%)"], inplace=True)

    return df

# 4. Requête API avec pagination

def get_weather_data(station, date):
    base_url = "https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/donnees-synop-essentielles-omm@public/records"
    all_data = []
    offset = 0
    limit = 100

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "where": f"date >= '{date}T00:00:00Z' AND date <= '{date}T23:59:59Z' AND nom = '{station}'",
            "sort": "date"
        }

        try:
            response = requests.get(base_url, params=params, timeout=25)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results:
                break
            all_data.extend(results)
            offset += limit
        except requests.Timeout:
            print("Temps d'attente dépassé !")
            break
        except requests.RequestException as e:
            print(f"Erreur API : {e}")
            break

    return [entry for entry in all_data if station.upper() in entry.get("nom", "").upper()]

# 5. Enregistrement JSON

def save_data_as_json(data, station, date):
    if not data:
        return
    file_path = create_data_directory() / f"weather_{station}_{date}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Données enregistrées sous {file_path}")

# 6. Affichage tableau terminal

def display_weather_table(df, station, date):
    if df.empty:
        print(f"Pas de données disponibles pour {station} à la date {date}.")
        return

    current_time = datetime.now()
    formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %Y")

    print("\n|--------------------------------------------|")
    print(f"| Weather station: {station:<32}|")
    print(f"| Today is the {date}. It's {current_time.strftime('%H:%M'):<15}|")
    print(f"| Chosen month: {formatted_date:<26}|")
    print("|----------------------------------------------|")
    print("|  Day                |  T(°C)  | Humidité(%)  |")
    print("|---------------------|---------|--------------|")

    for _, row in df.iterrows():
        temp = f"{row['Température (°C)']:.1f}".replace('.', ',') if pd.notna(row["Température (°C)"]) else "N/A"
        humidity = f"{row['Humidité (%)']:.1f}".replace('.', ',') if pd.notna(row["Humidité (%)"]) else "N/A"
        print(f"| {row['Date']} | {row['Heure']} | {temp:^7} | {humidity:^11} |")

    print("|--------------------------------------------|\n")
    print("\nRésumé des valeurs maximales et minimales :")
    print(f"Température max : {df['Température (°C)'].max()} °C")
    print(f"Température min : {df['Température (°C)'].min()} °C")
    print(f"Humidité max : {df['Humidité (%)'].max()} %")
    print(f"Humidité min : {df['Humidité (%)'].min()} %")

# 7. Graphe matplotlib

def plot_weather_data(df, station, date):
    if df.empty:
        print("Aucune donnée disponible pour le graphique.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["Heure"], df["Température (°C)"], 'r-o', label="Température (°C)")
    plt.twinx()
    plt.plot(df["Heure"], df["Humidité (%)"], 'b--s', label="Humidité (%)")
    plt.title(f"Évolution de la température et de l'humidité - {station} ({date})")
    plt.xlabel("Heure")
    plt.xticks(rotation=45)
    plt.grid()
    plt.show()

# 8. Export CSV

def save_data_as_csv(df, station, date):
    if df.empty:
        print("Aucune donnée à enregistrer.")
        return
    file_path = create_data_directory() / f"weather_{station}_{date}.csv"
    df.to_csv(file_path, index=False, sep=";", encoding="utf-8")
    print(f" Données enregistrées sous {file_path}")

# 9. Programme principal

def main():
    current_time = datetime.now()
    print("\n|--------------------------------------------|")
    print(f"| Welcome to Weather History Viewer          |")
    print(f"| Today is {current_time.strftime('%Y-%m-%d')}. It is {current_time.strftime('%H:%M'):<15}|")
    print("|--------------------------------------------|")

    station = input("\nEnter weather station name (e.g., ROUEN-BOOS): ").upper()
    date = input("Enter date (YYYY-MM-DD): ")

    if not is_valid_date(date):
        print("Format de date invalide. Veuillez entrer une date valide (YYYY-MM-DD).")
        return

    print("\nFetching weather data...")
    data = get_weather_data(station, date)
    if not data:
        print(f"Aucune donnée trouvée pour {station} à la date {date}.")
        return

    df = process_weather_data(data)
    if df.empty:
        print(f"Aucune donnée exploitable pour {station} à la date {date}.")
        return

    save_data_as_json(data, station, date)
    display_weather_table(df, station, date)
    save_data_as_csv(df, station, date)
    plot_weather_data(df, station, date)

if __name__ == "__main__":
    main()