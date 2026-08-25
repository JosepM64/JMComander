@echo off
setlocal EnableDelayedExpansion
REM =====================================================
REM 6_CREAR_DISTRIBUCION.BAT - Crear ZIP para distribuir
REM =====================================================
REM Este script crea un archivo ZIP listo para distribuir a usuarios.
REM El ZIP incluye todo lo necesario: ejecutable + DLLs + plugins.
REM 
REM Que hace:
REM   1. Verifica que el build existe y es valido
REM   2. Crea un ZIP en la carpeta releases/
REM   3. Incluye fecha en el nombre del archivo
REM   4. Muestra instrucciones para el usuario final
REM 
REM Uso: Ejecutar cuando quieras distribuir la aplicacion
REM =====================================================

echo ====================================
echo JMComander - Crear Distribucion ZIP
echo ====================================
echo.
echo Este script crea un paquete ZIP listo para distribuir.
echo Requisitos:
echo   - JMComander.exe debe existir en dist\JMComander\
echo   - Las DLLs deben estar en _internal\
echo.
echo Presiona ENTER para continuar...
pause >nul

cd /d "%~dp0.."

REM Verificar que el ejecutable existe
set "SOURCE_DIR=dist\JMComander"
set "EXE_PATH=%SOURCE_DIR%\JMComander.exe"

if not exist "%EXE_PATH%" (
  echo.
  echo [ERROR] Ejecutable NO encontrado: %EXE_PATH%
  echo.
  echo Por favor ejecuta primero:
  echo   build.bat
  echo   o
  echo   scripts\1_build_principal.bat
  echo.
  pause
  exit /b 1
)

echo [OK] Ejecutable encontrado: %EXE_PATH%
echo.

REM Verificar DLLs esenciales
set "INTERNAL_DIR=%SOURCE_DIR%\_internal"
set ESSENTIAL_DLLS=Qt6Core.dll Qt6Gui.dll Qt6Widgets.dll Qt6Svg.dll Qt6Network.dll
set ALL_FOUND=1

echo Verificando DLLs esenciales en _internal...
for %%D in (%ESSENTIAL_DLLS%) do (
  if exist "%INTERNAL_DIR%\%%D" (
    echo   [OK] %%D
  ) else (
    echo   [MISSING] %%D
    set ALL_FOUND=0
  )
)

if %ALL_FOUND% equ 0 (
  echo.
  echo [WARNING] Faltan algunas DLLs esenciales.
  echo Ejecutando 3_copy_qt_dlls.bat para corregir...
  call scripts\3_copy_qt_dlls.bat
  echo.
)

REM Crear directorio de releases si no existe
set "RELEASES_DIR=releases"
if not exist "%RELEASES_DIR%" (
  mkdir "%RELEASES_DIR%"
  echo [OK] Directorio releases creado
)

REM Generar nombre de archivo con version y fecha
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (
  set FECHA=%%c%%a%%b
)
set "ZIP_NAME=JMComander_v1.0_%FECHA%.zip"
set "ZIP_PATH=%RELEASES_DIR%\%ZIP_NAME%"

echo.
echo ====================================
echo Creando archivo ZIP...
echo ====================================
echo.
echo Origen: %SOURCE_DIR%\
echo Destino: %ZIP_PATH%
echo.

REM Eliminar ZIP anterior si existe
if exist "%ZIP_PATH%" (
  del /q "%ZIP_PATH%"
  echo [OK] ZIP anterior eliminado
)

REM Crear ZIP usando PowerShell
powershell -Command "Compress-Archive -Path '%SOURCE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"

if %ERRORLEVEL% neq 0 (
  echo.
  echo [ERROR] Fallo al crear ZIP
  echo Codigo de error: %ERRORLEVEL%
  pause
  exit /b 1
)

echo.
echo ====================================
echo [OK] ZIP creado exitosamente!
echo ====================================
echo.
echo Archivo: %ZIP_PATH%
echo.
echo Contenido del ZIP:
echo   - JMComander.exe
echo   - _internal\ (DLLs y dependencias)
echo   - [Otros archivos del build]
echo.
echo ====================================
echo Instrucciones para el usuario final:
echo ====================================
echo.
echo 1. Descomprimir el ZIP en cualquier carpeta
echo 2. Ejecutar JMComander.exe
echo 3. No requiere instalacion ni DLLs adicionales
echo.
echo El ZIP esta listo para distribuir!
echo.
echo Ubicacion: %CD%\%ZIP_PATH%
echo.

REM Mostrar tama?o del archivo
for %%F in ("%ZIP_PATH%") do (
  set TAMANO=%%~zF
  echo Tama?o: !TAMANO! bytes
echo.
)

echo Presiona ENTER para abrir la carpeta releases...
pause >nul

start "" "%RELEASES_DIR%"

echo.
echo Presiona ENTER para cerrar...
pause >nul
