from flask import Flask, render_template, request, send_file
import pandas as pd
import requests
import os
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

def create_data_directory():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_daily_weather_data(station, date):
    base_url = "https://data.opendatasoft.com/api/explore/v2.1/catalog/datasets/donnees-synop-essentielles-omm@public/records"
    params = {
        "limit": 1000,
        "refine.nom": station,
        "where": f"date >= '{date}T00:00:00Z' AND date <= '{date}T23:59:59Z'",
        "sort": "date"
    }
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except:
        return []

def process_weather_data(data):
    records = []
    for record in data:
        date_time = record.get("date", "")
        if not date_time:
            continue
        records.append({
            "Heure": date_time.split("T")[1][:5],
            "Température (°C)": round(record.get("tc", 0), 1) if record.get("tc") is not None else None,
            "Humidité (%)": record.get("u")
        })
    df = pd.DataFrame(records)
    df["Heure"] = pd.to_datetime(df["Heure"], format="%H:%M", errors="coerce").dt.strftime("%H:%M")
    df.dropna(subset=["Température (°C)", "Humidité (%)"], inplace=True)
    df.sort_values("Heure", inplace=True)
    return df

@app.route("/daily", methods=["GET", "POST"])
def daily():
    if request.method == "POST":
        station = request.form["station"].upper()
        date = request.form["date"]
        raw_data = get_daily_weather_data(station, date)
        if not raw_data:
            return render_template("daily.html", error="Aucune donnée trouvée.")
        df = process_weather_data(raw_data)
        if df.empty:
            return render_template("daily.html", error="Aucune donnée exploitable.")
        df_html = df.to_dict(orient="records")
        return render_template("daily.html", data=df_html, station=station, date=date)
    return render_template("daily.html")

if __name__ == "__main__":
    app.run(debug=True)
