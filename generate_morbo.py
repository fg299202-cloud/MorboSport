#!/usr/bin/env python3
"""
generate_morbo.py · Morbo · Fernando

Lee los partidos del día (data/morbo-today.json) y las clasificaciones
(data/standings.json), llama a Gemini 2.5 Flash con Google Search activado
para que tenga contexto fresco (noticias del día), y rellena cada partido
con: intensity, tags y reason.

Gemini busca por su cuenta en Google noticias deportivas frescas, así que
captura el morbo real: despedidas, fichajes, polemicas, lesiones,
contexto narrativo que ninguna API de fixtures puede dar.

USO:
  py generate_morbo.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: falta GEMINI_API_KEY.")
    print("Anade al archivo .env la linea:")
    print("  GEMINI_API_KEY=tu_key_aqui")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Falta el paquete 'requests'. Instalalo con: py -m pip install requests")
    sys.exit(1)

DATA_DIR = Path(__file__).parent / "morbo" / "data"
INPUT_FILE = DATA_DIR / "morbo-today.json"
STANDINGS_FILE = DATA_DIR / "standings.json"
PATTERNS_FILE = DATA_DIR / "patterns.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"

DEFAULT_PATTERNS = [
    "Derbi clasico (Madrid-Barca, Sevilla-Betis, Atleti-Madrid, Athletic-Real Sociedad, Espanyol-Barca).",
    "Dos equipos en zona de descenso enfrentandose en las ultimas 8 jornadas.",
    "Top 3 de la tabla enfrentandose en las ultimas 10 jornadas.",
    "Equipos peleando por la Champions (puesto 4-6) en cara a cara directo.",
    "Final o vuelta de eliminatoria con resultado ajustado.",
    "Ultima carrera del mundial de F1/MotoGP con titulo aun en juego.",
    "GP en circuito iconico: Monaco, Spa, Silverstone, Monza, Jerez, Mugello.",
    "GP de casa de un piloto lider o espanol.",
    "Revancha de una final, eliminatoria o carrera reciente con polemica.",
    "Ex-jugador volviendo a su antiguo club, sobre todo si salio en mal tono.",
    "Entrenador recien destituido o estrenandose en banquillo importante.",
    "Record goleador, racha de imbatibilidad o partidos consecutivos en juego.",
    "Ultimo partido oficial de un jugador legendario antes de retirarse o cambiar de equipo.",
]


def load_patterns():
    """Carga patrones del usuario. Acepta dos formatos:
       - Lista de strings: ["regla 1", "regla 2"]   (formato exportado por la PWA)
       - Lista de objetos: [{"text": "regla 1"}, ...]
    """
    user_patterns = []
    if PATTERNS_FILE.exists():
        try:
            raw = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str):
                        user_patterns.append(item.strip())
                    elif isinstance(item, dict) and item.get("text"):
                        user_patterns.append(item["text"].strip())
        except Exception as e:
            print(f"AVISO: no se pudo leer patterns.json ({e})")
    return DEFAULT_PATTERNS, user_patterns


def load_feedback():
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return json.loads(FEEDBACK_FILE.read_text())
    except Exception:
        return []


def load_standings():
    if not STANDINGS_FILE.exists():
        return {}
    try:
        return json.loads(STANDINGS_FILE.read_text())
    except Exception:
        return {}


def format_standings(standings):
    """Convierte el JSON de clasificaciones en texto compacto para el prompt."""
    if not standings:
        return "(no disponibles)"

    out_blocks = []
    for code, comp in standings.items():
        name = comp.get("name", code)
        season = comp.get("season", {})
        matchday = season.get("currentMatchday", "?")
        table = comp.get("table", [])

        lines = [f"=== {name} (jornada {matchday}) ==="]
        # Si hay grupos (Champions), agruparlos
        groups = {}
        for row in table:
            g = row.get("group") or "GENERAL"
            groups.setdefault(g, []).append(row)

        for g, rows in groups.items():
            if g != "GENERAL":
                lines.append(f"-- {g} --")
            for r in rows:
                pos = r.get("position")
                team = r.get("team")
                pts = r.get("points")
                pj = r.get("played")
                lines.append(f"  {pos:>2}. {team:<22s} {pts:>3} pts  ({pj} PJ)")
        out_blocks.append("\n".join(lines))

    return "\n\n".join(out_blocks)


def build_prompt(matches, standings, default_patterns, user_patterns, feedback):
    today = datetime.now().strftime("%A %d de %B de %Y")

    matches_lines = []
    for m in matches:
        comp_code = m.get("_meta", {}).get("competition_code", "")
        line = (f"- ID: {m['id']} | {m['time']} | {m['sport']} [{comp_code}] "
                f"({m.get('competition','')}) | {m['title']} vs {m['vs']}")
        matches_lines.append(line)

    patterns_text = "\n".join(f"- {p}" for p in default_patterns)
    user_text = "\n".join(f"- {p}" for p in user_patterns) if user_patterns else "(ninguno todavia)"

    feedback_text = ""
    if feedback:
        feedback_lines = []
        for f in feedback[-20:]:
            mark = "+" if f.get("feedback") == "up" else "-"
            note = f.get("note", "")
            entry = f"{mark} {f.get('event','')}"
            if note:
                entry += f" -- Leccion: {note}"
            feedback_lines.append(entry)
        feedback_text = "\n".join(feedback_lines)
    else:
        feedback_text = "(aun sin feedback)"

    standings_text = format_standings(standings)

    prompt = f"""Eres el editor jefe de "Morbo", una agenda diaria que selecciona los 3-5 momentos deportivos mas interesantes del dia para aficionados espanoles. Tu trabajo es elegir los partidos con mas historia, tension o significado real, y explicar EN UNA O DOS FRASES POTENTES por que importan HOY.

