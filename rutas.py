import os
import sys


def _directorio_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


RUTA_RAIZ = _directorio_base()


def ruta_raiz():
    return RUTA_RAIZ


def ruta_biblioteca():
    return os.path.join(ruta_raiz(), "biblioteca.db")


def ruta_carpeta_miniaturas():
    return os.path.join(ruta_raiz(), "miniaturas")


def ruta_carpeta_exploracion():
    return os.path.join(ruta_raiz(), "miniaturas", "exploracion")


def ruta_carpeta_videos():
    return os.path.join(ruta_raiz(), "videos_prueba")


def ruta_configuracion():
    return os.path.join(ruta_raiz(), "configuracion.json")


def ruta_video_existente(carpeta, nombre):
    """Devuelve la ruta absoluta de un video si la carpeta y el archivo existen.

    La UI delega aqui la comprobacion de existencia para no acceder
    directamente al filesystem. Devuelve `None` si `carpeta` no es una
    carpeta valida, `nombre` no es texto o el archivo no existe.
    """
    if not isinstance(nombre, str) or not nombre:
        return None
    if not isinstance(carpeta, str) or not carpeta:
        return None
    ruta = os.path.join(carpeta, nombre)
    if not os.path.isdir(carpeta) or not os.path.isfile(ruta):
        return None
    return ruta


def normalizar_carpeta(carpeta):
    """Normaliza una carpeta a forma canónica (abspath + normpath + normcase).

    Helper puro de rutas, arquitectónicamente aceptado para que la UI
    compare carpetas sin acceder directamente a os.path. No toca FS
    (no verifica existencia), solo normaliza la cadena.
    """
    if not isinstance(carpeta, str) or not carpeta.strip():
        return None
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(carpeta.strip())))
    except Exception:
        return None


def carpetas_iguales(a, b):
    """True si dos carpetas normalizadas coinciden (comparación pura, sin FS).

    Usa normalizar_carpeta internamente; no verifica existencia en disco.
    Reemplaza el uso directo de os.path.* en la UI para decidir si la vista
    actual coincide con la carpeta destino de una operación.
    """
    na = normalizar_carpeta(a)
    nb = normalizar_carpeta(b)
    if na is None or nb is None:
        return False
    return na == nb


def listar_subcarpetas(carpeta):
    """Lista subcarpetas inmediatas de forma segura y ordenada (B7.10).

    Helper mínimo de filesystem centralizado para que PanelOrganizacion
    no acceda directamente a os.listdir/isdir. No recursivo, solo hijas
    directas. Orden determinista case-insensitive.

    Returns:
        dict con claves:
          - ok: bool
          - valido: bool (True si carpeta existe y es dir accesible)
          - subcarpetas: list[str] nombres (vacía si error)
          - error: str|None mensaje descriptivo si no ok
    No lanza excepciones no controladas; diagnostica errores visibles.
    """
    if not isinstance(carpeta, str) or not carpeta.strip():
        return {"ok": False, "valido": False, "subcarpetas": [], "error": "ruta vacía"}
    carpeta = carpeta.strip()
    try:
        es_dir = os.path.isdir(carpeta)
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "valido": False, "subcarpetas": [], "error": f"no accesible: {exc}"}
    if not es_dir:
        return {"ok": False, "valido": False, "subcarpetas": [], "error": "destino no existe o no es carpeta"}
    try:
        entradas = os.listdir(carpeta)
    except PermissionError as exc:
        return {"ok": False, "valido": False, "subcarpetas": [], "error": f"sin permiso: {exc}"}
    except OSError as exc:
        return {"ok": False, "valido": False, "subcarpetas": [], "error": f"no accesible: {exc}"}
    subcarpetas = []
    omitidas = 0
    for nombre in entradas:
        try:
            ruta_hija = os.path.join(carpeta, nombre)
        except (TypeError, ValueError, OSError) as exc:
            omitidas += 1
            print(f"[B7.10] listar_subcarpetas join omitida {nombre!r}: {exc}")
            continue
        try:
            if os.path.isdir(ruta_hija):
                subcarpetas.append(nombre)
        except (OSError, PermissionError, TypeError, ValueError) as exc:
            omitidas += 1
            print(f"[B7.10] listar_subcarpetas isdir omitida {ruta_hija!r}: {exc}")
            continue
    if omitidas:
        print(f"[B7.10] listar_subcarpetas omitidas {omitidas} entradas no consultables en {carpeta!r}")
    # Orden determinista case-insensitive; subcarpetas ya validadas como str
    try:
        subcarpetas.sort(key=lambda s: s.lower())
    except (TypeError, ValueError, AttributeError) as exc:
        print(f"[B7.10] listar_subcarpetas sort error: {exc}")
        subcarpetas.sort()
    return {"ok": True, "valido": True, "subcarpetas": subcarpetas, "error": None}


def carpeta_padre(carpeta):
    """Devuelve la carpeta padre normalizada o None si no tiene padre/raíz.

    Helper puro de rutas (sin FS), para navegación del destino.
    """
    if not isinstance(carpeta, str) or not carpeta.strip():
        return None
    try:
        normal = os.path.normpath(os.path.abspath(carpeta.strip()))
    except (TypeError, ValueError, OSError, AttributeError) as exc:
        print(f"[B7.10] carpeta_padre normalización error: {exc}")
        return None
    try:
        padre = os.path.dirname(normal)
    except (TypeError, ValueError, AttributeError) as exc:
        print(f"[B7.10] carpeta_padre dirname error: {exc}")
        return None
    if not padre or padre == normal:
        return None
    # Evitar que padre sea igual (raíz)
    try:
        if os.path.normcase(padre) == os.path.normcase(normal):
            return None
    except (TypeError, ValueError, AttributeError, OSError) as exc:
        print(f"[B7.10] carpeta_padre normcase error: {exc}")
        return None
    return padre
