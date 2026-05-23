@echo off
REM ========================================
REM   MORBO - Subir cambios a GitHub
REM ========================================
REM   Doble clic para enviar el morbo del dia
REM   a GitHub. Netlify redesplegara solo.
REM ========================================

cd /d "%~dp0"

echo.
echo ============================================
echo   MORBO - Subiendo a GitHub
echo ============================================
echo.

REM Anadir todos los cambios
git add .

REM Hacer commit con mensaje y fecha
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do (
    set FECHA=%%a-%%b-%%c
)
git commit -m "Morbo del dia %FECHA%"

REM Si no habia cambios, git commit falla, ignoramos
if errorlevel 1 (
    echo.
    echo No hay cambios nuevos para subir.
    pause
    exit /b 0
)

REM Subir a GitHub
echo.
echo Subiendo a GitHub...
git push

if errorlevel 1 (
    echo.
    echo ERROR al subir a GitHub.
    echo Comprueba tu conexion o tus credenciales.
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
