# JMComander

Administrador de archivos de doble panel desarrollado con PySide6 para Windows.

## Descripción

JMComander es una aplicación de gestión de archivos con interfaz de doble panel, desarrollada en Python usando PySide6 (Qt6). Permite operaciones de archivos eficientes con vista dual, plugins extensibles y configuración personalizable.

## Requisitos del Sistema

- **Sistema Operativo:** Windows 10/11
- **Python:** 3.13 (a través de Conda)
- **Gestor de entornos:** Conda (Anaconda o Miniconda)
- **Entorno:** `jm_pyside_313`
## Instalación y Configuración

### 1. Instalar Conda

Descarga e instala Anaconda o Miniconda desde:
- [Anaconda](https://www.anaconda.com/download) (recomendado)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (versión ligera)

**Nota:** Durante la instalación, asegúrate de que la opción "Add to PATH" esté marcada.

### 2. Crear el Entorno

```bash
conda create -n jm_pyside_313 python=3.13 -y
conda activate jm_pyside_313
pip install PySide6 PyInstaller send2trash
```

### 3. Desarrollo

Para ejecutar la aplicación en modo desarrollo:

```bash
conda activate jm_pyside_313
cd JMComander
python main.py
```

## Compilación (Build)

Los scripts de build están en la carpeta `scripts/`.

### Build Rápido (Recomendado)

```batch
build.bat
```

Este script compila automáticamente sin pausas. Ideal para desarrollo diario.

### Verificación

```batch
python scripts\verify_automatica.py
```

Ejecuta 82 tests de estructura, imports, funcionalidades y plugins antes de cada release.

### Flujo Completo para Distribución

```batch
build.bat                              # Compila
python scripts\verify_automatica.py    # Verifica (82 tests)
scripts\6_crear_distribucion.bat       # Crea ZIP para distribuir
```

## Scripts Disponibles

| Script | Descripción | Cuándo usarlo |
|--------|-------------|---------------|
| `build.bat` | Build rápido automático | Desarrollo diario (RECOMENDADO) |
| `scripts\3_copy_qt_dlls.bat` | Copia DLLs de Qt6 | Si hay error de ImportError |
| `scripts\5_lanzar_final.bat` | Ejecuta JMComander | Para probar rápidamente |
| `scripts\6_crear_distribucion.bat` | Crea ZIP distribuible | Cuando quieres distribuir |
| `scripts\7_verificar_iconos.bat` | Verifica iconos en el build | Si hay problemas visuales |
| `scripts\8_cambiar_tema.bat` | Cambia tema de iconos | Antes de compilar |
| `scripts\9_compilar_ambos_auto.bat` | Compila ambas versiones | Para distribuir Material + Phosphor |
| `python scripts\verify_automatica.py` | Verificación (82 tests) | Antes de cada release |

**Más información:** Ver `scripts/README.md` para documentación detallada de cada script.

## Estructura del Proyecto

```
JMcomander/
├── main.py              # Punto de entrada
├── build.bat            # Build rápido (raíz del proyecto)
├── JMComander.spec      # Configuración de PyInstaller
├── src/                 # Código fuente de la aplicación
│   ├── core/           # Lógica de negocio
│   ├── ui/             # Interfaz de usuario
│   └── plugins/        # Plugins extensibles
├── scripts/             # Scripts auxiliares
│   ├── 3_copy_qt_dlls.bat
│   ├── 5_lanzar_final.bat
│   ├── 6_crear_distribucion.bat
│   ├── 7_verificar_iconos.bat
│   ├── 8_cambiar_tema.bat
│   ├── 9_compilar_ambos_auto.bat
│   ├── CONFIG.bat
│   ├── verify_automatica.py
│   └── README.md
├── docs/
│   └── ENV.md
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

## Salida del Build

Después de compilar, el ejecutable se encuentra en:

```
dist/
└── JMComander/
    ├── JMComander.exe      # Ejecutable principal
    ├── _internal/          # DLLs y dependencias (Qt6, PySide6)
    └── src/plugins/        # Plugins de la aplicación
```

## Distribución

Para distribuir la aplicación:

1. Ejecuta `scripts\6_crear_distribucion.bat`
2. El script creará un archivo ZIP en `releases/JMComander_v1.0_YYYYMMDD.zip`
3. El ZIP contiene todo lo necesario para ejecutar la aplicación
4. El usuario final solo necesita descomprimir y ejecutar `JMComander.exe`

**Nota:** No se requiere instalación ni dependencias adicionales. Todo está incluido en el ZIP.

## Solución de Problemas

### Error: "No se encuentra el entorno jm_pyside_313"

Crea el entorno:
```bash
conda create -n jm_pyside_313 python=3.13 -y
conda activate jm_pyside_313
pip install PySide6 PyInstaller send2trash
```

### El ejecutable no funciona en otro ordenador

Asegúrate de que las DLLs de Visual C++ Redistributable estén instaladas en el ordenador destino. Descarga desde:
[Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

## Características

- **Doble panel:** Vista dual para operaciones de archivos eficientes
- **Plugins extensibles:** Sistema de plugins para funcionalidades adicionales
- **Configuración persistente:** Guarda preferencias y bookmarks
- **Atajos de teclado:** Navegación rápida con teclado
- **Vista de lista/iconos:** Cambia entre diferentes modos de visualización
- **Operaciones de archivos:** Copiar, mover, eliminar, renombrar, comprimir

## Documentación Adicional

- `scripts/README.md` - Guía completa de scripts de build
- `docs/ENV.md` - Configuración del entorno de desarrollo
- `CHANGELOG.md` - Historial de cambios y versiones

## Notas Importantes

- **Solo Windows:** Esta versión está diseñada exclusivamente para Windows
- **PySide6:** Usa Qt6 a través de PySide6 (no PyQt6)
- **Conda:** Requiere entorno Conda específico (`jm_pyside_313`)
- **Portátil:** El ejecutable generado es portátil (no requiere instalación)

## Licencia

[Agregar información de licencia]

## Contacto

[Agregar información de contacto]

---

**Última actualización:** 2026-07-29  
**Versión:** 6.8.3  
**Estado:** Estable y listo para distribución
