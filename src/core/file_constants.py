"""
Constants de categorització i tipus de fitxers per JMComander.
Extret de panel.py per complir amb SoC (Separation of Concerns).
"""

import os

FILE_CATEGORIES = {
    "compressed": [
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".iso",
        ".cab",
        ".arj",
        ".lz",
        ".lzma",
    ],
    "video": [
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".mpg",
        ".mpeg",
        ".3gp",
    ],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"],
    "image": [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".svg",
        ".ico",
        ".webp",
        ".tiff",
        ".tif",
        ".psd",
        ".raw",
    ],
    "document": [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".rtf",
        ".odt",
        ".ods",
        ".odp",
    ],
    "code": [
        ".py",
        ".js",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".rb",
        ".go",
        ".rs",
        ".ts",
        ".html",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
    ],
    "executable": [".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".msi"],
    "folder": ["__folder__"],
}

EXTENSION_CATEGORIES = {}
for category, extensions in FILE_CATEGORIES.items():
    for ext in extensions:
        EXTENSION_CATEGORIES[ext] = category

FILE_TYPE_DISPLAY = {
    ".pdf": "PDF",
    ".doc": "Word",
    ".docx": "Word",
    ".xls": "Excel",
    ".xlsx": "Excel",
    ".ppt": "PowerPoint",
    ".pptx": "PowerPoint",
    ".txt": "Text",
    ".rtf": "RTF",
    ".odt": "Text",
    ".ods": "Sheet",
    ".odp": "Slide",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".png": "Image",
    ".gif": "Image",
    ".bmp": "Image",
    ".svg": "Image",
    ".ico": "Icon",
    ".webp": "Image",
    ".tiff": "Image",
    ".tif": "Image",
    ".psd": "Image",
    ".raw": "Image",
    ".mp4": "Video",
    ".avi": "Video",
    ".mkv": "Video",
    ".mov": "Video",
    ".wmv": "Video",
    ".flv": "Video",
    ".webm": "Video",
    ".m4v": "Video",
    ".mpg": "Video",
    ".mpeg": "Video",
    ".3gp": "Video",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".wma": "Audio",
    ".m4a": "Audio",
    ".opus": "Audio",
    ".aiff": "Audio",
    ".zip": "Archive",
    ".rar": "Archive",
    ".7z": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".bz2": "Archive",
    ".xz": "Archive",
    ".iso": "Image",
    ".cab": "Archive",
    ".arj": "Archive",
    ".exe": "Exe",
    ".dll": "DLL",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".ps1": "Script",
    ".sh": "Script",
    ".msi": "Installer",
    ".py": "Python",
    ".js": "JavaScript",
    ".java": "Java",
    ".c": "C",
    ".cpp": "C++",
    ".h": "Header",
    ".hpp": "Header",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

CATEGORY_DISPLAY_NAMES = {
    "compressed": "Arxiu comprimit",
    "video": "Video",
    "audio": "Audio",
    "image": "Imatge",
    "document": "Document",
    "code": "Codi",
    "executable": "Executable",
    "folder": "Carpeta",
    "other": "Altre",
}


def get_file_type_display(filename):
    """Retorna el nom display abreujat del tipus d'arxiu"""
    ext = os.path.splitext(filename)[1].lower()
    return FILE_TYPE_DISPLAY.get(ext, ext[1:].upper() if ext else "File")


def get_file_category(filename):
    """Retorna la categoria d'arxiu basada en l'extensió"""
    ext = os.path.splitext(filename)[1].lower()
    return EXTENSION_CATEGORIES.get(ext, "other")


def get_category_display_name(category):
    """Retorna el nom display de la categoria"""
    return CATEGORY_DISPLAY_NAMES.get(category, "Altre")


def get_extension(filename):
    """Retorna l'extensió de l'arxiu sense el punt"""
    ext = os.path.splitext(filename)[1]
    return ext[1:] if ext else ""