Hoy es {today}.

== PARTIDOS DEL DIA ==
{chr(10).join(matches_lines)}

== CLASIFICACIONES ACTUALES (datos REALES de la API oficial) ==
{standings_text}

== PATRONES DE MORBO BASE ==
{patterns_text}

== PATRONES PERSONALIZADOS DEL EDITOR ==
{user_text}

== LECCIONES APRENDIDAS DE FEEDBACK PREVIO ==
{feedback_text}

== INSTRUCCIONES CRITICAS ==
1. USA LA HERRAMIENTA DE BUSQUEDA DE GOOGLE para informarte del contexto fresco del dia:
   - Despedidas de jugadores (Modric, Lewandowski, etc.)
   - Fichajes anunciados
   - Polemicas o disputas recientes
   - Lesiones de ultima hora
   - Cualquier noticia de hoy o ayer que de morbo a un partido concreto
   Las clasificaciones de arriba son fiables, pero TODO el contexto narrativo lo tienes que buscar.

2. NO INVENTES. Si no encuentras un dato concreto sobre un partido, no lo digas. Prohibido escribir "podria jugarse el titulo", "probable revancha", "se rumorea que..." Solo afirma cosas que hayas verificado con la busqueda o que esten en las clasificaciones.

3. PROHIBIDO el lenguaje vacio: nada de "sera un buen partido", "promete emocion", "tension hasta el ultimo minuto", "encuentro vibrante". Eso no es morbo, es relleno.

4. Selecciona entre 3 y 5 partidos con verdadero morbo. NO rellenes por rellenar: si solo hay 3 con sustancia, devuelve 3. Mejor 3 buenos que 5 mediocres.

5. Para cada uno asigna:
   - intensity: 3 = imperdible, 2 = atractivo, 1 = curioso
   - tags: 1-3 etiquetas cortas (ej: "Descenso", "Derbi", "Despedida")
   - reason: 1-2 frases CONCRETAS y verificables. Menciona el dato exacto (posicion en tabla, jornadas que quedan, gol numero X, etc.) Tono editorial, periodistico.

