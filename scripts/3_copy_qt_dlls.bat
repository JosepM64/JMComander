@echo off
REM =====================================================
REM 3_COPY_QT_DLLS.BAT - Copiar DLLs de Qt6
REM =====================================================
REM Este script copia las DLLs de Qt6 desde el entorno Conda.
REM Lo usa quick_build.bat automaticamente, pero puedes ejecutarlo manualmente
REM si el ejecutable da error "ImportError: could not import module 'PySide6.QtGui'"
REM 
REM Que hace:
REM   - Detecta automaticamente la ubicacion de Conda
REM   - Copia todas las DLLs de Qt6 necesarias a _internal/
REM   - Verifica que Qt6Gui.dll este presente (la mas importante)
REM 
REM Uso: Ejecutar si hay errores de DLLs faltantes
REM NOTA: Requiere que 'conda' este en el PATH del sistema
REM =====================================================

echo ====================================
echo Copying Qt6 DLLs from Conda environment
echo ====================================
echo.

REM Cargar configuracion si existe
if exist "%~dp0CONFIG.bat" (
  call "%~dp0CONFIG.bat"
)

REM Si no se definio CONDA_BASE en CONFIG.bat, detectarlo automaticamente
if not defined CONDA_BASE (
  for /f "tokens=*" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
)

if not defined CONDA_BASE (
  echo [ERROR] No se pudo detectar la instalacion de Conda.
  echo.
  echo Asegurate de que:
  echo 1. Conda esta instalado
  echo 2. 'conda' esta en el PATH del sistema
  echo 3. Puedes ejecutar 'conda info --base' desde cualquier carpeta
  echo.
  echo Si Conda esta en una ubicacion no estandar, edita scripts\CONFIG.bat
  echo y descomenta la linea: set CONDA_BASE=C:\\Tu\\Ruta\\Conda
  echo.
  pause
  exit /b 1
)

REM Detectar ubicaci?n del entorno conda
if not defined CONDA_ENV set "CONDA_ENV=jm_pyside_313"

REM Verificar si el entorno est? en .conda del usuario o en Miniconda3
if exist "%USERPROFILE%\.conda\envs\%CONDA_ENV%" (
    set "CONDA_PREFIX=%USERPROFILE%\.conda\envs\%CONDA_ENV%"
) else (
    set "CONDA_PREFIX=%CONDA_BASE%\envs\%CONDA_ENV%"
)

set "QT_BIN=%CONDA_PREFIX%\Library\bin"
set "QT_PYSIDE=%CONDA_PREFIX%\Lib\site-packages\PySide6"

echo [OK] Conda detectado en: %CONDA_BASE%
echo [OK] Entorno encontrado en: %CONDA_PREFIX%
echo.

REM Navegar al directorio raiz del proyecto (subir un nivel desde scripts/)
cd /d "%~dp0.."

set "DIST_DIR=dist\JMComander\_internal"

REM Verificar al menos una de las ubicaciones de Qt
if not exist "%QT_BIN%" (
  if not exist "%QT_PYSIDE%" (
    echo [ERROR] Qt binaries directory not found in either:
    echo   %QT_BIN%
    echo   %QT_PYSIDE%
    echo.
    echo Verifica que:
    echo - El entorno '%CONDA_ENV%' existe
    echo - Qt/PySide6 esta instalado en el entorno
    echo.
    pause
    exit /b 1
  )
)

if not exist "%DIST_DIR%" (
  echo [ERROR] Distribution directory not found: %DIST_DIR%
  echo.
  echo Ejecuta primero: build.bat
  echo.
  pause
  exit /b 1
)

echo Qt binaries directory 1: %QT_BIN%
echo Qt binaries directory 2: %QT_PYSIDE%
echo Destination directory: %DIST_DIR%
echo.

REM Qt6Core.dll, Qt6Gui.dll, Qt6Widgets.dll ja estan inclosos per PyInstaller a PySide6/
REM No cal copiar-los manualment per evitar duplicats
REM Llista buida - nom?s verifiquem que existeixen
set DLLS=

set COPIED=0
for %%D in (%DLLS%) do (
  REM Buscar en PySide6 primero, luego en Library/bin
  set "FOUND=0"
  if exist "%QT_PYSIDE%\%%D" (
    copy /y "%QT_PYSIDE%\%%D" "%DIST_DIR%\%%D" >nul 2>&1
    if exist "%DIST_DIR%\%%D" (
      echo [OK] Copied %%D from PySide6
      set /a COPIED+=1
      set "FOUND=1"
    ) else (
      echo [FAIL] Failed to copy %%D from PySide6
    )
  )
  
  if "%FOUND%"=="0" (
    if exist "%QT_BIN%\%%D" (
      copy /y "%QT_BIN%\%%D" "%DIST_DIR%\%%D" >nul 2>&1
      if exist "%DIST_DIR%\%%D" (
        echo [OK] Copied %%D from Library/bin
        set /a COPIED+=1
        set "FOUND=1"
      ) else (
        echo [FAIL] Failed to copy %%D from Library/bin
      )
    )
  )
  
  if "%FOUND%"=="0" (
    echo [SKIP] %%D not found in any Qt directory
  )
)

echo.
echo ====================================
echo Copying Platform Plugins
echo ====================================

REM Los platforms ya est?n incluidos por PyInstaller autom?ticamente
echo [INFO] Platforms incluidos automaticamente por PyInstaller

echo.
echo ====================================
echo Summary
echo ====================================
echo DLLs copied: %COPIED%
echo.

REM Verificar que Qt6Gui.dll existeix (dins PySide6/ subcarpeta)
if exist "%DIST_DIR%\PySide6\Qt6Gui.dll" (
  echo [OK] Qt6Gui.dll is present in PySide6/ - correct for pip-installed PySide6
) else if exist "%DIST_DIR%\Qt6Gui.dll" (
  echo [OK] Qt6Gui.dll is present in _internal/ root
) else (
  echo [FAIL] Qt6Gui.dll not found in any expected location
  echo.
  echo Note: With pip-installed PySide6, Qt DLLs are inside PySide6/ subfolder
  echo   %DIST_DIR%\PySide6\
  echo.
  echo Qt6Gui.dll was not found there either. PyInstaller should have included it.
)
echo.
exit /b 0
