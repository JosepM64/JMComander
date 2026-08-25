@echo off
REM Lint script for JMComander using Ruff
REM Usage: ruff_lint.bat [--fix]

setlocal

echo ========================================
echo JMComander Ruff Linter
echo ========================================

REM Check if Ruff is installed
python -m ruff --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ruff is not installed.
    echo Install it with: pip install ruff
    exit /b 1
)

REM Run Ruff with appropriate arguments
if "%1"=="--fix" (
    echo Running Ruff with --fix (auto-fixing issues except formatting)...
    python -m ruff check --fix .
) else (
    echo Running Ruff check (no auto-fixes)...
    python -m ruff check .
)

if errorlevel 1 (
    echo.
    echo ========================================
    echo Linting completed with errors/warnings.
    ========================================
    exit /b 1
) else (
    echo.
    echo ========================================
    echo No linting issues found!
    echo ========================================
)

endlocal
