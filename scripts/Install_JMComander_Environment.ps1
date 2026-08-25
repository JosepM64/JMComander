#!/usr/bin/env pwsh
# Script de instalación automática de JMComander
# Ejecutar como Administrador en PowerShell
# .[JmComander_Installer.ps1

param(
    [switch]$SkipCondaInstall = $false,
    [switch]$SkipEnvCreation = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# Colores para output
function Write-Header($text) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $text -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success($text) {
    Write-Host "✓ $text" -ForegroundColor Green
}

function Write-Error($text) {
    Write-Host "✗ $text" -ForegroundColor Red
}

function Write-Info($text) {
    Write-Host "→ $text" -ForegroundColor Yellow
}

# Verificar si se ejecuta como administrador
function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Error "Este script debe ejecutarse como Administrador"
    Write-Info "Cierra PowerShell y vuelve a abrirlo con 'Ejecutar como administrador'"
    exit 1
}

Write-Header "Instalador JMComander v1.6.1"
Write-Info "Fecha: $(Get-Date)"
Write-Info "Sistema: $([System.Environment]::OSVersion.VersionString)"

# ============================================
# PASO 1: Instalar Miniconda
# ============================================
if (-not $SkipCondaInstall) {
    Write-Header "PASO 1: Instalando Miniconda"
    
    # Verificar si conda ya está instalado
    $condaInstalled = $false
    try {
        $condaPath = (Get-Command conda -ErrorAction SilentlyContinue).Source
        if ($condaPath) {
            Write-Success "Miniconda ya está instalado en: $condaPath"
            $condaInstalled = $true
        }
    } catch {
        $condaInstalled = $false
    }
    
    if (-not $condaInstalled) {
        Write-Info "Descargando Miniconda..."
        $minicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
        $installerPath = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"
        
        try {
            Invoke-WebRequest -Uri $minicondaUrl -OutFile $installerPath -UseBasicParsing
            Write-Success "Descarga completada"
        } catch {
            Write-Error "Error descargando Miniconda: $_"
            exit 1
        }
        
        Write-Info "Instalando Miniconda (esto puede tardar varios minutos)..."
        # Instalación silenciosa: /S = silent, /D = directorio de instalación
        $installDir = "C:\ProgramData\Miniconda3"
        $arguments = "/S /D=$installDir"
        
        $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
        
        if ($process.ExitCode -ne 0) {
            Write-Error "Error instalando Miniconda (código: $($process.ExitCode))"
            exit 1
        }
        
        Write-Success "Miniconda instalado correctamente"
        
        # Agregar al PATH del sistema
        Write-Info "Agregando Miniconda al PATH..."
        $condaPath = "$installDir\Scripts"
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
        
        if ($currentPath -notlike "*$condaPath*") {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$condaPath", "Machine")
            Write-Success "Miniconda agregado al PATH"
        } else {
            Write-Info "Miniconda ya está en el PATH"
        }
        
        # Refrescar PATH en la sesión actual
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
        
        # Limpiar instalador
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Info "Omitiendo instalación de Miniconda (--SkipCondaInstall)"
}

# ============================================
# PASO 2: Configurar Conda
# ============================================
Write-Header "PASO 2: Configurando Conda"

# Inicializar conda para PowerShell
Write-Info "Inicializando Conda..."
& conda init powershell | Out-Null
Write-Success "Conda inicializado"

# Aceptar términos de servicio
Write-Info "Aceptando términos de servicio de Conda..."
try {
    & conda tos accept 2>&1 | Out-Null
    Write-Success "Términos de servicio aceptados"
} catch {
    Write-Error "Error aceptando términos: $_"
}

# Eliminar canales problemáticos
Write-Info "Configurando canales de Conda..."
try {
    # Verificar canales actuales
    $channels = & conda config --show channels 2>&1
    
    # Eliminar canales problemáticos si existen
    $problematicChannels = @("miktex", "texlive")
    foreach ($channel in $problematicChannels) {
        if ($channels -match $channel) {
            Write-Info "Eliminando canal problemático: $channel"
            & conda config --remove channels $channel 2>&1 | Out-Null
        }
    }
    
    Write-Success "Canales configurados correctamente"
} catch {
    Write-Info "No se encontraron canales problemáticos o ya fueron eliminados"
}

# ============================================
# PASO 3: Crear entorno jm_pyside_312
# ============================================
if (-not $SkipEnvCreation) {
    Write-Header "PASO 3: Creando entorno 'jm_pyside_312'"
    
    # Verificar si el entorno ya existe
    $envExists = $false
    try {
        $envList = & conda env list 2>&1
        if ($envList -match "jm_pyside_312") {
            $envExists = $true
            Write-Info "El entorno 'jm_pyside_312' ya existe"
        }
    } catch {
        $envExists = $false
    }
    
    if (-not $envExists) {
        Write-Info "Creando entorno jm_pyside_312 con Python 3.12..."
        
        try {
            & conda create -n jm_pyside_312 python=3.12 -y 2>&1 | ForEach-Object {
                if ($Verbose) { Write-Host $_ }
            }
            Write-Success "Entorno creado correctamente"
        } catch {
            Write-Error "Error creando entorno: $_"
            exit 1
        }
    } else {
        Write-Success "Usando entorno existente 'jm_pyside_312'"
    }
    
    # ============================================
    # PASO 4: Instalar dependencias
    # ============================================
    Write-Header "PASO 4: Instalando dependencias"
    
    $packages = @(
        "pyside6",
        "pyinstaller",
        "send2trash",
        "rarfile",
        "py7zr"
    )
    
    foreach ($package in $packages) {
        Write-Info "Instalando $package..."
        try {
            & conda run -n jm_pyside_312 pip install $package 2>&1 | ForEach-Object {
                if ($Verbose) { Write-Host $_ }
            }
            Write-Success "$package instalado"
        } catch {
            Write-Error "Error instalando $package`: $_"
        }
    }
    
    Write-Success "Todas las dependencias instaladas"
    
} else {
    Write-Info "Omitiendo creación de entorno (--SkipEnvCreation)"
}

# ============================================
# PASO 5: Verificar instalación
# ============================================
Write-Header "PASO 5: Verificando instalación"

try {
    # Verificar conda
    $condaVersion = & conda --version 2>&1
    Write-Success "Conda: $condaVersion"
    
    # Verificar entorno
    $envList = & conda env list 2>&1
    if ($envList -match "jm_pyside_312") {
        Write-Success "Entorno 'jm_pyside_312': OK"
    } else {
        Write-Error "Entorno 'jm_pyside_312' no encontrado"
    }
    
    # Verificar Python
    $pythonVersion = & conda run -n jm_pyside_312 python --version 2>&1
    Write-Success "Python: $pythonVersion"
    
    # Verificar PySide6
    try {
        $pysideVersion = & conda run -n jm_pyside_312 python -c "import PySide6; print(PySide6.__version__)" 2>&1
        Write-Success "PySide6: $pysideVersion"
    } catch {
        Write-Error "PySide6 no está instalado correctamente"
    }
    
} catch {
    Write-Error "Error en verificación: $_"
}

# ============================================
# RESUMEN
# ============================================
Write-Header "INSTALACIÓN COMPLETADA"

Write-Host "`nPara compilar JMComander:" -ForegroundColor Cyan
Write-Host "1. Copia el código fuente a tu ordenador" -ForegroundColor White
Write-Host "2. Abre PowerShell en la carpeta del proyecto" -ForegroundColor White
Write-Host "3. Ejecuta: .\scripts\2_quick_build.bat" -ForegroundColor Yellow

Write-Host "`nComandos útiles:" -ForegroundColor Cyan
Write-Host "  conda activate jm_pyside_312    # Activar entorno" -ForegroundColor Gray
Write-Host "  conda deactivate                # Desactivar entorno" -ForegroundColor Gray
Write-Host "  conda env list                  # Ver entornos" -ForegroundColor Gray

Write-Host "`nEl entorno está listo para usar!" -ForegroundColor Green

# Preguntar si desea reiniciar PowerShell
$restart = Read-Host "`n¿Deseas reiniciar PowerShell ahora para aplicar los cambios? (S/N)"
if ($restart -eq "S" -or $restart -eq "s") {
    Write-Info "Reiniciando PowerShell..."
    Start-Process powershell
    exit
}
