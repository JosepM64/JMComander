@echo off
REM =====================================================
REM BUILD.BAT - Build RAPIDO automatico con Anaconda
REM =====================================================
REM Este script hace un build rapido SIN PAUSAS.
REM Busca automaticamente Anaconda/Miniconda con "where conda"
REM 
REM Que hace:
REM   1. Busca Anaconda automaticamente
REM   2. Limpia builds anteriores (automatico)
REM   3. Compila con PyInstaller
REM   4. Copia DLLs automaticamente si faltan
REM 
REM Uso: Ejecutar y esperar a que termine (3-5 minutos)
REM =====================================================

echo ====================================
echo JMComander - Build Rapido (AUTOMATICO)
echo ====================================
echo.
echo This script will:
echo 1. Auto-detect Anaconda/Miniconda
echo 2. Clean previous build artifacts
echo 3. Build JMComander.exe with Python 3.13 (Conda)
echo 4. Copy any missing runtime DLLs
echo.

cd /d "%~dp0"

REM Carregar configuraci? (CONDA_ENV, EXE_NAME, etc.)
call "%~dp0scripts\CONFIG.bat"

REM Cerrar procesos que puedan interferir
echo Closing JMComander.exe processes...
taskkill /F /IM JMComander.exe >nul 2>&1
timeout /t 1 /nobreak >nul

REM Buscar conda automaticamente con where
set CONDA_PATH=
for /f "tokens=*" %%i in ('where.exe conda 2^>nul') do (
    set "CONDA_PATH=%%i"
    goto :found_conda
)

:found_conda
if "%CONDA_PATH%"=="" (
    echo ERROR: No se encontr? conda. Asegurate de tener Miniconda/Anaconda instalado y en el PATH.
    pause
    exit /b 1
)

REM Usar conda info --base para obtener la ruta base
for /f "tokens=*" %%b in ('"%CONDA_PATH%" info --base 2^>nul') do set "CONDA_BASE=%%b"
if not "%CONDA_BASE%"=="" (
    set "CONDA_PATH=%CONDA_BASE%\Scripts\conda.exe"
)
echo [OK] Conda detectado: %CONDA_PATH%

REM Limpiar directorios anteriores
echo Cleaning previous build...
if exist "dist" rd /s /q "dist" >nul 2>&1
if exist "build" rd /s /q "build" >nul 2>&1

REM Localitzar Python del entorn conda directament
echo.
echo Localitzant Python de l'entorn %CONDA_ENV%...
if "%CONDA_BASE%"=="" (
    for /f "tokens=*" %%b in ('"%CONDA_PATH%" info --base 2^>nul') do set "CONDA_BASE=%%b"
)
set "CONDA_PYTHON=%CONDA_BASE%\envs\%CONDA_ENV%\python.exe"
if not exist "%CONDA_PYTHON%" (
    echo ERROR: No es troba Python a %CONDA_PYTHON%
    pause
    exit /b 1
)
echo [OK] Python: %CONDA_PYTHON%

REM Verificar depend?ncies via pip directe
echo.
echo Verificant depend?ncies...
"%CONDA_PYTHON%" -m pip show PySide6 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Instal?lant depend?ncies via pip...
    "%CONDA_PYTHON%" -m pip install PySide6 PyInstaller pywin32-ctypes send2trash paramiko cryptography bcrypt rarfile py7zr mutagen numpy musicbrainzngs psutil pillow-heif pywin32 Pillow --quiet
)

REM Ejecutar build
echo.
echo Building JMComander with PyInstaller...
"%CONDA_PYTHON%" -m PyInstaller JMComander.spec --noconfirm --clean

if %ERRORLEVEL% equ 0 (
  echo.
  echo ====================================
  echo BUILD SUCCESSFUL!
  echo ====================================
  echo.
  echo Executable: dist\JMComander\JMComander.exe
  echo.

  REM Verificar si faltan DLLs y copiarlas
  echo Copying Qt6 DLLs from Conda environment...
  call scripts\3_copy_qt_dlls.bat

  echo.
  echo Build complete! You can now run JMComander.exe
  
  REM Limpiar carpeta build temporal
  echo Cleaning temporary build folder...
  if exist "build" rmdir /s /q build
  echo [OK] Build folder cleaned
) else (
  echo.
  echo ====================================
  echo BUILD FAILED
  echo ====================================
  echo.
  echo Check the error messages above
)

echo.
echo Closing in 5 seconds...
timeout /t 5 /nobreak >nul