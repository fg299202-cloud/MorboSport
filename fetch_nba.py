#!/usr/bin/env python3
"""
fetch_nba.py · Morbo · Fernando

Descarga partidos NBA del dia (si los hay) desde balldontlie.io y los anade
al archivo data/morbo-today.json para que Gemini los considere en la seleccion.

REQUISITOS:
  1. Cuenta gratis en https://app.balldontlie.io
  2. API key copiada en .env como:  BALLDONTLIE_API_KEY=tu_key

Si no hay BALLDONTLIE_API_KEY en .env, el script no hace nada (silencioso).
Esto permite que el proyecto funcione aunque NBA no este configurado.

USO:
  py fetch_nba.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

API_KEY = os.environ.get("BALLDONTLIE_API_KEY")
if not API_KEY:
    print("[NBA] BALLDONTLIE_API_KEY no configurada. Salto sin error.")
    print("[NBA] Si quieres activar NBA, registrate en https://app.balldontlie.io")
    print("[NBA] y anade tu key al .env como BALLDONTLIE_API_KEY=...")
    sys.exit(0)

try:
    import requests
except ImportError:
    print("Falta el paquete 'requests'. Instalalo con: py -m pip install requests")
    sys.exit(1)

DATA_DIR = Path(__file__).parent / "morbo" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TARGET_FILE = DATA_DIR / "morbo-today.json"

BASE_URL = "https://api.balldontlie.io/nba/v1"
HEADERS = {"Authorization": API_KEY}


def fetch_games_for_date(date_ymd: str) -> list:
    """Llama al endpoint /games filtrado por fecha (YYYY-MM-DD)."""
    url = f"{BASE_URL}/games"
    params = {"dates[]": date_ymd, "per_page": 50}
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 401:
        print("[NBA] Error 401: API key invalida. Comprueba tu .env")
        sys.exit(1)
    if r.status_code == 429:
        print("[NBA] Error 429: limite de peticiones alcanzado.")
        sys.exit(1)
    r.raise_for_status()
    return r.json().get("data", [])


def normalize_game(g: dict) -> dict:
    """Convierte un partido NBA al formato Morbo."""
    # status puede ser "Final", "1Q 5:23", "Scheduled", "8:00 PM ET", etc.
    # Para hora: balldontlie no siempre da hora UTC estructurada, asi que
    # usamos el campo status si parece hora.
    status = g.get("status", "")
    # Para simplificar: usamos hora de inicio del partido en horario ES
    # NBA empieza tipicamente entre las 23:00 y 04:00 hora ES (madrugada).
    # balldontlie no expone hora UTC fiable en free tier, asi que ponemos
    # "Noche" como placeholder y dejamos a Gemini que busque la hora exacta.
    hora = "Noche"

    home = g.get("home_team", {}).get("full_name", "Home")
    away = g.get("visitor_team", {}).get("full_name", "Away")

    season = g.get("season")
    postseason = g.get("postseason", False)
    competition = "NBA Playoffs" if postseason else f"NBA {season}"

    return {
        "id": f"nba-{g['id']}",
        "sport": "NBA",
        "competition": competition,
        "date_iso": f"{g.get('date','')}T00:00:00",
        "time": hora,
        "date_ymd": g.get("date", "")[:10],
        "title": home,
        "vs": away,
        "status": status,
        "intensity": None,
        "tags": [],
        "reason": None,
        "_meta": {
            "source": "balldontlie",
            "postseason": postseason,
            "home_id": g.get("home_team", {}).get("id"),
            "away_id": g.get("visitor_team", {}).get("id"),
        },
    }


def main():
    # Calculamos "hoy" en hora local ES.
    # NBA juega tarde-noche US, asi que un partido del "21 mayo NBA" se
    # juega de madrugada el 22 hora ES. Por eso miramos hoy y ayer.
    today_utc = datetime.now(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)

    print(f"[NBA] Pidiendo partidos {yesterday_utc} y {today_utc}...")
    all_games = []
    for d in [yesterday_utc, today_utc]:
        try:
            games = fetch_games_for_date(d.strftime("%Y-%m-%d"))
            all_games.extend(games)
        except Exception as e:
            print(f"[NBA] Aviso al pedir {d}: {e}")

    print(f"[NBA] Total partidos recibidos: {len(all_games)}")

    if not all_games:
        print("[NBA] Sin partidos hoy. NBA fuera de temporada o sin actividad.")
        return

    normalized = [normalize_game(g) for g in all_games]

    # Filtramos: solo nos quedamos con los que aun no han terminado (status != "Final")
    # y los programados para hoy o esta noche.
    upcoming = [g for g in normalized if g.get("status") != "Final"]
    print(f"[NBA] Partidos no terminados (proximos / en juego): {len(upcoming)}")

    if not upcoming:
        print("[NBA] Todos los partidos ya han terminado. No anadimos NBA hoy.")
        return

    # Anadir al morbo-today.json existente
    if TARGET_FILE.exists():
        data = json.loads(TARGET_FILE.read_text())
    else:
        data = {"date": today_utc.strftime("%Y-%m-%d"), "matches_today": [], "matches_week": []}

    existing = data.get("matches_today", [])
    # Quitar entradas NBA previas (idempotente: si se ejecuta dos veces no duplica)
    existing = [m for m in existing if not m.get("id", "").startswith("nba-")]
    existing.extend(upcoming)
    data["matches_today"] = existing
    data["nba_added_at"] = datetime.now().isoformat()

    TARGET_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[NBA] {len(upcoming)} partidos anadidos a morbo-today.json")
    for g in upcoming[:10]:
        print(f"  · {g['title']} vs {g['vs']} ({g['status']})")


if __name__ == "__main__":
    main()
