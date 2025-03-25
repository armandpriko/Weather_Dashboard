import requests
import json
import calendar
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
from datetime import datetime
from fpdf import FPDF
from pathlib import Path
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------ UTILS ------------------
def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir


# ------------------ DAILY FROM software_one ------------------
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


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


# ------------------ DAILY ROUTES ------------------
@app.route("/daily", methods=["GET", "POST"])
def daily():
    if request.method == "POST":
        station = request.form["station"].upper()
        date = request.form["date"]

        if not is_valid_date(date):
            return render_template("daily.html", error="Date invalide (YYYY-MM-DD)")

        data = get_weather_data(station, date)
        if not data:
            return render_template("daily.html", error="Aucune donnée trouvée pour cette date.")

        df = process_weather_data(data)
        if df.empty:
            return render_template("daily.html", error="Aucune donnée exploitable.")

        return render_template("daily.html", data=df.to_dict(orient="records"), station=station, date=date)

    return render_template("daily.html")


# ------------------ REMAINING MONTHLY ROUTES ------------------

@app.route("/")
def home():
    return redirect(url_for("daily"))

if __name__ == "__main__":
    app.run(debug=True)
