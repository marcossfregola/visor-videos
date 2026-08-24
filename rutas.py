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


def resolver_destino_drop(destino, objetivo_nombre):
    """B7.12 — resuelve destino efectivo para futuro soltado sin FS duplicado.

    Si objetivo_nombre es None/vacío retorna destino normalizado.
    Si objetivo_nombre es subcarpeta hija válida, retorna join normalizado.
    Valida que nombre no contenga separadores ni sea '.'/'..' ni vacío.
    No verifica existencia en disco; solo normaliza ruta pura.
    Retorna None si destino inválido o nombre inválido con separadores.
    Reutilizable por futuro gesto de arrastre sin tocar PanelOrganizacion.
    """
    if not isinstance(destino, str) or not destino.strip():
        return None
    destino_norm = destino.strip()
    try:
        destino_norm = os.path.normpath(destino_norm)
    except (TypeError, ValueError, OSError, AttributeError) as exc:
        print(f"[B7.12] resolver_destino_drop destino norm error: {exc}")
        return None
    if objetivo_nombre is None:
        return destino_norm
    if not isinstance(objetivo_nombre, str):
        try:
            objetivo_nombre = str(objetivo_nombre)
        except (ValueError, TypeError, RuntimeError) as exc:
            print(f"[B7.12] resolver_destino_drop conversión error: {exc}")
            return None
    objetivo_nombre = objetivo_nombre.strip()
    if not objetivo_nombre:
        return destino_norm
    if objetivo_nombre in (".", ".."):
        return None
    if "/" in objetivo_nombre or "\\" in objetivo_nombre:
        return None
    if objetivo_nombre in ("(vacío)", "(cargando…)"):
        return None
    try:
        combinado = os.path.join(destino_norm, objetivo_nombre)
        combinado = os.path.normpath(combinado)
    except (TypeError, ValueError, OSError, AttributeError) as exc:
        print(f"[B7.12] resolver_destino_drop join error: {exc}")
        return None
    # Seguridad: debe ser hijo directo (no traversal que salga)
    try:
        padre_combinado = os.path.dirname(combinado)
        if os.path.normcase(padre_combinado) != os.path.normcase(destino_norm):
            # si no es hijo directo, rechazar (posible nombre con .. encubierto ya filtrado)
            return None
    except (TypeError, ValueError, AttributeError, OSError) as exc:
        print(f"[B7.12] resolver_destino_drop padre check error: {exc}")
        return None
    return combinado


def normalizar_ruta_clave(ruta):
    """B8.1 — normalización centralizada de ruta para identidad del catálogo.

    Contrato estable en Windows:
    - elimina espacios exteriores del texto de entrada;
    - convierte a absoluta;
    - aplica normpath;
    - aplica normcase;
    - devuelve representación estable apta para identidad.

    Única función oficial para clave técnica `ruta_normalizada`.
    La ruta real/original sigue almacenándose en `videos.ruta`.
    """
    if not isinstance(ruta, str):
        raise TypeError("ruta debe ser texto")
    texto = ruta.strip()
    if not texto:
        raise ValueError("ruta no puede estar vacía")
    try:
        absoluta = os.path.abspath(texto)
        normal = os.path.normpath(absoluta)
        estable = os.path.normcase(normal)
    except Exception as exc:
        raise ValueError(f"no se pudo normalizar ruta {ruta!r}: {exc}") from None
    return estable


def validar_destino_drop_completo(destino_completo):
    """B7.12 — valida destino completo puro (sin FS): no vacío y no contiene ilegales.

    No verifica existencia en disco; la validez FS la resuelve TareaListarSubcarpetasDestino.
    Retorna True si es ruta plausible (str no vacío, no None).
    """
    if not isinstance(destino_completo, str) or not destino_completo.strip():
        return False
    # Rechazar rutas con caracteres nulos; delegar resto a FS
    if "\x00" in destino_completo:
        return False
    return True
