@echo off
REM =====================================================
REM CONFIG.BAT - Configuracion de variables
REM =====================================================
REM Este archivo contiene la configuracion de variables
REM que usan los scripts de build.
REM
REM IMPORTANTE: No modifiques este archivo a menos que
REM sepas lo que estas haciendo. Los valores por defecto
REM funcionan en la mayoria de los casos.
REM =====================================================

REM Nombre del entorno Conda
set CONDA_ENV=jm_pyside_313

REM Nombre del ejecutable de salida
set EXE_NAME=JMComander

REM Version para el nombre del ZIP
set VERSION=1.0

REM =====================================================
REM NOTAS PARA DESARROLLADORES:
REM =====================================================
REM Si necesitas cambiar la ubicacion de Conda porque
REM 'conda info --base' no funciona en tu sistema,
REM puedes descomentar y modificar la siguiente linea:
REM
REM set CONDA_BASE=C:\ProgramData\anaconda3
REM
REM Si haces esto, asegurate de que:
REM 1. La ruta apunta a la instalacion base de Conda
REM 2. El entorno %CONDA_ENV% existe en %CONDA_BASE%\envs\
REM =====================================================
