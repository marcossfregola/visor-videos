"""Servicio B7.3 — creación segura de una carpeta hija directa.

Contrato:
- Validación Windows estricta reutilizando nombres.py (sin sanitización silenciosa).
- Solo una carpeta hija directa; rechaza separadores/ruta anidada.
- Colisión case-insensitive (Windows) sin sobrescribir.
- Creación atómica via os.mkdir con manejo de carrera (FileExistsError).
- No toca SQLite/catálogo/miniaturas.
- No borra nada en compensación: si mkdir ok, operación terminó.
"""

import os

import nombres as nombres_mod


class CrearCarpetaError(Exception):
    pass


class ValidacionError(CrearCarpetaError):
    pass


class ColisionError(CrearCarpetaError):
    pass


def validar_nombre_carpeta(nombre):
    """Valida nombre de carpeta (un solo componente) B7.3.

    Rechaza conservadoramente:
      - no str / vacío / solo espacios
      - leading/trailing espacios
      - termina en punto o espacio
      - "." o ".."
      - contiene separadores '/' o '\\'
      - caracteres inválidos Windows <>:"/\\|?* y controles 0..31
      - nombres reservados Windows (CON, PRN, AUX, NUL, COM1..9, LPT1..9)
      - longitud > 255
      - forma que sanitizar_componente alteraría (defensivo)
    Retorna nombre validado tal cual si pasa.
    """
    if not isinstance(nombre, str):
        raise ValidacionError("nombre debe ser texto")
    # Vacío tras strip -> vacío
    if not nombre.strip():
        raise ValidacionError("nombre vacío")
    # Leading/trailing espacios -> inválido (Windows)
    if nombre != nombre.strip():
        raise ValidacionError("nombre no puede tener espacios al inicio o al final")
    # Termina en punto o espacio
    if nombre.endswith(" ") or nombre.endswith("."):
        raise ValidacionError("nombre no puede terminar en punto o espacio")
    # Componentes . / ..
    if nombre in (".", ".."):
        raise ValidacionError("nombre no puede ser '.' o '..'")
    # Separadores / ruta anidada
    if "/" in nombre or "\\" in nombre:
        raise ValidacionError("nombre no puede contener separadores de ruta")
    # Si contiene os.sep adicional (ya cubierto) pero por si plataforma distinta
    if os.sep in nombre and os.sep not in ("/", "\\"):
        raise ValidacionError("nombre no puede contener separador de ruta")
    # Longitud
    if len(nombre) > nombres_mod.MAX_COMPONENTE:
        raise ValidacionError(f"nombre demasiado largo ({len(nombre)} > {nombres_mod.MAX_COMPONENTE})")
    # Caracteres inválidos y controles
    for ch in nombre:
        if ch in nombres_mod.CARACTERES_INVALIDOS or (0 <= ord(ch) <= 31):
            raise ValidacionError(f"nombre contiene carácter inválido {ch!r}")
    # rstrip punto/espacio defensivo
    if nombre.rstrip(" .") != nombre:
        raise ValidacionError("nombre no puede terminar en punto o espacio")
    # Reservado
    # _es_reservado espera stem antes del primer punto; para carpeta sin extensión aplica igual
    if nombres_mod._es_reservado(nombre):
        raise ValidacionError(f"nombre reservado Windows: {nombre!r}")
    # Sanitización defensiva: si sanitizar altera, es inválido
    try:
        sanit = nombres_mod.sanitizar_componente(nombre)
    except Exception as exc:
        raise ValidacionError(str(exc)) from exc
    if sanit != nombre:
        raise ValidacionError("nombre contiene forma no permitida Windows")
    return nombre


def crear_carpeta(carpeta_padre, nombre):
    """Crea una carpeta hija directa de forma segura (B7.3).

    Pasos:
      1. Validar carpeta_padre existe y es directorio.
      2. Validar nombre vía validar_nombre_carpeta.
      3. Construir ruta destino (abspath, join).
      4. Prevalidar colisión case-insensitive (listdir lower) + os.path.exists.
      5. os.mkdir (capturando FileExistsError como ColisionError).
    Retorna dict {ok, ruta, padre, nombre, error}
    No toca SQLite. No borra tras éxito.
    """
    if not isinstance(carpeta_padre, str) or not carpeta_padre.strip():
        raise ValidacionError("carpeta_padre debe ser texto no vacío")
    # Normalizar padre a abspath para coherencia
    # Preservar si es absoluta: abspath; si relativa, también abspath
    carpeta_padre_abs = os.path.abspath(carpeta_padre.strip())
    # Validar existencia y tipo
    if not os.path.exists(carpeta_padre_abs):
        raise ValidacionError(f"carpeta padre no existe: {carpeta_padre!r}")
    if not os.path.isdir(carpeta_padre_abs):
        raise ValidacionError(f"carpeta padre no es directorio: {carpeta_padre!r}")

    nombre_validado = validar_nombre_carpeta(nombre)

    nueva_ruta = os.path.join(carpeta_padre_abs, nombre_validado)
    # Normalizar nueva_ruta a abspath (join ya lo es si padre es abs)
    nueva_ruta = os.path.abspath(nueva_ruta)

    # Prevalidación colisión case-insensitive determinista (simula Windows en Linux)
    try:
        entradas = os.listdir(carpeta_padre_abs)
    except OSError as exc:
        raise CrearCarpetaError(f"no se pudo listar carpeta padre: {exc}") from exc

    nombre_lower = nombre_validado.lower()
    # Usar normcase para Windows pero lower para determinismo cross-platform
    # Detectar colisión comparando lower y también normcase
    for entrada in entradas:
        if entrada.lower() == nombre_lower:
            raise ColisionError(f"ya existe entrada con mismo nombre (case-insensitive): {entrada!r} colisiona con {nombre_validado!r}")
        # Extra: normcase check en Windows (case-insensitive ya)
        try:
            if os.path.normcase(entrada) == os.path.normcase(nombre_validado):
                raise ColisionError(f"ya existe entrada (normcase): {entrada!r}")
        except Exception:
            pass

    # También verificar existencia directa (cubre archivos y carpetas exactas y races donde listing desfasado)
    if os.path.exists(nueva_ruta):
        raise ColisionError(f"ya existe archivo o carpeta en destino: {nueva_ruta!r}")

    # Creación atómica
    try:
        os.mkdir(nueva_ruta)
    except FileExistsError as exc:
        raise ColisionError(f"colisión carrera: ya existe {nueva_ruta!r}") from exc
    except PermissionError as exc:
        raise CrearCarpetaError(f"sin permisos para crear carpeta: {exc}") from exc
    except OSError as exc:
        raise CrearCarpetaError(f"fallo al crear carpeta: {exc}") from exc

    # Verificación post
    if not os.path.isdir(nueva_ruta):
        raise CrearCarpetaError(f"ruta creada no es directorio: {nueva_ruta!r}")

    return {
        "ok": True,
        "ruta": nueva_ruta,
        "padre": carpeta_padre_abs,
        "nombre": nombre_validado,
        "error": None,
    }
