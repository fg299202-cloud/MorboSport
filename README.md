# Morbo · Agenda deportiva diaria

PWA + script que cada día selecciona los partidos con más morbo del fútbol
español, Champions y Serie A, los enriquece con contexto fresco usando
Gemini + Google Search, y los muestra en una app instalable en el móvil.

---

## Estructura

```
MorboSport/
├── fetch_matches.py      → descarga partidos y clasificaciones reales
├── generate_morbo.py     → Gemini selecciona los 3-5 mejores y los redacta
├── .env                  → tus claves (lo creas tú, ver abajo)
├── .env.example          → plantilla de referencia
├── README.md             → este archivo
└── morbo/                → la PWA
    ├── index.html
    ├── manifest.json
    ├── sw.js
    └── data/             → se crea sola al ejecutar los scripts
        ├── morbo-today.json
        └── standings.json
```

---

## Configuración inicial (una sola vez)

### 1. Crea tu archivo `.env`

Copia `.env.example` y renómbralo a `.env`. Edítalo y pega tus dos claves:

```
FOOTBALL_API_KEY=tu_token_de_football_data_org
GEMINI_API_KEY=tu_key_de_ai_studio
```

Cómo conseguir cada una:
- **football-data.org** → https://www.football-data.org/client/register (gratis, te llega por email)
- **Gemini** → https://aistudio.google.com/apikey (gratis, botón "Create API key")

### 2. Instala el paquete `requests` (solo la primera vez)

Abre PowerShell en la carpeta `MorboSport` y ejecuta:

```powershell
py -m pip install requests
```

---

## Uso diario

Abre PowerShell en la carpeta `MorboSport` y ejecuta dos comandos:

```powershell
py fetch_matches.py
py generate_morbo.py
```

El primero baja los partidos y clasificaciones. El segundo llama a Gemini
con Google Search activado para que detecte el morbo real del día.

Después, abre la PWA:
- Haz **doble clic en `morbo/index.html`** y se abrirá en tu navegador.
- O sube la carpeta `morbo/` a Netlify Drop para tenerla online (te dan URL).

---

## Códigos de acceso

La PWA pide un código al entrar. Códigos válidos en esta versión:

- `MORBO-FOUNDER` (para ti)
- `MORBO-A7K3` (demo)
- `MORBO-DEMO`

Cuando empieces a cobrar, cada usuario que pague tendrá su propio código.
Los gestionas editando la lista `VALID_CODES` en `morbo/index.html` (la
buscas con Ctrl+F, está cerca del principio del `<script>`).

---

## Solución de problemas

**"El término 'py' no se reconoce"** → tienes que reinstalar Python marcando
"Add Python to PATH" en el instalador.

**"FOOTBALL_API_KEY no está definido"** → tu `.env` no está en la misma
carpeta que los scripts, o está mal nombrado (no debe ser `.env.txt`).

**Gemini no encuentra noticias** → comprueba tu cuota en https://aistudio.google.com
(1500 búsquedas/día son gratis, sobra para uso personal).

**Errores 403 con football-data.org** → tu token es incorrecto o caducó.
Vuelve a https://www.football-data.org/client/register y regenera.

---

## Próximos pasos

- [ ] Calendario de F1 y MotoGP (JSON estático)
- [ ] GitHub Actions con cron diario automático
- [ ] Notificación push matinal
- [ ] Sistema de pago real con Stripe
