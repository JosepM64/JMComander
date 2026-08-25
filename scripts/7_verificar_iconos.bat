@echo off
echo ==========================================
echo JMComander - Verificacion de Iconos
echo ==========================================
echo.
echo Ejecutando prueba de carga de iconos...
echo.

cd /d "%~dp0.."

REM Verificar que los iconos existen en src/assets/icons
echo [1] Verificando iconos en src/assets/icons:
if exist "src\assets\icons\mdi-terminal-outline.svg" (
    echo     [OK] mdi-terminal-outline.svg
) else (
    echo     [FALTA] mdi-terminal-outline.svg
)

if exist "src\assets\icons\mdi-console.svg" (
    echo     [OK] mdi-console.svg
) else (
    echo     [FALTA] mdi-console.svg
)

if exist "src\assets\icons\mdi-content-duplicate.svg" (
    echo     [OK] mdi-content-duplicate.svg
) else (
    echo     [FALTA] mdi-content-duplicate.svg
)

if exist "src\assets\icons\mdi-folder-open.svg" (
    echo     [OK] mdi-folder-open.svg
) else (
    echo     [FALTA] mdi-folder-open.svg
)

if exist "src\assets\icons\mdi-select-all.svg" (
    echo     [OK] mdi-select-all.svg
) else (
    echo     [FALTA] mdi-select-all.svg
)

if exist "src\assets\icons\mdi-content-copy-outline.svg" (
    echo     [OK] mdi-content-copy-outline.svg
) else (
    echo     [FALTA] mdi-content-copy-outline.svg
)

if exist "src\assets\icons\mdi-folder-plus-outline.svg" (
    echo     [OK] mdi-folder-plus-outline.svg
) else (
    echo     [FALTA] mdi-folder-plus-outline.svg
)

echo.
echo [2] Verificando que el ejecutable existe:
if exist "dist\JMComander\JMComander.exe" (
    echo     [OK] Ejecutable encontrado
    echo.
    echo [3] Verificando iconos en el bundle:
    if exist "dist\JMComander\_internal\src\assets\icons" (
        echo     [OK] Carpeta de iconos en bundle encontrada
        dir /b "dist\JMComander\_internal\src\assets\icons\*.svg" 2>nul | find /c "mdi-" >nul && (
            echo     [OK] Iconos mdi-*.svg encontrados en bundle
        ) || (
            echo     [ADVERTENCIA] No se encontraron iconos mdi-*.svg en bundle
        )
    ) else (
        echo     [ERROR] No se encontro carpeta de iconos en bundle
        echo     Ruta esperada: dist\JMComander\_internal\src\assets\icons
    )
) else (
    echo     [ERROR] Ejecutable NO encontrado
    echo     Ejecuta primero: build.bat
)

echo.
echo ==========================================
echo Instrucciones:
echo ==========================================
echo.
echo Si los iconos estan en src/assets/icons pero NO en el bundle,
echo el problema esta en el empaquetado (JMComander.spec).
echo.
echo Si los iconos estan en ambos lugares pero no se ven,
echo el problema puede ser:
echo   - Tama?o de icono muy pequeno
echo   - Plugin SVG de Qt no cargado
echo   - Problema de renderizado de SVG
.
echo.
echo Presiona ENTER para ejecutar JMComander y verificar visualmente...
pause >nul

if exist "dist\JMComander\JMComander.exe" (
    start "" "dist\JMComander\JMComander.exe"
) else (
    echo.
    echo [ERROR] No se puede ejecutar - ejecutable no encontrado
    echo Ejecuta: build.bat
    pause
)
