@echo off
setlocal EnableDelayedExpansion
REM =====================================================
REM 5_LANZAR_FINAL.BAT - Ejecutar JMComander
REM =====================================================
REM Este script lanza el ejecutable JMComander.exe.
REM Busca el ejecutable en dist/JMComander/ y lo ejecuta.
REM 
REM Que hace:
REM   - Localiza JMComander.exe
REM   - Lo ejecuta desde el directorio correcto
REM 
REM Uso: Para probar la aplicacion rapidamente
REM =====================================================

echo ====================================
echo JMComander - Launcher FINAL
echo ====================================
echo.
echo IMPORTANTE: NO copies la carpeta _internal manualmente
echo Deja que PyInstaller la maneje.
echo.

cd /d "%~dp0.."

set "EXE_PATH=dist\JMComander\JMComander.exe"

if not exist "%EXE_PATH%" (
  echo [ERROR] Ejecutable NO existe
  echo Por favor ejecuta primero: python -m PyInstaller JMComander.spec --noconfirm --clean
  pause
  exit /b 1
)

echo Ejecutable encontrado: %EXE_PATH%
echo.
echo Directorio actual: %CD%
echo.
echo Presiona ENTER para iniciar JMComander...
echo.
echo NOTA: La aplicacion se ejecutara desde este directorio.
echo El ejecutable usara las dependencias que empaqueto PyInstaller.
echo.
pause >nul

echo Iniciando JMComander...
echo.

cd dist\JMComander
start "" "JMComander" "%EXE_PATH%"

echo.
echo ====================================
echo JMComander iniciado
echo ====================================
echo.
echo Si la aplicacion se cierra inmediatamente, puede haber:
echo 1. Un error de PySide6.QtGui (ver ventana de comandos)
echo 2. Un error en la inicializacion de la aplicacion
echo 3. Un problema con las dependencias de Qt6
echo.
echo Presiona ENTER para cerrar esta ventana...
pause >nul