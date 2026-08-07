import os
import shutil


def sumar(a, b):
    return a + b


def copiar_archivos(origen, archivos, destino):
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
    for nombre in lista:
        if not isinstance(nombre, str) or not nombre:
            continue
        ruta = os.path.join(origen, nombre)
        if not os.path.isfile(ruta):
            errores.append((ruta, "archivo no encontrado"))
            continue
        destino_archivo = os.path.join(destino, nombre)
        if os.path.exists(destino_archivo):
            omitidos.append(ruta)
            continue
        try:
            os.makedirs(os.path.dirname(destino_archivo), exist_ok=True)
            shutil.copy2(ruta, destino_archivo)
            copiados.append(ruta)
        except OSError as exc:
            errores.append((ruta, str(exc)))
    return {
        "copiados": copiados,
        "omitidos": omitidos,
        "errores": errores,
    }


def pegar_archivos(archivos, destino):
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
    for ruta in lista:
        if not isinstance(ruta, str) or not ruta:
            continue
        if not os.path.isfile(ruta):
            errores.append((ruta, "archivo no encontrado"))
            continue
        destino_archivo = os.path.join(destino, os.path.basename(ruta))
        if os.path.exists(destino_archivo):
            omitidos.append(ruta)
            continue
        try:
            shutil.copy2(ruta, destino_archivo)
            copiados.append(ruta)
        except OSError as exc:
            errores.append((ruta, str(exc)))
    return {
        "copiados": copiados,
        "omitidos": omitidos,
        "errores": errores,
    }
