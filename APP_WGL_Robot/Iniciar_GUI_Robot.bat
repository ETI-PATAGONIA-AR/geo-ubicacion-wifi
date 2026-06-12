@echo off
title App WGL - ETI Patagonia - prof.martintorres@educ.ar
color 0B

:: -------------------------------------------------------------------
:: Este .bat arranca la GUI del Robot automáticamente.
:: Funciona desde cualquier carpeta donde pongas la aplicación.
:: -------------------------------------------------------------------

:: Vamos a la carpeta donde está este .bat
cd /d "%~dp0"

echo =============================================
echo   WGL - ETI Patagonia - Iniciando App de Control
echo =============================================
echo.

:: Verificar que Python esté instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo Para instalar Python:
    echo   1. Andá a https://www.python.org/downloads/
    echo   2. Descargá la version mas reciente
    echo   3. IMPORTANTE: tildá "Add Python to PATH" durante la instalacion
    echo.
    pause
    exit /b
)

echo [OK] Python detectado

:: Verificar/instalar dependencias
echo.
echo [..] Verificando dependencias...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo.
    echo [ADVERTENCIA] No se pudieron instalar las dependencias.
    echo Probá ejecutar manualmente: pip install -r requirements.txt
    echo.
    pause
    exit /b
)
echo [OK] Dependencias listas

:: Verificar que el archivo gui_robot.py exista
if not exist "gui_robot.py" (
    echo.
    echo [ERROR] No se encuentra el archivo gui_robot.py
    echo.
    pause
    exit /b
)

:: Arrancar la GUI
echo.
echo [OK] Iniciando GUI...
echo.
echo   IMPORTANTE: Antes de usar la GUI asegurate de:
echo     1. Los 4 nodos esten energizados y emitiendo
echo     2. El robot ESP32 este encendido
echo     3. Tu laptop este conectada a la red "ROBOT_NET"
echo.
echo   Si es la primera vez: conectate a ROBOT_NET (pass: robot1234)
echo.  Si la GUI se cerro, enviame un correo a prof.martintorres@educ.ar y muestrame mensaje de error
echo.
echo =============================================
echo.

python gui_robot.py

:: Si la GUI se cerró, envíame un correo a prof.martintorres@educ.ar y muestrame mensaje de error
echo.
echo =============================================
echo   GUI cerrada.
echo =============================================
echo.
pause