6. RESPONDE SOLO CON JSON VALIDO, sin texto adicional, sin markdown, sin triple backtick. Formato exacto:

{{
  "selected": [
    {{
      "id": "fd-12345",
      "intensity": 3,
      "tags": ["Despedida", "LaLiga"],
      "reason": "Frase concreta y verificable."
    }}
  ]
}}
"""
    return prompt


def call_gemini_with_search(prompt):
    """Llama a Gemini 2.5 Flash con la herramienta google_search activada."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + API_KEY
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.6,
            # OJO: no podemos forzar responseMimeType=json cuando usamos tools.
            # Le pedimos JSON via prompt y lo parseamos despues.
        }
    }
    r = requests.post(url, json=payload, timeout=90)
    if r.status_code != 200:
        print(f"\nError HTTP {r.status_code}:")
        print(r.text[:600])
        sys.exit(1)
    data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)

        # Limpiar posibles ```json ... ```
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            if text.endswith("```"):
                text = text[:-3].strip()

        return json.loads(text), data
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"\nError parseando respuesta de Gemini: {e}")
        print("Respuesta cruda (primeros 2000 chars):")
        print(json.dumps(data, indent=2)[:2000])
        sys.exit(1)


def extract_search_queries(gemini_raw):
    """Si Gemini ha usado google_search, extrae las queries para mostrarlas."""
    try:
        grounding = gemini_raw["candidates"][0].get("groundingMetadata", {})
        queries = grounding.get("webSearchQueries", [])
        return queries
    except Exception:
        return []


def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: no encuentro {INPUT_FILE}")
        print("Ejecuta primero: py fetch_matches.py")
        sys.exit(1)

    data = json.loads(INPUT_FILE.read_text())
    matches_today = data.get("matches_today", [])

    if not matches_today:
        print("No hay partidos hoy. Nada que procesar.")
        return

    print(f"Partidos del dia: {len(matches_today)}")

    standings = load_standings()
    default_patterns, user_patterns = load_patterns()
    feedback = load_feedback()
    print(f"Clasificaciones: {len(standings)} competiciones")
    print(f"Patrones base: {len(default_patterns)}  ·  Patrones del usuario: {len(user_patterns)}  ·  Feedback acumulado: {len(feedback)}")

    prompt = build_prompt(matches_today, standings, default_patterns, user_patterns, feedback)

    print("\nLlamando a Gemini 2.5 Flash con busqueda de Google...")
    response, raw = call_gemini_with_search(prompt)

    queries = extract_search_queries(raw)
    if queries:
        print(f"\nBusquedas que Gemini hizo en Google:")
        for q in queries:
            print(f"  > {q}")

    selected = response.get("selected", [])
    if not selected:
        print("\nGemini no ha seleccionado ningun partido.")
        return

    print(f"\n-> Gemini ha seleccionado {len(selected)} partidos con morbo:\n")

    selected_by_id = {s["id"]: s for s in selected}
    enriched_matches = []
    for m in matches_today:
        if m["id"] in selected_by_id:
            s = selected_by_id[m["id"]]
            m["intensity"] = s.get("intensity", 1)
            m["tags"] = s.get("tags", [])
            m["reason"] = s.get("reason", "")
            enriched_matches.append(m)

    enriched_matches.sort(key=lambda m: (-m.get("intensity", 0), m["time"]))

    for m in enriched_matches:
        intensity_marker = "X" * m["intensity"]
        tags = " · ".join(m["tags"])
        print(f"  [{intensity_marker:3s}] {m['time']}  {m['title']} vs {m['vs']}  [{tags}]")
        print(f"        > {m['reason']}\n")

    data["matches_today"] = enriched_matches
    data["generated_morbo_at"] = datetime.now().isoformat()
    data["search_queries_used"] = queries
    INPUT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"OK Guardado en {INPUT_FILE.name}")


if __name__ == "__main__":
    main()
