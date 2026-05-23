@echo off
REM ========================================
REM   MORBO - Actualizar morbo del dia
REM ========================================

cd /d "%~dp0"

echo.
echo ============================================
echo   MORBO - Generando el morbo del dia
echo ============================================
echo.

echo [1/3] Descargando partidos y clasificaciones...
echo --------------------------------------------
py fetch_matches.py
if errorlevel 1 (
    echo.
    echo ERROR en fetch_matches.py
    pause
    exit /b 1
)
echo.

echo [2/3] Anadiendo partidos NBA (si esta configurado)...
echo --------------------------------------------
py fetch_nba.py
echo.

echo [3/3] Generando morbo con Gemini...
echo --------------------------------------------
py generate_morbo.py
if errorlevel 1 (
    echo.
    echo ERROR en generate_morbo.py
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LISTO! Morbo del dia generado.
echo ============================================
echo.
pause
