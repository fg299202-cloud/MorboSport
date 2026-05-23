@echo off
REM ========================================
REM   MORBO - Subir cambios a GitHub
REM ========================================
REM   Doble clic para enviar tus cambios.
REM   Sincroniza primero los del bot diario
REM   para evitar conflictos.
REM ========================================

cd /d "%~dp0"

echo.
echo ============================================
echo   MORBO - Subiendo a GitHub
echo ============================================
echo.

REM Paso 1: Si hay cambios locales en los JSON del bot,
REM descartarlos (el bot diario es la fuente de verdad)
echo [1/4] Limpiando posibles conflictos con el bot...
git checkout -- morbo/data/morbo-today.json 2>nul
git checkout -- morbo/data/standings.json 2>nul

REM Paso 2: Anadir todos los cambios pendientes
echo [2/4] Preparando cambios...
git add .

REM Paso 3: Hacer commit (si hay algo que commitear)
echo [3/4] Guardando cambios...
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do (
    set FECHA=%%a-%%b-%%c
)
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Cambios manuales %FECHA%"
) else (
    echo   Sin cambios nuevos para commitear.
)

REM Paso 4: Pull primero (por si el bot ha trabajado)
REM y luego push. El --no-edit evita que se abra el editor.
echo [4/4] Sincronizando con GitHub...
git pull --no-edit --rebase=false
if errorlevel 1 (
    echo.
    echo ATENCION: hubo un conflicto al hacer pull.
    echo Avisa a Fernando antes de continuar.
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo.
    echo ERROR al subir a GitHub.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LISTO! Cambios enviados.
echo   Netlify redesplegara en ~30 segundos.
echo ============================================
echo.
echo Tu app: https://morbosport.netlify.app
echo.
pause
