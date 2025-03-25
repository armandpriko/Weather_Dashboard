import requests
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

#  Vérifier si une date entrée est valide
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

#  Créer un dossier "data" s'il n'existe pas déjà
def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir

# Transformer les données JSON en DataFrame Pandas
def process_weather_data(data):
    """Transforme les données JSON en DataFrame exploitable."""
    records = []

    for record in data:
        date_time = record.get("date", "")
        if not date_time:
            continue  # Sauter les entrées sans date

        records.append({
            "Date": date_time.split("T")[0],  # YYYY-MM-DD
            "Heure": date_time.split("T")[1][:5],  # HH:MM
            "Température (°C)": round(record.get("tc", 0), 1) if record.get("tc") is not None else None,
            "Humidité (%)": record.get("u", None),
            "Précipitations (mm)": record.get("rr1", None)
        })
    df = pd.DataFrame(records)

    if df.empty:
        return df
    df["Heure"] = pd.to_datetime(df["Heure"], format="%H:%M")

    # Arrondi au multiple de 3h le plus proche
    df["Heure"] = df["Heure"].dt.floor("3H").dt.strftime("%H:%M")

    df = df[df["Heure"].isin(["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00","22:00"])]


    return df


#  Obtenir les données météo via l'API OpenDataSoft
def get_weather_data(station, date):
    """Télécharge les données météo pour une station et une date spécifique"""
    
    base_url = "https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/donnees-synop-essentielles-omm@public/records"

    params = {
        "limit": 100,  # API limite à 100 résultats
        "refine.nom": station,
        "where": f"date >= '{date}T00:00:00Z' AND date <= '{date}T23:59:59Z'",
        "sort": "date"
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=25)
        response.raise_for_status()
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            print("Erreur API : Réponse non valide.")
            return []
            
        if "results" not in data or not data["results"]:
            print(f"Aucune donnée trouvée pour la station '{station}' à la date '{date}'.")
            return []
        
         #  Ajoute cette ligne pour voir tous les noms des stations dans la réponse API
        print("\n Liste des stations retournées par l'API :", [entry.get("nom", "") for entry in data["results"]])

        valid_data = [entry for entry in data["results"] if station.upper() in entry.get("nom", "").upper()]

        if not valid_data:
            print(f"Aucune donnée exacte pour la station '{station}' à la date '{date}'.")
            return []
        return valid_data

    except requests.Timeout:
        print("Temps d'attente dépassé ! Réessayez plus tard.")
        return []
    except requests.RequestException as e:
        print(f"Erreur API : {e}")
        return []

#  Enregistrer les données JSON dans un fichier
def save_data_as_json(data, station, date):
    if not data:
        return
    
    data_dir = create_data_directory()
    file_path = data_dir / f"weather_{station}_{date}.json"

    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

    print(f"Données enregistrées sous {file_path}")

#  Extraction et affichage des informations essentielles
def display_weather_table(df, station, date):
    """Affiche les données météo sous forme tabulaire."""

    if df.empty:
        print(f"Pas de données disponibles pour la station {station} à la date {date}.")
        return

    # Convertir la date en objet datetime pour formater le mois et l'année
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %Y")
    current_time = datetime.now()

    print("\n|--------------------------------------------|")
    print(f"| Weather station: {station}                  |")
    print(f"| Today is the {date}. It's {current_time.strftime('%H:%M')}|")
    print(f"| Chosen month: {formatted_date}                     |")
    print("|----------------------------------------------|")
    print("|  Day                |  T(°C)  | Humidité(%)  |")
    print("|---------------------|---------|--------------|")

    for _, row in df.iterrows():
        temp = f"{round(row['Température (°C)'], 1):.1f}".replace('.', ',') if pd.notna(row["Température (°C)"]) else "N/A"
        humidity = f"{row['Humidité (%)']:.1f}".replace('.', ',') if pd.notna(row["Humidité (%)"]) else "N/A"
        precipitation = f"{row['Précipitations (mm)']:.1f}".replace('.', ',') if pd.notna(row["Précipitations (mm)"]) else "N/A"

        print(f"| {row['Date']} | {row['Heure']} | {temp:^7} | {humidity:^11} |")

    print("|--------------------------------------------|\n")

    # Affichage du résumé statistiquer
    print("\nRésumé des valeurs maximales et minimales :")
    print(f"Température max : {df['Température (°C)'].max()} °C")
    print(f"Température min : {df['Température (°C)'].min()} °C")
    print(f"Humidité max : {df['Humidité (%)'].max()} %")
    print(f"Humidité min : {df['Humidité (%)'].min()} %")


def plot_weather_data(df, station, date):
    """Affiche les graphiques de température et d'humidité."""
    
    if df.empty:
        print("Aucune donnée disponible pour le graphique.")
        return

    plt.figure(figsize=(10, 5))
    
    # Tracé des températures
    plt.plot(df["Heure"], df["Température (°C)"], marker='o', linestyle='-', color='r', label="Température (°C)")

    # Ajout de l'humidité sur un second axe
    plt.twinx()
    plt.plot(df["Heure"], df["Humidité (%)"], marker='s', linestyle='--', color='b', label="Humidité (%)")

    plt.title(f"Évolution de la température et de l'humidité - {station} ({date})")
    plt.xlabel("Heure")
    plt.xticks(rotation=45)
    plt.legend(loc="upper left")

    plt.grid()
    plt.show()

def save_data_as_csv(df, station, date):
    """Enregistre les données dans un fichier CSV."""
    
    if df.empty:
        print("Aucune donnée à enregistrer.")
        return
    
    data_dir = create_data_directory()
    file_path = data_dir / f"weather_{station}_{date}.csv"
    
    df.to_csv(file_path, index=False, sep=";", encoding="utf-8")
    
    print(f" Données enregistrées sous {file_path}")


#  Fonction principale
def main():
    current_time = datetime.now()

    # Message de bienvenue
    print("\n|--------------------------------------------|")
    print(f"| Welcome to Weather History Viewer          |")
    print(f"| Today is {current_time.strftime('%Y-%m-%d')}. It is {current_time.strftime('%H:%M')}           |")
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

    # Transformer les données JSON en DataFrame
    df = process_weather_data(data)

    if df.empty:
        print(f"Aucune donnée exploitable pour {station} à la date {date}.")
        return

    # Enregistrer les données JSON
    save_data_as_json(data, station, date)

    # Affichage des données sous forme tabulaire
    display_weather_table(df, station, date)

        # Sauvegarde en CSV
    save_data_as_csv(df, station, date)

    # Affichage des graphiques
    plot_weather_data(df, station, date)


if __name__ == "__main__":
    main() 

    