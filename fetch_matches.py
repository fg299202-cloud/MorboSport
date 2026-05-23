#!/usr/bin/env python3
"""
fetch_matches.py · Morbo · Fernando

Llama a football-data.org y descarga los partidos del día y de los próximos 7
días para las competiciones suscritas en el plan gratis: LaLiga, Champions,
Premier, Bundesliga, Serie A, Ligue 1, Copa del Mundo, etc.

Genera dos archivos en data/:
  - matches-raw.json  → respuesta cruda de la API (debug)
  - morbo-today.json  → formato normalizado que entiende la PWA

USO LOCAL (en tu PC):
  1. pip install requests python-dotenv
  2. crea un archivo .env con:  FOOTBALL_API_KEY=tu_token_aqui
  3. python fetch_matches.py

USO EN GITHUB ACTIONS:
  La variable FOOTBALL_API_KEY se inyecta desde "Secrets" del repo.
  No hace falta .env.
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Falta el paquete 'requests'. Instálalo con: pip install requests")
    sys.exit(1)

# Cargar .env si existe (para uso local)
ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

API_KEY = os.environ.get("FOOTBALL_API_KEY")
if not API_KEY:
    print("ERROR: falta FOOTBALL_API_KEY.")
    print("Crea un archivo .env con: FOOTBALL_API_KEY=tu_token")
    print("O exporta la variable: export FOOTBALL_API_KEY=tu_token")
    sys.exit(1)

BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}

# Competiciones que nos interesan (códigos oficiales de la API)
# Free tier incluye: PD (LaLiga), CL (Champions), PL (Premier), BL1 (Bundesliga),
# SA (Serie A), FL1 (Ligue 1), CLI (Copa Libertadores), etc.
COMPETITIONS = {
    "PD": "LaLiga",
    "CL": "Champions",
    "PL": "Premier",
    "BL1": "Bundesliga",
    "SA": "Serie A",
}

OUT_DIR = Path(__file__).parent / "morbo" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_matches_for_date_range(date_from: str, date_to: str) -> dict:
    """Llama al endpoint /matches con filtro de fechas."""
    url = f"{BASE_URL}/matches"
    params = {
        "dateFrom": date_from,
        "dateTo": date_to,
        "competitions": ",".join(COMPETITIONS.keys()),
    }
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 403:
        print(f"Error 403: tu plan no cubre estas competiciones. {r.text[:200]}")
        sys.exit(1)
    if r.status_code == 429:
        print("Error 429: límite de peticiones alcanzado. Espera un minuto.")
        sys.exit(1)
    r.raise_for_status()
    return r.json()


def fetch_standings(competition_code: str) -> dict | None:
    """Descarga la clasificación actual de una competición.
    Devuelve None si la API no la sirve (ej. Champions en fase de grupos)."""
    url = f"{BASE_URL}/competitions/{competition_code}/standings"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def normalize_standings(raw: dict) -> list:
    """Extrae la clasificación TOTAL (no HOME/AWAY) en formato compacto."""
    if not raw:
        return []
    out = []
    for s in raw.get("standings", []):
        if s.get("type") != "TOTAL":
            continue
        # Si hay group (Champions), incluirlo. Liga normal no tiene grupo.
        group = s.get("group")
        for row in s.get("table", []):
            out.append({
                "position": row.get("position"),
                "team": row.get("team", {}).get("shortName") or row.get("team", {}).get("name"),
                "team_id": row.get("team", {}).get("id"),
                "played": row.get("playedGames"),
                "won": row.get("won"),
                "draw": row.get("draw"),
                "lost": row.get("lost"),
                "points": row.get("points"),
                "goal_diff": row.get("goalDifference"),
                "group": group,
            })
    return out


def normalize_match(m: dict) -> dict:
    """Convierte un partido crudo de la API al formato que usa la PWA."""
    utc_dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
    # Hora local de España (UTC+1 en invierno, +2 en verano)
    # Simplificación: usamos +2 entre marzo y octubre, +1 el resto
    month = utc_dt.month
    offset = 2 if 3 <= month <= 10 else 1
    local_dt = utc_dt + timedelta(hours=offset)

    comp_code = m.get("competition", {}).get("code", "")
    sport_label = COMPETITIONS.get(comp_code, m.get("competition", {}).get("name", ""))

    matchday = m.get("matchday")
    stage = m.get("stage", "")
    if comp_code == "CL" and stage and stage != "REGULAR_SEASON":
        comp_subtitle = stage.replace("_", " ").title()
    elif matchday:
        comp_subtitle = f"Jornada {matchday}"
    else:
        comp_subtitle = stage.replace("_", " ").title() if stage else ""

    return {
        "id": f"fd-{m['id']}",
        "sport": sport_label,
        "competition": comp_subtitle,
        "date_iso": local_dt.isoformat(),
        "time": local_dt.strftime("%H:%M"),
        "date_ymd": local_dt.strftime("%Y-%m-%d"),
        "title": m["homeTeam"]["shortName"] or m["homeTeam"]["name"],
        "vs": m["awayTeam"]["shortName"] or m["awayTeam"]["name"],
        "status": m.get("status"),
        # Estos los rellenará Gemini en el siguiente paso:
        "intensity": None,
        "tags": [],
        "reason": None,
        # Metadatos para que Gemini tenga contexto:
        "_meta": {
            "home_id": m["homeTeam"]["id"],
            "away_id": m["awayTeam"]["id"],
            "competition_code": comp_code,
            "matchday": matchday,
            "stage": stage,
        }
    }


def main():
    today = datetime.now(timezone.utc).date()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"Pidiendo partidos del {date_from} al {date_to}...")
    print(f"Competiciones: {', '.join(COMPETITIONS.values())}")

    raw = fetch_matches_for_date_range(date_from, date_to)

    matches_raw = raw.get("matches", [])
    print(f"\n  → {len(matches_raw)} partidos recibidos.")

    # Guardar respuesta cruda (debug)
    raw_file = OUT_DIR / "matches-raw.json"
    raw_file.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    print(f"  → matches-raw.json guardado ({raw_file.stat().st_size // 1024} KB)")

    # Normalizar
    normalized = [normalize_match(m) for m in matches_raw]

    # Filtrar solo los de HOY para el archivo principal
    today_local = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%d")
    today_matches = [m for m in normalized if m["date_ymd"] == today_local]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": today_local,
        "matches_today": today_matches,
        "matches_week": normalized,
    }

    out_file = OUT_DIR / "morbo-today.json"
    out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"  → morbo-today.json guardado ({out_file.stat().st_size // 1024} KB)")
    print(f"\nPartidos HOY ({today_local}): {len(today_matches)}")
    for m in today_matches[:15]:
        print(f"  · {m['time']}  {m['sport']:10s}  {m['title']} vs {m['vs']}")

    # Descargar clasificaciones SOLO de competiciones con partidos hoy
    print("\nDescargando clasificaciones...")
    comps_with_matches = set(m["_meta"]["competition_code"] for m in today_matches)
    if not comps_with_matches:
        # Si no hay nada hoy, descargamos LaLiga por defecto
        comps_with_matches = {"PD"}

    standings_out = {}
    for code in comps_with_matches:
        name = COMPETITIONS.get(code, code)
        print(f"  · {name} ({code})...", end=" ", flush=True)
        raw_standings = fetch_standings(code)
        if raw_standings:
            normalized_st = normalize_standings(raw_standings)
            standings_out[code] = {
                "name": name,
                "season": raw_standings.get("season", {}),
                "table": normalized_st,
            }
            print(f"{len(normalized_st)} equipos")
        else:
            print("no disponible")

    st_file = OUT_DIR / "standings.json"
    st_file.write_text(json.dumps(standings_out, indent=2, ensure_ascii=False))
    print(f"\n  → standings.json guardado ({st_file.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
