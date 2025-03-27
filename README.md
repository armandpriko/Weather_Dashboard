#  Weather Dashboard

**Weather Dashboard** est une application web développée avec **Flask** permettant d'explorer et de visualiser les données météorologiques historiques issues de l’API OpenDataSoft (données SYNOP). L'utilisateur peut effectuer des recherches mensuelles ou journalières, afficher des graphiques interactifs, et exporter les résultats en CSV, JSON ou PDF.

---

##  Fonctionnalités principales

- 🔍 Rechercher des données météo :
  - **Mensuelles** (par station, année, mois)
  - **Journalières** (par station et date spécifique)
- 📊 Affichage graphique :
  - GDD cumulés (mensuel)
  - Température & humidité heure par heure (journalier)
- 📁 Export des résultats :
  - CSV
  - JSON
  - PDF multi-pages avec graphique intégré
- ⬆️ Import d’un fichier CSV/JSON externe
- ⚙️ Déploiement possible sur Render, Railway, Heroku ou Raspberry Pi

---

## 🖼️ Captures d’écran

| Page d'analyse mensuelle | Page d'analyse journalière |
|--------------------------|----------------------------|
| ![Monthly Screenshot](static/demo_monthly.png) | ![Daily Screenshot](static/demo_daily.png) |

---

Application déployée sur Render.

---

## Partie Client serveur expliquée et ajoutée à la suite.

Pour cette partie , j’ai monté un Raspberry pi avec un DHT11 pour la collecte des donnés sur des intervalles de 3h à partir de 00h00 (donc 8 prises par jour).





## 🚀 Installation locale

### 1. Cloner le dépôt

```bash
git clone https://github.com/armandpriko/Weather_Dashboard.git
cd Weather_Dashboard```

