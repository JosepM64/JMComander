@echo off
REM ==========================================
REM Compilador Dual: Material + Phosphor (AUTO)
REM ==========================================
echo.
echo JMComander - Compilacion de Ambas Versiones
echo ==========================================
echo.
echo Este script creara DOS ejecutables:
echo 1. JMComander-Material.exe (tema Material Design)
echo 2. JMComander-Phosphor.exe (tema Phosphor Icons)
echo.
echo [Iniciando automaticamente...]

cd /d "%~dp0.."

REM ==========================================
REM VERSION 1: MATERIAL DESIGN
REM ==========================================
echo.
echo [1/4] Preparando version MATERIAL DESIGN...
cd src\assets
echo ICON_THEME = "MATERIAL" > icon_theme.py
echo # Sistema de Temas de Iconos para JMComander >> icon_theme.py
echo # Opciones: MATERIAL ^| PHOSPHOR >> icon_theme.py
echo. >> icon_theme.py
echo # Colores para iconos Material Design >> icon_theme.py
echo COLORS = { >> icon_theme.py
echo     "primary": "#2196F3",    # Azul - Acciones principales >> icon_theme.py
echo     "success": "#4CAF50",    # Verde - Crear/Aceptar >> icon_theme.py
echo     "danger": "#F44336",     # Rojo - Eliminar/Cancelar >> icon_theme.py
echo     "warning": "#FF9800",    # Naranja - Advertencia >> icon_theme.py
echo     "info": "#00BCD4",       # Cyan - Informacion >> icon_theme.py
echo     "neutral": "#607D8B",    # Gris - Navegacion >> icon_theme.py
echo } >> icon_theme.py
echo. >> icon_theme.py
echo # Tamano de iconos >> icon_theme.py
echo ICON_SIZE = 20  # 20x20 pixels >> icon_theme.py
cd ..\..\..

echo [2/4] Compilando MATERIAL DESIGN...
call build.bat
if exist "dist\JMComander\JMComander.exe" (
    copy "dist\JMComander\JMComander.exe" "JMComander-Material.exe" >nul
    echo [OK] JMComander-Material.exe creado
) else (
    echo [ERROR] Fallo al compilar version Material
)

REM ==========================================
REM VERSION 2: PHOSPHOR ICONS
REM ==========================================
echo.
echo [3/4] Preparando version PHOSPHOR ICONS...
cd src\assets
echo ICON_THEME = "PHOSPHOR" > icon_theme.py
echo # Sistema de Temas de Iconos para JMComander >> icon_theme.py
echo # Opciones: MATERIAL ^| PHOSPHOR >> icon_theme.py
echo. >> icon_theme.py
echo # Colores para iconos Phosphor >> icon_theme.py
echo COLORS = { >> icon_theme.py
echo     "primary": "#2196F3",    # Azul >> icon_theme.py
echo     "success": "#4CAF50",    # Verde >> icon_theme.py
echo     "danger": "#F44336",     # Rojo >> icon_theme.py
echo     "warning": "#FF9800",    # Naranja >> icon_theme.py
echo } >> icon_theme.py
echo. >> icon_theme.py
echo # Tamano de iconos >> icon_theme.py
echo ICON_SIZE = 20  # 20x20 pixels >> icon_theme.py
cd ..\..\..

echo [4/4] Compilando PHOSPHOR ICONS...
call build.bat
if exist "dist\JMComander\JMComander.exe" (
    copy "dist\JMComander\JMComander.exe" "JMComander-Phosphor.exe" >nul
    echo [OK] JMComander-Phosphor.exe creado
) else (
    echo [ERROR] Fallo al compilar version Phosphor
)

REM ==========================================
REM RESUMEN
REM ==========================================
echo.
echo ==========================================
echo COMPILACION COMPLETADA
echo ==========================================
echo.
echo Se han creado DOS ejecutables:
echo.
echo 1. JMComander-Material.exe
    echo    - Tema: Material Design (26 iconos)
    echo    - Estilo: B/N coloreable
    echo    - Look: Google Material
echo.
echo 2. JMComander-Phosphor.exe
    echo    - Tema: Phosphor Icons (22 iconos)
    echo    - Estilo: Moderno profesional
    echo    - Look: Windows 11 / Modern UI
echo.
echo ==========================================
echo.
echo Proceso finalizado automaticamente.
