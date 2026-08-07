import ctypes
import os
import shutil
from ctypes import wintypes


def sumar(a, b):
    return a + b


_FO_DELETE = 0x0003
_FOF_ALLOWUNDO = 0x0040
_FOF_NOCONFIRMATION = 0x0010
_FOF_NOERRORUI = 0x0400
_FOF_SILENT = 0x0004


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def _enviar_a_papelera(ruta):
    if os.name != "nt":
        raise OSError("Enviar a la Papelera solo está disponible en Windows")
    operacion = _SHFILEOPSTRUCTW()
    operacion.hwnd = None
    operacion.wFunc = _FO_DELETE
    operacion.pFrom = ctypes.cast(
        ctypes.create_unicode_buffer(ruta + "\0"), wintypes.LPCWSTR
    )
    operacion.pTo = None
    operacion.fFlags = (
        _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_NOERRORUI | _FOF_SILENT
    )
    operacion.fAnyOperationsAborted = False
    operacion.hNameMappings = None
    operacion.lpszProgressTitle = None
    resultado = ctypes.windll.shell32.SHFileOperationW(
        ctypes.byref(operacion)
    )
    if resultado != 0:
        raise OSError(
            f"no se pudo enviar a la Papelera (código {resultado})"
        )


def copiar_archivos(origen, archivos, destino, on_progreso=None):
    if not isinstance(origen, str) or not origen:
        raise ValueError("origen debe ser una ruta de texto no vacía")
    if not isinstance(destino, str) or not destino:
        raise ValueError("destino debe ser una ruta de texto no vacía")
    if isinstance(archivos, (str, bytes, bytearray)):
        raise TypeError("archivos debe ser una colección de nombres, no texto")
    try:
        lista = list(archivos)
    except TypeError:
        raise TypeError("archivos debe ser una colección iterable")
    copiados = []
    omitidos = []
    errores = []
    total = len(lista)
    for indice, nombre in enumerate(lista):
        if isinstance(nombre, str) and nombre:
            ruta = os.path.join(origen, nombre)
            if not os.path.isfile(ruta):
                errores.append((ruta, "archivo no encontrado"))
            else:
                destino_archivo = os.path.join(destino, nombre)
                if os.path.exists(destino_archivo):
                    omitidos.append(ruta)
                else:
                    try:
                        os.makedirs(
                            os.path.dirname(destino_archivo), exist_ok=True
                        )
                        shutil.copy2(ruta, destino_archivo)
                        copiados.append(ruta)
                    except OSError as exc:
                        errores.append((ruta, str(exc)))
        if on_progreso is not None:
            on_progreso(indice + 1, total)
    return {
        "copiados": copiados,
        "omitidos": omitidos,
        "errores": errores,
    }


def pegar_archivos(archivos, destino, on_progreso=None):
    if not isinstance(destino, str) or not destino:
        raise ValueError("destino debe ser una ruta de texto no vacía")
    if isinstance(archivos, (str, bytes, bytearray)):
        raise TypeError("archivos debe ser una colección de rutas, no texto")
    try:
        lista = list(archivos)
    except TypeError:
        raise TypeError("archivos debe ser una colección iterable")
    copiados = []
    omitidos = []
    errores = []
    total = len(lista)
    for indice, ruta in enumerate(lista):
        if isinstance(ruta, str) and ruta:
            if not os.path.isfile(ruta):
                errores.append((ruta, "archivo no encontrado"))
            else:
                destino_archivo = os.path.join(destino, os.path.basename(ruta))
                if os.path.exists(destino_archivo):
                    omitidos.append(ruta)
                else:
                    try:
                        shutil.copy2(ruta, destino_archivo)
                        copiados.append(ruta)
                    except OSError as exc:
                        errores.append((ruta, str(exc)))
        if on_progreso is not None:
            on_progreso(indice + 1, total)
    return {
        "copiados": copiados,
        "omitidos": omitidos,
        "errores": errores,
    }


def eliminar_archivos(archivos, on_progreso=None):
    if isinstance(archivos, (str, bytes, bytearray)):
        raise TypeError("archivos debe ser una colección de rutas, no texto")
    try:
        lista = list(archivos)
    except TypeError:
        raise TypeError("archivos debe ser una colección iterable")
    eliminados = []
    omitidos = []
    errores = []
    total = len(lista)
    for indice, ruta in enumerate(lista):
        if isinstance(ruta, str) and ruta:
            if not os.path.isfile(ruta):
                errores.append((ruta, "archivo no encontrado"))
            else:
                try:
                    _enviar_a_papelera(ruta)
                    eliminados.append(ruta)
                except OSError as exc:
                    errores.append((ruta, str(exc)))
        if on_progreso is not None:
            on_progreso(indice + 1, total)
    return {
        "eliminados": eliminados,
        "omitidos": omitidos,
        "errores": errores,
    }
