import requests
import json
import calendar
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
from fpdf import FPDF
from pathlib import Path
import os



# ---- CONFIG FLASK ----
app = Flask(__name__)

# ---- CONFIG DOSSIER DATA ----
def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir

# ---- RECUPERATION DES DONNEES METEO MENSUELLES ----
def get_monthly_weather_data(station, year, month):
    """Télécharge les données météo pour une station sur un mois donné"""
    base_url = "https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/donnees-synop-essentielles-omm@public/records"

    last_day = calendar.monthrange(year, month)[1]
    date_prefix = f"{year}-{month:02d}"

    params = {
        "limit": 100,
        "where": f"date >= '{date_prefix}-01T00:00:00Z' AND date <= '{date_prefix}-{last_day}T23:59:59Z'",
        "sort": "date"
    }

    try:
        response = requests.get(base_url, params=params, timeout=25)
        response.raise_for_status()
        data = response.json()

        # Vérification de la présence de "results"
        if "results" not in data or not data["results"]:
            print(f"❌ Aucune donnée trouvée pour {station} en {date_prefix}.")
            return []

        # Liste des stations disponibles
        available_stations = [entry.get("nom", "").upper() for entry in data["results"]]
        print("✅ Stations disponibles :", available_stations)

        # Vérifie si la station demandée existe
        if station.upper() not in available_stations:
            print(f"❌ Station '{station}' introuvable. Choisissez parmi :", available_stations)
            return []

        # Filtrer uniquement les données de la station demandée
        filtered_data = [entry for entry in data["results"] if entry.get("nom", "").upper() == station.upper()]
        
        if not filtered_data:
            print(f"❌ Aucune donnée spécifique pour la station '{station}' en {date_prefix}.")
            return []

        return filtered_data

    except requests.RequestException as e:
        print(f"❌ Erreur API : {e}")
        return []


# ---- TRANSFORMATION EN DATAFRAME ----
def process_weather_data(data):
    """Transforme les données JSON en DataFrame exploitable."""
    records = []

    for record in data:
        date_time = record.get("date", "")
        if not date_time:
            continue

        records.append({
            "Date": date_time.split("T")[0],
            "Température min (°C)": record.get("tn", None),
            "Température max (°C)": record.get("tx", None),
            "Humidité (%)": record.get("u", None),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    
    return df.groupby("Date").agg({
        "Température min (°C)": "min",
        "Température max (°C)": "max",
        "Humidité (%)": "mean"
    }).reset_index()

# ---- CALCUL GROWING DEGREE DAYS (GDD) ----
def calculate_gdd(df, tbase=10):
    """Calcule les Growing Degree Days (GDD)."""
    df["GDD"] = ((df["Température min (°C)"] + df["Température max (°C)"]) / 2) - tbase
    df["GDD"] = df["GDD"].apply(lambda x: max(0, x))  # Pas de valeurs négatives
    df["GDD cumulés"] = df["GDD"].cumsum()
    return df

# ---- SAUVEGARDE DES DONNEES ----
def save_data(df, station, year, month, format="csv"):
    data_dir = create_data_directory()
    file_path = data_dir / f"weather_{station}_{year}_{month}.{format}"

    if format == "csv":
        df.to_csv(file_path, index=False, sep=";", encoding="utf-8")
    elif format == "json":
        df.to_json(file_path, orient="records", indent=4, force_ascii=False)

    return file_path

# ---- GENERATION DU PDF ----

def generate_pdf(df, station, year, month):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"Rapport météo - {station} ({month}/{year})", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "", 12)
    for index, row in df.iterrows():
        pdf.cell(200, 10, f"{row['Date']} - Temp Min: {row['Température min (°C)']}°C, Temp Max: {row['Température max (°C)']}°C, Humidité: {row['Humidité (%)']}%", ln=True)
    
    file_path = f"data/weather_{station}_{year}_{month}.pdf"
    pdf.output(file_path)

    # Vérifier si le fichier a bien été créé
    if not os.path.exists(file_path):
        print(f" Erreur : Le fichier PDF {file_path} n'a pas été généré !")
        return None  # Retourne None si le fichier n'existe pas

    print(f" PDF généré avec succès : {file_path}")
    return file_path

# ---- ROUTES FLASK ----
uploaded_data = [] 

@app.route("/", methods=["GET", "POST"])

def index():
    global uploaded_data  # Accès aux données uploadées

    if request.method == "POST":
        station = request.form["station"].upper()
        year = int(request.form["year"])
        month = int(request.form["month"])

        data = get_monthly_weather_data(station, year, month)
        if not data:
            return render_template("index.html", error="Aucune donnée trouvée.")

        df = process_weather_data(data)
        
        if df.empty:
            return render_template("index.html", error="Aucune donnée exploitable.")

        df = calculate_gdd(df)

        save_data(df, station, year, month, "csv")
        save_data(df, station, year, month, "json")

        return render_template("index.html", data=df.to_dict(orient="records"), station=station, year=year, month=month)

    # Vérifie si on a des données uploadées
    if uploaded_data:
        return render_template("index.html", data=uploaded_data)

    return render_template("index.html")

@app.route("/download/<file_type>/<station>/<year>/<month>")
def download(file_type, station, year, month):
    file_path = f"data/weather_{station}_{year}_{month}.{file_type}"
    return send_file(file_path, as_attachment=True)


UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Création du dossier si non existant
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier sélectionné."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Fichier invalide."}), 400

    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["csv", "json"]:
        return jsonify({"error": "Format non supporté. Veuillez uploader un fichier CSV ou JSON."}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    try:
        if file_ext == "csv":
            df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")  # Modifier delimiter si besoin
        else:
            df = pd.read_json(file_path)

        #  Afficher les colonnes existantes pour debug
        print("Colonnes du fichier uploadé :", df.columns.tolist())

        #  **Correspondance des colonnes entre ton fichier et celles attendues**
        column_mapping = {
            "date": "Date",
            "tn12": "Température min (°C)",  # Vérifier que 'tn12' correspond bien à la temp min
            "tx12": "Température max (°C)",  # Vérifier que 'tx12' correspond bien à la temp max
            "u": "Humidité (%)"  # Vérifier que 'u' correspond bien à l'humidité
        }

        #  Renommer les colonnes si elles existent dans le fichier
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        #  Vérification des colonnes après renommage
        required_columns = {"Date", "Température min (°C)", "Température max (°C)", "Humidité (%)"}
        file_columns = set(df.columns)

        if not required_columns.issubset(file_columns):
            return jsonify({"error": f"Colonnes manquantes après renommage ! Fichier : {file_columns}, Attendu : {required_columns}"}), 400

        # Stocker les données pour affichage
        global uploaded_data
        uploaded_data = df.to_dict(orient="records")

        return jsonify({"success": "Fichier chargé avec succès.", "data": uploaded_data})

    except Exception as e:
        return jsonify({"error": f"Erreur lors de la lecture du fichier : {str(e)}"}), 500


# ---- LANCEMENT FLASK ----
if __name__ == "__main__":
    app.run(debug=True)
