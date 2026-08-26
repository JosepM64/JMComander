"""
Gestió de dispositius MTP (Media Transfer Protocol) com iPhone.
Inclou detecció d'iPhone connectat via USB i navegació via Shell Namespace de Windows.

Extret de panel.py per complir amb SoC (Separation of Concerns).
"""

import logging
import time

import win32com.client

logger = logging.getLogger(__name__)

_iphone_cache = None
_iphone_cache_time = 0
_IPHONE_CACHE_TIMEOUT = 30  # resultat positiu (iPhone connectat)
_IPHONE_NEGATIVE_TTL = 300  # sense iPhone: no re-escanejar COM a cada navegació
_shell_app = None  # singleton COM — tot corre al thread d'UI, afinitat garantida


def _get_shell():
    """Retorna la instància COM Shell.Application reutilitzada.
    Crear un Dispatch per crida costava ~100ms i deixava objectes COM solts."""
    global _shell_app  # noqa: PLW0603
    if _shell_app is None:
        _shell_app = win32com.client.Dispatch("Shell.Application")
    return _shell_app


def get_iphone_storage_path(force_refresh=False):
    """
    Retorna (path, name) de l'emmagatzematge intern del primer iPhone detectat.
    Si no troba 'Internal Storage', retorna la ruta del dispositiu.

    Args:
        force_refresh: Si True, ignora el cache i força nova detecció
    """
    global _iphone_cache, _iphone_cache_time  # noqa: PLW0603

    logger.debug(
        f"get_iphone_storage_path llamado:"
        f" force_refresh={force_refresh},"
        f" cache_time={_iphone_cache_time},"
        f" cache={_iphone_cache}"
    )

    if not force_refresh and _iphone_cache_time > 0:
        # TTL llarg per resultats negatius: en màquines SENSE iPhone, passats els
        # 30s cada navegació disparava una enumeració COM completa de "Aquest PC"
        ttl = _IPHONE_CACHE_TIMEOUT if _iphone_cache else _IPHONE_NEGATIVE_TTL
        elapsed = time.time() - _iphone_cache_time
        if elapsed < ttl:
            logger.debug(
                f"Usando cache de iPhone (hace {elapsed:.1f}s, resultado: {_iphone_cache})"  # noqa: G004
            )
            return _iphone_cache

    try:
        shell = _get_shell()
        computers = shell.NameSpace("shell:::{20D04FE0-3AEA-1069-A2D8-08002B30309D}")
        if computers is None:
            logger.debug("No se pudo obtener el namespace de This PC")
            _iphone_cache = None
            _iphone_cache_time = time.time()
            logger.debug("Cache guardado: None (tiempo: %s)", _iphone_cache_time)
            return None

        for item in computers.Items():
            if item.Name and "iPhone" in item.Name:
                logger.debug("Dispositivo iPhone encontrado: %s, Path: %s", item, item)

                try:
                    device_folder = shell.NameSpace(item.Path)
                    if device_folder:
                        items_in_device = device_folder.Items()
                        logger.debug("Items en dispositivo iPhone: %s", items_in_device)

                        result = (item.Path, f"{item.Name}")
                        logger.debug("Retornant dispositiu base iPhone: %s", item)

                        _iphone_cache = result
                        _iphone_cache_time = time.time()
                        logger.debug("Cache guardat: %s", result)
                        return result
                except Exception as folder_error:  # noqa: BLE001
                    logger.debug(
                        f"Error accediendo al folder del iPhone {item.Name}: {folder_error}"  # noqa: G004
                    )

                logger.debug("Usando ruta del dispositivo directamente: %s", item)
                result = (item.Path, item.Name)
                _iphone_cache = result
                _iphone_cache_time = time.time()
                logger.debug(
                    "Cache guardado: fallback dispositivo (tiempo: %s)", _iphone_cache_time
                )
                return result

        logger.debug("No se encontraron dispositivos iPhone en This PC")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error detectando iPhone via shell: %s", e)

        try:
            wmi = win32com.client.GetObject("winmgmts:")
            devices = wmi.ExecQuery("SELECT * FROM Win32_PnPEntity WHERE Name LIKE '%iPhone%'")
            for device in devices:
                logger.debug("Dispositivo iPhone WMI: %s, DeviceID: %s", device, device)
        except Exception as wmi_error:  # noqa: BLE001
            logger.debug("Error en detección WMI: %s", wmi_error)

    _iphone_cache = None
    _iphone_cache_time = time.time()
    logger.debug("Cache guardado: No hay iPhone (tiempo: %s)", _iphone_cache_time)
    return None


