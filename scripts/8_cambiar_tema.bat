@echo off
REM ==========================================
REM Selector de Tema de Iconos para JMComander
REM ==========================================
echo.
echo JMComander - Selector de Tema de Iconos
echo ==========================================
echo.
echo Opciones disponibles:
echo.
echo 1. MATERIAL DESIGN (por defecto)
echo    - Iconos con estilo Google Material
echo    - B/N (se puede colorear)
echo    - M?s de 26 iconos disponibles
echo.
echo 2. PHOSPHOR ICONS (moderno)
echo    - Estilo moderno y profesional  
echo    - 22 iconos descargados
echo    - Look similar a Windows 11
echo.
echo ==========================================

:MENU
echo.
echo Selecciona una opcion:
echo [1] Usar Material Design
echo [2] Usar Phosphor Icons
echo [3] Ver iconos disponibles
echo [4] Salir
echo.

set /p choice="Opcion (1-4): "

if "%choice%"=="1" goto MATERIAL
if "%choice%"=="2" goto PHOSPHOR
if "%choice%"=="3" goto VER
if "%choice%"=="4" goto SALIR
echo Opcion invalida. Intenta de nuevo.
goto MENU

:MATERIAL
echo.
echo [1] Cambiando a MATERIAL DESIGN...
cd /d "%~dp0..\src\assets"
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
echo # Tama?o de iconos >> icon_theme.py
echo ICON_SIZE = 20  # 20x20 pixels >> icon_theme.py
echo.
echo [OK] Tema cambiado a MATERIAL DESIGN
echo.
echo Iconos disponibles en: src\assets\icons\
echo (26 iconos Material Design)
echo.
pause
goto MENU

:PHOSPHOR
echo.
echo [2] Cambiando a PHOSPHOR ICONS...
cd /d "%~dp0..\src\assets"
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
echo # Tama?o de iconos >> icon_theme.py
echo ICON_SIZE = 20  # 20x20 pixels >> icon_theme.py
echo.
echo [OK] Tema cambiado a PHOSPHOR ICONS
echo.
echo Iconos disponibles en: src\assets\icons-phosphor\
echo (22 iconos Phosphor descargados)
echo.
pause
goto MENU

:VER
echo.
echo [3] Iconos disponibles:
echo.
echo MATERIAL DESIGN (src\assets\icons\):
dir /b "%~dp0..\src\assets\icons\*.svg" 2>nul | find /c "mdi-" >nul && (
    dir /b "%~dp0..\src\assets\icons\*.svg" | more
) || (
    echo No se encontraron iconos Material Design
)
echo.
echo PHOSPHOR ICONS (src\assets\icons-phosphor\):
dir /b "%~dp0..\src\assets\icons-phosphor\*.svg" 2>nul | find /c ".svg" >nul && (
    dir /b "%~dp0..\src\assets\icons-phosphor\*.svg" | more
) || (
    echo No se encontraron iconos Phosphor
)
echo.
pause
goto MENU

:SALIR
echo.
echo ==========================================
echo Para aplicar el tema, ejecuta:
echo   build.bat
echo ==========================================
echo.
pause
exit /b 0
