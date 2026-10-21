import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import py7zr
import rarfile

logger = logging.getLogger(__name__)


@dataclass
class MountInfo:
    archive_path: Path
    mount_point: Path
    created_at: float
    last_access: float
    size: int


class ArchiveHandler:
    def __init__(self, temp_base: Path | None = None):
        self.temp_base = temp_base or Path(tempfile.gettempdir()) / "JMComander"
        self.mounted_archives: dict[str, MountInfo] = {}
        self._ensure_temp_dir()
        self.RAR_EXE = self._find_rar_exe()
        self.SEVEN_ZIP_EXE = self._find_7z_exe()
        self._configure_rarfile()

    def _ensure_temp_dir(self):
        try:
            if not self.temp_base.exists():
                self.temp_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.exception("Error creando directorio temporal: %s", e)  # noqa: TRY401

    @staticmethod
    def _get_assets_path() -> Path:
        if getattr(sys, "frozen", False):
            base = Path(sys._MEIPASS)  # noqa: SLF001
            for candidate in [base / "assets", base / "src" / "assets"]:
                if candidate.exists():
                    return candidate
        return Path(__file__).parent.parent / "assets"

    def _find_rar_exe(self) -> str | None:
        locations = ["UnRAR.exe", "unrar", "RAR.exe"]
        for loc in locations:
            if shutil.which(loc):
                logger.info("Found RAR executable: %s", loc)
                return loc
        assets = self._get_assets_path()
        for loc in locations:
            exe_path = assets / loc
            if exe_path.exists():
                logger.info("Found RAR in assets: %s", exe_path)
                return str(exe_path)
        return None

    def _find_rar_creator(self) -> str | None:
        """Busca una eina que pugui CREAR arxius RAR.

        El UnRAR.exe gratuït que incloem (assets/UnRAR.exe) SOLAMENT extreu:
        no accepta l'ordre 'a' (crear). Crear RAR requereix WinRAR (shareware)
        o RAR.exe, que no venen amb l'aplicació.
        """
        locations = ["WinRAR.exe", "RAR.exe", "rar.exe"]
        for loc in locations:
            found = shutil.which(loc)
            if found:
                logger.info("Found RAR creator: %s", found)
                return found
        for base in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
        ):
            if not base:
                continue
            for loc in locations:
                exe_path = Path(base) / "WinRAR" / loc
                if exe_path.exists():
                    logger.info("Found RAR creator: %s", exe_path)
                    return str(exe_path)
        return None

    def _find_7z_exe(self) -> str | None:
        locations = ["7z.exe", "7za.exe"]
        for loc in locations:
            if shutil.which(loc):
                logger.info("Found 7-Zip: %s", loc)
                return loc
        pf = os.environ.get("ProgramFiles", "C:\\Program Files")  # noqa: SIM112
        for loc in locations:
            exe_path = Path(pf) / "7-Zip" / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in Program Files: %s", exe_path)
                return str(exe_path)
        pf_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")  # noqa: SIM112
        for loc in locations:
            exe_path = Path(pf_x86) / "7-Zip" / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in Program Files x86: %s", exe_path)
                return str(exe_path)
        assets = self._get_assets_path()
        for loc in locations:
            exe_path = assets / loc
            if exe_path.exists():
                logger.info("Found 7-Zip in assets: %s", exe_path)
                return str(exe_path)
        return None

    def _configure_rarfile(self):
        """Configura rarfile perquè utilitzi una eina que realment funcioni.

        rarfile 4.x és un parser 100% Python, però per descomprimir els
        fitxers *comprimits* necessita un descompressor extern (unrar, unar,
        7z o bsdtar). Si no se li diu quin utilitzar, tria el primer que
        troba al PATH: a les màquines amb conda hi ha bsdtar (libarchive), que
        NO sap llegir RAR5 comprimit i falla amb
        "Failed the read enough data: req=... got=...".

        Per això fixem l'eina: la DLL UnRAR si la versió de rarfile la sap
        fer servir (rarfile < 4), i si no, l'executable UnRAR.exe / 7z.exe que
        shippem a assets/.
        """
        try:
            if hasattr(rarfile, "UNRAR_LIB") and sys.platform == "win32":
                dll_path = self._find_unrar_dll()
                if dll_path:
                    rarfile.UNRAR_LIB = dll_path
                    logger.info("Configurado UnRAR DLL: %s", dll_path)
            if self.RAR_EXE:
                rarfile.UNRAR_TOOL = self.RAR_EXE
            elif self.SEVEN_ZIP_EXE:
                rarfile.SEVENZIP_TOOL = self.SEVEN_ZIP_EXE
        except (ImportError, AttributeError):
            pass

    def _ensure_rarfile_tool(self) -> None:
        """Força rarfile a reassignar l'eina (cachea el resultat globalment)."""
        try:
            rarfile.tool_setup(force=True)
            logger.info("rarfile usando la herramienta: %s", rarfile.tool_setup().setup["open_cmd"][0])
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo configurar la herramienta de rarfile: %s", e)

    def _find_unrar_dll(self) -> str | None:
        dll_names = ["UnRAR.dll", "UnRAR64.dll"]
        assets = self._get_assets_path()
        for name in dll_names:
            dll_path = assets / name
            if dll_path.exists():
                logger.info("Found UnRAR DLL: %s", dll_path)
                return str(dll_path)
        for name in dll_names:
            found = shutil.which(name.lower().replace(".dll", ""))
            if found:
                return found
        return None

    def is_archive(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path.lower())[1]
        return ext in [".zip", ".tar", ".gz", ".bz2", ".rar", ".7z"]

    def mount_archive(self, archive_path: str) -> str | None:
        path = Path(archive_path)
        if not path.exists():
            return None

        # Si ya está montado, retornar
        if str(path) in self.mounted_archives:
            self.mounted_archives[str(path)].last_access = time.time()
            return str(self.mounted_archives[str(path)].mount_point)

        # Crear punto de montaje
        hash_id = hashlib.md5(str(path).encode()).hexdigest()[:10]
        mount_point = self.temp_base / f"mnt_{hash_id}"

        try:
            if mount_point.exists():
                shutil.rmtree(mount_point)
            mount_point.mkdir(parents=True, exist_ok=True)

            if self._extract_archive(path, mount_point):
                self.mounted_archives[str(path)] = MountInfo(
                    archive_path=path,
                    mount_point=mount_point,
                    created_at=time.time(),
                    last_access=time.time(),
                    size=path.stat().st_size,
                )
                return str(mount_point)
        except Exception as e:
            logger.exception("Error montando archivo %s: %s", path, e)  # noqa: TRY401

        return None

    def _extract_archive(self, path: Path, dest: Path, password: str | None = None) -> bool:
        ext = path.suffix.lower()
        try:
            if ext == ".zip":
                with zipfile.ZipFile(path, "r") as z:
                    if password:
                        z.setpassword(password.encode())
                    z.extractall(dest)
                return True
            if ext in [".tar", ".gz", ".bz2"]:
                with tarfile.open(path, "r:*") as t:
                    t.extractall(dest)
                return True
            if ext == ".rar":
                return self._extract_rar(path, dest, password)
            if ext == ".7z":
                return self._extract_7z(path, dest, password)
        except Exception as e:
            logger.exception("Error extrayendo %s: %s", path, e)  # noqa: TRY401
        return False

    def _progress_cancel_loop(
        self, progress, items: list, process_fn,
    ) -> int:
        """Itera llista amb progress bar i cancel·lació. Retorna els processats."""
        processed = 0
        total = len(items) if items else 0
        if total == 0:
            return 0
        # QProgressDialog ja ha de ser creat pel cridor amb range configurat
        for i, item in enumerate(items):
            if progress.wasCanceled():
                progress.close()
                return processed
            progress.setValue(i + 1)
            progress.setLabelText(f"Processant: {item}")
            try:
                process_fn(item)
            except Exception:  # noqa: BLE001
                logger.warning("Error processant: %s", item)
                progress.setLabelText(f"Error: {item}")
        progress.setValue(len(items) if items else 0)
        progress.close()
        return processed

    def _extract_rar(self, path: Path, dest: Path, password: str | None = None) -> bool:
        """Extreu un RAR.

        Orden: UnRAR.exe CLI -> rarfile (parser Python) -> 7z.exe CLI.

        El CLI de UnRAR va primer perquè és ~20x més ràpid que rarfile
        (rarfile.extractall() obre un procés per cada fitxer) i perquè
        bsdtar/libarchive no sap llegir els RAR5 sòlids.
        Tots els subprocess s'executen sense finestra de consola (CREATE_NO_WINDOW).
        """
        # 1) UnRAR.exe CLI (ventana oculta) - mes rapida i mes fiable
        if self.RAR_EXE:
            try:
                # UnRAR retorna rc=10 (destino no encontrado) si el directorio no existe
                dest.mkdir(parents=True, exist_ok=True)
                # "-p-" = sense contrasenya (no pregunta res i no s'ha penjat)
                cmd = [self.RAR_EXE, "x", "-y", "-p-"]
                if password:
                    cmd[3] = f"-p{password}"
                cmd.extend([str(path), str(dest)])
                result = self._run_hidden(cmd, timeout=300)
                if result.returncode == 0:
                    logger.info("Extracted RAR using CLI: %s", path)
                    return True
                logger.warning("UnRAR CLI failed (rc=%s): %s", result.returncode, result.stderr[:200])
            except Exception as cli_e:
                logger.exception("UnRAR CLI error: %s", cli_e)  # noqa: TRY401

        # 2) rarfile (parseo puro en Python, usa la herramienta configurada)
        try:
            self._ensure_rarfile_tool()
            with rarfile.RarFile(str(path)) as r:
                if password:
                    r.setpassword(password)
                r.extractall(str(dest))
            logger.info("Extracted RAR using rarfile: %s", path)
            return True  # noqa: TRY300
        except Exception as e:  # noqa: BLE001
            logger.warning("rarfile failed: %s", e)

        # 3) Ultimo recurso: 7z.exe CLI (tambien lee RAR, ventana oculta)
        if self.SEVEN_ZIP_EXE:
            try:
                dest.mkdir(parents=True, exist_ok=True)
                cmd = [self.SEVEN_ZIP_EXE, "x", "-y", "-p"]
                if password:
                    cmd[3] = f"-p{password}"
                cmd.extend([str(path), f"-o{dest!s}"])
                result = self._run_hidden(cmd, timeout=300)
                if result.returncode == 0:
                    logger.info("Extracted RAR using 7z CLI: %s", path)
                    return True
                logger.warning("7z CLI failed (rc=%s): %s", result.returncode, result.stderr[:200])
            except Exception as cli_e:
                logger.exception("7z CLI error: %s", cli_e)  # noqa: TRY401
        return False

    @staticmethod
    def _run_hidden(cmd: list[str], timeout: int = 120):
        """Ejecuta un comando sin abrir ventana de consola (Windows)."""
        kwargs = {
            "capture_output": True,
            "timeout": timeout,
            "stdin": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return subprocess.run(cmd, **kwargs)  # noqa: PLW1510

    def _extract_7z(self, path: Path, dest: Path, password: str | None = None) -> bool:
        # Intentar py7zr primero
        try:
            with py7zr.SevenZipFile(str(path), mode="r", password=password) as z:
                z.extractall(str(dest))
            logger.info("Extracted 7z using py7zr: %s", path)
            return True  # noqa: TRY300
        except Exception as e:  # noqa: BLE001
            logger.warning("py7zr failed: %s", e)
            # Fallback: usar 7z.exe CLI (ventana oculta)
            if self.SEVEN_ZIP_EXE:
                try:
                    # "-p" sin valor = sin contrasenya (evita que 7z la demani)
                    cmd = [self.SEVEN_ZIP_EXE, "x", "-y", f"-p{password}" if password else "-p"]
                    cmd.extend([str(path), f"-o{dest!s}"])
                    result = self._run_hidden(cmd, timeout=300)
                    if result.returncode == 0:
                        logger.info("Extracted 7z using CLI: %s", path)
                        return True
                    logger.warning("7z CLI failed (rc=%s): %s", result.returncode, result.stderr[:200])
                except Exception as cli_e:
                    logger.exception("7z CLI error: %s", cli_e)  # noqa: TRY401
        return False

    def unmount_archive(self, archive_path: str) -> bool:
        if archive_path in self.mounted_archives:
            mount = self.mounted_archives.pop(archive_path)
            try:
                if mount.mount_point.exists():
                    shutil.rmtree(mount.mount_point)
                return True  # noqa: TRY300
            except Exception:  # noqa: BLE001
                pass
        return False

    def get_mount_info(self, path: str) -> MountInfo | None:
        for mount in self.mounted_archives.values():
            if path.startswith(str(mount.mount_point)):
                return mount
        return None

    def get_display_path(self, mount_point: str) -> str:
        """Retorna la ruta del archivo original en lugar del punto de montaje"""
        info = self.get_mount_info(mount_point)
        if info:
            return f"{info.archive_path}►"
        return mount_point

    def is_inside_archive(self, path: str) -> bool:
        """Indica si la ruta está dentro de un archivo comprimido"""
        return self.get_mount_info(path) is not None


# Instancia global
archive_handler = ArchiveHandler()
