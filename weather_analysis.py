import requests
import json
import calendar
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Utilise le backend non-GUI adapté aux serveurs
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
from fpdf import FPDF
from pathlib import Path
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_monthly_weather_data(station, year, month):
    base_url = "https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/donnees-synop-essentielles-omm@public/exports/json"
    last_day = calendar.monthrange(year, month)[1]
    date_prefix = f"{year}-{month:02d}"

    params = {
        "refine.nom": station,
        "where": f"date >= '{date_prefix}-01T00:00:00Z' AND date <= '{date_prefix}-{last_day}T23:59:59Z'",
        "timezone": "UTC"
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f" Aucune donnée trouvée pour {station} en {date_prefix}.")
            return []
        return data

    except requests.RequestException as e:
        print(f" Erreur API : {e}")
        return []


def process_weather_data(data):
    records = []
    for record in data:
        date_time = record.get("date", "")
        if not date_time:
            continue

        records.append({
            "Date": date_time.split("T")[0],
            "Température min (°C)": record.get("tn12c"),
            "Température max (°C)": record.get("tx12c"),
            "Humidité (%)": record.get("u")
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df = df.groupby("Date").agg({
        "Température min (°C)": "min",
        "Température max (°C)": "max",
        "Humidité (%)": "mean"
    }).reset_index()

    return df


def calculate_gdd(df, tbase=10):
    df["GDD"] = ((df["Température min (°C)"] + df["Température max (°C)"]) / 2) - tbase
    df["GDD"] = df["GDD"].apply(lambda x: max(0, x))
    df["GDD cumulés"] = df["GDD"].cumsum()
    return df


def save_data(df, station, year, month, format="csv"):
    data_dir = create_data_directory()
    file_path = data_dir / f"weather_{station}_{year}_{month}.{format}"

    if format == "csv":
        df.to_csv(file_path, index=False, sep=";", encoding="utf-8")
    elif format == "json":
        df.to_json(file_path, orient="records", indent=4, force_ascii=False)

    return file_path


def generate_pdf(df, station, year, month):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1 : Texte
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, f"Rapport météo - {station} ({month}/{year})", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "", 12)
    for index, row in df.iterrows():
        line = f"{row['Date']} - Temp Min: {row['Température min (°C)']}°C, Temp Max: {row['Température max (°C)']}°C, Humidité: {row['Humidité (%)']}%"
        pdf.multi_cell(0, 10, line)

    # Page 2 : Graphique GDD
    plot_path = f"static/gdd_plot.png"
    if os.path.exists(plot_path):
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Graphique des GDD cumulés", ln=True, align="C")
        pdf.ln(5)
        pdf.image(plot_path, x=10, w=190)  

    file_path = f"data/weather_{station}_{year}_{month}.pdf"
    pdf.output(file_path)

    return file_path if os.path.exists(file_path) else None




def plot_gdd(df, station, year, month):
    if "GDD cumulés" not in df.columns:
        return

    
    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)

    plt.figure(figsize=(10, 5))
    plt.plot(df["Date"], df["GDD cumulés"], marker='o', color='green')
    plt.title(f"GDD cumulés - {station} ({month}/{year})")
    plt.xlabel("Date")
    plt.ylabel("GDD cumulés")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid()

    plot_path = static_dir / "gdd_plot.png"
    plt.savefig(plot_path)
    plt.close()



@app.route("/", methods=["GET", "POST"])
def index():
    global uploaded_data
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
        plot_gdd(df, station, year, month)
        return render_template("index.html", data=df.to_dict(orient="records"), station=station, year=year, month=month)
    return render_template("index.html")


@app.route("/download/<file_type>/<station>/<year>/<month>")
def download(file_type, station, year, month):
    if file_type == "pdf":
        # Recharge le CSV pour le PDF
        file_path_csv = f"data/weather_{station}_{year}_{month}.csv"
        if not os.path.exists(file_path_csv):
            return "CSV introuvable pour générer le PDF", 404
        df = pd.read_csv(file_path_csv, delimiter=";")
        file_path = generate_pdf(df, station, year, month)
    else:
        file_path = f"data/weather_{station}_{year}_{month}.{file_type}"

    if not os.path.exists(file_path):
        return "Fichier non trouvé", 404

    return send_file(file_path, as_attachment=True)



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
            df = pd.read_csv(file_path, delimiter=";", encoding="utf-8")
        else:
            df = pd.read_json(file_path)
        column_mapping = {
            "date": "Date",
            "tn12": "Température min (°C)",
            "tx12": "Température max (°C)",
            "u": "Humidité (%)"
        }
        df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)
        required_columns = {"Date", "Température min (°C)", "Température max (°C)", "Humidité (%)"}
        if not required_columns.issubset(set(df.columns)):
            return jsonify({"error": f"Colonnes manquantes après renommage. Présentes : {set(df.columns)}"}), 400
        global uploaded_data
        uploaded_data = df.to_dict(orient="records")
        return jsonify({"success": "Fichier chargé avec succès.", "data": uploaded_data})
    except Exception as e:
        return jsonify({"error": f"Erreur lors de la lecture du fichier : {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
