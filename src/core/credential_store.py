"""Windows Credential Manager per emmagatzemar contrasenyes de forma segura."""

import ctypes
from ctypes import wintypes

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
    ]


def _get_service_name(name):
    return f"JMComander_{name}"


def store_password(service, username, password):
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    target = _get_service_name(service)
    user = f"{username}@{service}"
    blob = password.encode("utf-16-le")
    blob_size = len(blob)
    cred = CREDENTIAL()
    cred.Type = CRED_TYPE_GENERIC
    cred.TargetName = target
    cred.UserName = user
    cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(wintypes.BYTE))
    cred.CredentialBlobSize = blob_size
    cred.Persist = CRED_PERSIST_LOCAL_MACHINE
    result = advapi32.CredWrite(ctypes.byref(cred), 0)
    if not result:
        error = ctypes.get_last_error()
        msg = f"Error guardant credencial: {error}"
        raise OSError(msg)


def get_password(service, username):  # noqa: ARG001
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    target = _get_service_name(service)
    pcred = ctypes.POINTER(CREDENTIAL)()
    result = advapi32.CredRead(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pcred))
    if not result:
        return None
    try:
        cred = pcred.contents
        blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
        return blob.decode("utf-16-le")
    finally:
        advapi32.CredFree(pcred)


def delete_password(service, username):  # noqa: ARG001
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    target = _get_service_name(service)
    result = advapi32.CredDelete(target, CRED_TYPE_GENERIC, 0)
    return bool(result)