def list_shell_folder(path):
    """
    Llista el contingut d'una carpeta usant Shell.Namespace de Windows.
    Funciona per a rutes de dispositiu MTP com iPhone.
    """
    try:
        logger.info("list_shell_folder: intentanto listar %s", path)
        shell = _get_shell()

        folder = shell.NameSpace(path)
        if folder is None:
            logger.warning("Shell folder es None para path: %s", path)
            return _list_shell_folder_fallback(path, shell)

        logger.debug("Folder obtenido exitosamente para %s", path)

        folder_items = folder.Items()
        item_count = folder_items.Count
        logger.info("Items encontrados: %s para path: %s", item_count, path)

        items = []

        try:
            for item in folder_items:
                try:
                    name = item.Name
                    item_path = item.Path
                    is_dir = item.IsFolder
                    size = _get_item_size(folder, item, is_dir)
                    mtime = _get_item_date(folder, item)

                    items.append(
                        {
                            "name": name,
                            "path": item_path,
                            "is_dir": is_dir,
                            "size": size,
                            "mtime": mtime,
                        }
                    )
                    logger.debug(" Item: %s (carpeta: %s) -> %s", name, is_dir, item_path)
                except Exception as inner_e:  # noqa: BLE001
                    logger.warning("Error procesando item: %s", inner_e)
        except Exception as iter_e:  # noqa: BLE001
            logger.warning("Error iterando sobre folder_items: %s", iter_e)

        logger.info("Total items devueltos: %s", len(items))
        return items  # noqa: TRY300

    except Exception as e:  # noqa: BLE001
        logger.warning("Error listing shell folder %s: %s", path, e)
        return []


def _get_item_size(folder, item, is_dir):
    """Obtenir mida real via GetDetailsOf (columna 2). MTP no exposa item.Size."""
    try:
        if is_dir:
            return 0
        detail = folder.GetDetailsOf(item, 2)
        if not detail:
            return 0
        detail = detail.strip().replace("\xa0", " ")
        # Format "2,89 MB", "1.024 KB", "500 bytes"
        parts = detail.split(" ")
        if len(parts) != 2:
            return 0
        try:
            value = float(parts[0].replace(",", "."))
        except ValueError:
            return 0
        unit = parts[1].lower()
        mult = {
            "bytes": 1,
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
            "tb": 1024**4,
        }
        factor = mult.get(unit, 0)
        return int(value * factor) if factor else 0
    except Exception:  # noqa: BLE001
        return 0


def _get_item_date(folder, item):
    """Obtenir data de modificació via GetDetailsOf (columna 3)."""
    try:
        detail = folder.GetDetailsOf(item, 3)
        if not detail:
            return None
        # Formats possibles: "30/6/2019 15:42" o amb hora
        return detail.strip()
    except Exception:  # noqa: BLE001
        return None


def _list_shell_folder_fallback(path, shell):
    """
    Fallback per a rutes MTP/iPhone on shell.NameSpace() no funciona directament.
    Navega des del dispositiu pare baixant per CADA segment del path (SID o GUID),
    usant GetFolder sobre els items que coincideixin.
    """
    logger.info("Intent fallback per a path: %s", path)
    path_str = str(path)

    parts = _split_shell_path(path_str)
    if not parts:
        logger.warning("No s'han trobat parts navegables a: %s", path_str)
        return []

    try:
        folder = shell.NameSpace(path_str)
        if folder is not None:
            # NameSpace directe ja funciona
            items = _collect_folder_items(folder)
            logger.info("Fallback (directe): %s items", len(items))
            return items

        # Si NameSpace falla, navegar des de la base del dispositiu
        base_path = path_str.split("\\SID-", maxsplit=1)[0].split("\\{", maxsplit=1)[0].rstrip("\\")
        folder = shell.NameSpace(base_path)
        if folder is None:
            folder = _find_mtp_device_folder(shell, base_path, [])
            if folder is None:
                logger.warning("No s'ha pogut trobar el dispositiu MTP")
                return []

        for part in parts:
            folder = _descend_shell(folder, part)
            if folder is None:
                logger.warning("No s'ha pogut baixar al segment: %s", part)
                return []

        items = _collect_folder_items(folder)
        logger.info("Fallback: retornant %s items", len(items))
    except Exception as e:  # noqa: BLE001
        logger.warning("Error en fallback list_shell_folder: %s", e)
        return []

    return items


