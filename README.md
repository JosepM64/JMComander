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
pip install -r requirements.txt
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
pip install -r requirements.txt
```

### El ejecutable no funciona en otro ordenador

Asegúrate de que las DLLs de Visual C++ Redistributable estén instaladas en el ordenador destino. Descarga desde:
[Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

## Características

- **Doble panel:** Vista dual estilo Total Commander con swap, comparación de carpetas y sincronización
- **iPhone / MTP:** Navega por el Internal Storage del iPhone vía Shell COM y copia fotos/vídeos al PC (F5), con vista de columnas ordenables por nombre, tamaño y fecha
- **Motor de copia propio:** Copia en paralelo con barra de progreso in-line, cancelación en vivo y sin diálogos modales; soporta archivos >2GB
- **Archivos comprimidos:** Explora contenido de zip/rar/7z como si fueran carpetas
- **Menús contextuales nativos de Windows** y Quick Look (F3) para previsualizar
- **Plugins extensibles:** 16 plugins incluidos — organizador, buscador de duplicados, sincronizador, conversor de imágenes (con soporte HEIF del iPhone), conexión remota SFTP, borrado seguro, analizador de espacio, etc.
- **Borrado seguro:** Método auto que detecta SSD/HDD y aplica pasadas sobrescribiendo
- **Configuración persistente:** Preferencias, bookmarks, apps rápidas e historial de rutas
- **Atajos de teclado:** Navegación rápida estilo Norton Commander (F5 copiar, F6 mover, F8 eliminar...)
- **Vistas:** Detalles / Lista / Iconos, con filtro rápido, pestañas de carpetas y breadcrumb

## Documentación Adicional

- `scripts/README.md` - Guía completa de scripts de build
- `CHANGELOG.md` - Historial de cambios y versiones
- `AGENTS.md` - Arquitectura interna y guía para desarrolladores

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

**Última actualización:** 2026-08-30  
**Versión:** 6.9.21  
**Estado:** Estable y listo para distribución