def _descend_shell(folder, part):
    """
    Baixa un nivell dins un Folder shell fins al subitem que coincideix amb `part`.
    `part` pot ser un SID (SID-{NUM,Nom,Mida}) o un GUID ({xxxx-...}).
    Retorna el subfolder o None si no troba coincidència.
    """
    part = str(part)
    part_lower = part.lower()
    # Eliminar prefix SID-
    if part_lower.startswith("sid-"):
        part = part[4:]
    part_clean = part.strip("{}")
    target_name = None

    # Si és un SID {NUM,Nom,Mida}, el nom visible és parts[1]
    if "," in part_clean:
        sid_parts = part_clean.split(",")
        if len(sid_parts) >= 2:
            target_name = sid_parts[1].strip()

    for item in folder.Items():
        if not item.IsFolder:
            continue
        item_name = str(item.Name)
        # Coincideix per nom visible (SID) o per GUID dins el path
        if target_name is not None:
            if item_name == target_name:
                sub = item.GetFolder
                return sub if sub is not None else None
        else:
            try:
                item_path = str(item.Path)
                if part_clean.lower() in item_path.lower():
                    sub = item.GetFolder
                    return sub if sub is not None else None
            except Exception:  # noqa: BLE001
                continue

    return None


def _extract_child_name_from_sid(path_or_seg):
    """Extreu el nom del fill d'una ruta MTP amb format SID-{...,Nom,...}
    o directament d'un segment {NUM,Nom,Mida}."""
    sid_and_child = path_or_seg.split("\\SID-")[-1] if "\\SID-" in path_or_seg else path_or_seg

    # Format: {NUM,Nom,Mida} → parts = ["{NUM", "Nom", "Mida}"]
    if "," in sid_and_child:
        parts = sid_and_child.split(",")
        if len(parts) >= 3:
            return parts[1]
    return None


def _find_mtp_device_folder(shell, hardware_path, child_names):
    """Troba dispositiu MTP navegant des de This PC i retorna la carpeta arrel.
    Cerca items amb SID- al path (dispositius portables)."""
    computers = shell.NameSpace("shell:::{20D04FE0-3AEA-1069-A2D8-08002B30309D}")
    if computers is None:
        return None

    for item in computers.Items():
        if not item.IsFolder:
            continue
        try:
            item_path = str(item.Path)
            if "SID-" not in item_path:
                continue
            folder = item.GetFolder
            if folder is not None:
                logger.info("MTP trobat a This PC: %s", item.Name)
                return folder
        except Exception:
            continue

    logger.warning("No s'ha trobat MTP a This PC per: %s", hardware_path)
    return None


def _collect_folder_items(folder):
    """Recull els items d'un Folder object del Shell."""
    items = []
    for sub_item in folder.Items():
        try:
            is_dir = sub_item.IsFolder
            items.append(
                {
                    "name": sub_item.Name,
                    "path": sub_item.Path,
                    "is_dir": is_dir,
                    "size": _get_item_size(folder, sub_item, is_dir),
                    "mtime": _get_item_date(folder, sub_item),
                }
            )
        except Exception:  # noqa: BLE001
            pass
    return items


def get_shell_display_name(shell_path):
    """Retorna el nom de visualització per a rutes shell (com iPhone)."""
    if "\\SID-" in shell_path:
        parts = shell_path.split("\\SID-")
        if len(parts) > 1:
            sid_part = parts[-1]
            if "," in sid_part:
                return sid_part.split(",")[1].rstrip("}")
    return shell_path.split("\\")[-1] if "\\" in shell_path else "iPhone"


def open_shell_file(shell_path):
    """
    Obre un fitxer dins d'un dispositiu MTP (iPhone) amb l'aplicació per defecte.
    Navega des de l'arrel fins al fitxer i invoca el verb 'open'.
    """
    logger.info("open_shell_file: %s", shell_path)
    path_str = str(shell_path)
    shell = _get_shell()

    # Navegar al pare i trobar l'item
    item = _navigate_to_last_item(path_str, shell)
    if item is None:
        logger.warning("No s'ha trobat l'item per: %s", shell_path)
        return False

    try:
        item.InvokeVerb("open")
        logger.info("InvokeVerb('open') executat per: %s", item.Name)
    except Exception as e:  # noqa: BLE001
        logger.warning("Error InvokeVerb('open') per %s: %s", shell_path, e)
        return False

    return True


def copy_shell_items(shell_paths, dst_folder):
    """
    Copia items MTP (iPhone) al destí usant Shell.CopyHere de Windows.
    Retorna (copiats, errors) amb els noms.
    Síncron — per a còpies des de la UI fer servir MtpCopyJob (jobs.py).
    """
    import os  # noqa: PLC0415

    shell = _get_shell()
    dst = shell.NameSpace(dst_folder)
    copied = []
    errors = []

    for shell_path in shell_paths:
        try:
            copied.append(_copy_single_shell_item(shell, dst, shell_path))
        except Exception as e:  # noqa: BLE001
            logger.warning("Error copiant %s: %s", shell_path, e)
            errors.append(os.path.basename(str(shell_path)))

    return copied, errors


def _copy_single_shell_item(shell, dst_ns, shell_path):
    """Copia UN item shell al namespace destí i retorna el seu nom.
    Llança excepció si falla — el cridador decideix com reportar-ho."""
    import os  # noqa: PLC0415

    if dst_ns is None:
        raise ValueError("Namespace destí nul")
    item = _navigate_to_last_item(str(shell_path), shell)
    if item is None:
        raise LookupError(f"Item no trobat: {shell_path}")
    # 0x14 = FOF_NOCONFIRMATION | FOF_SILENT (sense diàlegs)
    dst_ns.CopyHere(item, 0x14)
    return str(item.Name)


def _navigate_to_last_item(path_str, shell):  # noqa: PLR0912
    """
    Navega des de l'arrel d'un path shell fins al darrer item (fitxer o carpeta)
    i el retorna. Retorna None si no troba res.
    Gestiona tant segments SID-{NUM,Nom,Mida} com GUIDs.
    """
    parts = _split_shell_path(path_str)
    if not parts:
        return None

    # Base del dispositiu: tot el path abans del primer SID/GUID
    base_path = path_str.split("\\SID-")[0].split("\\{")[0].rstrip("\\")
    folder = shell.NameSpace(base_path)
    if folder is None:
        return None

    last_item = None
    for part in parts:
        clean_part = part[4:] if part.lower().startswith("sid-") else part
        part_clean = clean_part.strip("{}")
        target_name = None
        if "," in part_clean:
            sid_parts = part_clean.split(",")
            if len(sid_parts) >= 2:
                target_name = sid_parts[1].strip()

        found_item = None
        for item in folder.Items():
            item_name = str(item.Name)
            if target_name is not None:
                if item_name == target_name:
                    found_item = item
                    break
            else:
                try:
                    if part_clean.lower() in str(item.Path).lower():
                        found_item = item
                        break
                except Exception:  # noqa: BLE001
                    continue

        if found_item is None:
            return None
        last_item = found_item
        if found_item.IsFolder:
            sub_folder = found_item.GetFolder
            if sub_folder is not None:
                folder = sub_folder

    return last_item


def _split_shell_path(path_str):
    r"""
    Descompon un path shell MTP en segments navegables.
    Ex: ::{CLSID}\\\?\usb#...\SID-{NUM,Nom,Mida}\{GUID1}\{GUID2}
    -> ['SID-{NUM,Nom,Mida}', '{GUID1}', '{GUID2}']
    """
    path_str = str(path_str)
    parts = []
    current = path_str
    while True:
        low = current.lower()
        sid_idx = low.find("\\sid-")
        guid_idx = low.find("\\{")
        if sid_idx == -1 and guid_idx == -1:
            break
        idx = sid_idx if sid_idx != -1 and (guid_idx == -1 or sid_idx < guid_idx) else guid_idx
        rest = current[idx + 1:]
        # Trobar el final del segment
        end = len(rest)
        sid_next = rest.lower().find("\\sid-", 5 if rest.lower().startswith("sid-") else 1)
        guid_next = rest.lower().find("\\{", 5 if rest.lower().startswith("sid-") else 1)
        candidates = [e for e in (sid_next, guid_next) if e != -1]
        if candidates:
            end = min(candidates)
        parts.append(rest[:end])
        current = current[idx + 1 + end:]

    return parts
