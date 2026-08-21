import math
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime

from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

EXTENSIONES = {".mp4", ".mkv", ".avi"}
EXTENSION_MINIATURA = ".jpg"
CANTIDAD_PREVIEWS_POR_DEFECTO = 3
CANTIDAD_PREVIEWS = CANTIDAD_PREVIEWS_POR_DEFECTO


def configurar_cantidad_previews(n):
    global CANTIDAD_PREVIEWS
    if isinstance(n, int) and n > 0:
        CANTIDAD_PREVIEWS = n
COLUMNAS_EXTRA = [
    ("duracion_segundos", "REAL"),
    ("ancho", "INTEGER"),
    ("alto", "INTEGER"),
    ("codec_video", "TEXT"),
    ("cantidad_miniaturas", "INTEGER"),
    ("tamano_bytes", "INTEGER"),
    ("mtime_ns", "INTEGER"),
]

ORDEN_CRITERIO_DEFAULT = "nombre"
ORDEN_DIRECCION_DEFAULT = "asc"

# Whitelists cerradas de dominio (B6.2). La UI/config solo pueden expresar
# orden mediante estas claves y direcciones; ninguna de ellas es SQL.
ORDEN_CRITERIOS = (
    "nombre",
    "duracion",
    "resolucion",
    "codec",
    "tamano",
    "fecha_importacion",
)
ORDEN_DIRECCIONES = ("asc", "desc")

# Paleta cerrada de clasificación por color (B6.3). Las claves son estables y
# se persisten en SQLite (`color TEXT NULL` en `marcadores_video` y
# `segmentos_video`). La misma paleta sirve para marcadores y segmentos;
# `NULL` conserva los colores históricos (marcador rojo, segmento azul).
# Es la única fuente de verdad de la paleta: la UI y la configuración solo
# pueden expresar colores mediante estas claves.
COLORES_CLASIFICACION = (
    ("rojo", 229, 57, 53),
    ("naranja", 255, 152, 0),
    ("amarillo", 251, 192, 45),
    ("verde", 76, 175, 80),
    ("azul", 33, 150, 243),
    ("violeta", 156, 39, 176),
)
CLAVES_COLOR_CLASIFICACION = frozenset(
    clave for clave, *_resto in COLORES_CLASIFICACION
)


def color_rgb(clave):
    """Devuelve `(r, g, b)` de una clave de la paleta o `None` si no existe."""
    for candidata, r, g, b in COLORES_CLASIFICACION:
        if candidata == clave:
            return (r, g, b)
    return None


def _validar_color_clasificacion(clave):
    """Valida una clave de color: `None` (quitar color) o clave estable."""
    if clave is None:
        return None
    if not isinstance(clave, str):
        raise TypeError("color debe ser texto o None")
    if clave not in CLAVES_COLOR_CLASIFICACION:
        raise ValueError(f"color no reconocido: {clave!r}")
    return clave

# Expresiones SQL internas (constantes cerradas): primer término detecta el
# "nulo" para colocar siempre los NULL al final en ASC y DESC; el segundo es
# el criterio de orden; el desempate final estable es siempre `id ASC`.
_ORDEN_EXPRESION_NULO = {
    "nombre": "(nombre IS NULL)",
    "duracion": "(duracion_segundos IS NULL)",
    "resolucion": "(ancho IS NULL OR alto IS NULL)",
    "codec": "(codec_video IS NULL)",
    "tamano": "(tamano_bytes IS NULL)",
    "fecha_importacion": "(fecha_importacion IS NULL)",
}
_ORDEN_EXPRESION_CRITERIO = {
    "nombre": "nombre",
    "duracion": "duracion_segundos",
    "resolucion": "(ancho * alto)",
    "codec": "codec_video",
    "tamano": "tamano_bytes",
    "fecha_importacion": "fecha_importacion",
}

_ESCANEO_RECURSIVO = False


def configurar_escaneo_recursivo(activado):
    global _ESCANEO_RECURSIVO
    _ESCANEO_RECURSIVO = activado


def _nombre_seguro(nombre):
    return nombre.replace(os.sep, "_").replace("/", "_")


def escanear_videos(carpeta):
    if _ESCANEO_RECURSIVO:
        return sorted(
            os.path.relpath(os.path.join(raiz, nombre), carpeta)
            for raiz, _, archivos in os.walk(carpeta)
            for nombre in archivos
            if os.path.splitext(nombre)[1].lower() in EXTENSIONES
        )
    return sorted(
        nombre for nombre in os.listdir(carpeta)
        if os.path.splitext(nombre)[1].lower() in EXTENSIONES
    )

def preparar_registros_basicos(videos, carpeta):
    if isinstance(videos, (str, bytes, bytearray)):
        raise TypeError("videos debe ser una colección de nombres, no texto")
    try:
        lista = list(videos)
    except TypeError:
        raise TypeError("videos debe ser una colección iterable") from None
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    fecha = datetime.now().isoformat()
    registros = []
    for nombre in lista:
        registros.append(
            {
                "nombre": nombre,
                "ruta": os.path.join(carpeta, nombre),
                "extension": os.path.splitext(nombre)[1].lower(),
                "fecha_importacion": fecha,
            }
        )
    return registros

CLAVES_METADATOS_FFPROBE = ("duracion_segundos", "ancho", "alto", "codec_video")


def _normalizar_ruta(ruta):
    if ruta is None:
        return None
    return os.path.normcase(os.path.normpath(ruta))


def _normalizar_ruta_absoluta(ruta):
    """Normalización estable para comparar rutas (B4.5 Etapa 3)."""
    if ruta is None:
        return None
    return os.path.normcase(
        os.path.normpath(os.path.abspath(ruta))
    )


def _metadata_ffprobe_utilizable(datos):
    """Indica si la metadata persistida sirve para reutilizarse sin FFprobe."""
    if not isinstance(datos, dict):
        return False
    if not _duracion_utilizable(datos.get("duracion_segundos")):
        return False
    ancho = datos.get("ancho")
    alto = datos.get("alto")
    if not (isinstance(ancho, int) and not isinstance(ancho, bool) and ancho > 0):
        return False
    if not (isinstance(alto, int) and not isinstance(alto, bool) and alto > 0):
        return False
    codec = datos.get("codec_video")
    return isinstance(codec, str) and bool(codec.strip())


def _metadata_reutilizable(registro, ruta_actual, stat):
    """Criterio exacto de reutilización de metadata sin FFprobe (B4.5 Etapa 3).

    Reutiliza solo si: existe registro, `mtime_ns` no es NULL, la ruta
    normalizada coincide, el tamaño coincide, el `mtime_ns` coincide y la
    metadata almacenada es utilizable.
    """
    if not isinstance(registro, dict):
        return False
    if registro.get("mtime_ns") is None:
        return False
    if _normalizar_ruta_absoluta(registro.get("ruta")) != _normalizar_ruta_absoluta(
        ruta_actual
    ):
        return False
    if not isinstance(stat, dict):
        return False
    if stat.get("tamano_bytes") != registro.get("tamano_bytes"):
        return False
    if stat.get("mtime_ns") != registro.get("mtime_ns"):
        return False
    return _metadata_ffprobe_utilizable(registro)


def combinar_registros_con_ffprobe(videos, carpeta, resultado_ffprobe):
    registros = preparar_registros_basicos(videos, carpeta)
    por_ruta = {}
    for item in ((resultado_ffprobe or {}).get("resultados") or []):
        if not isinstance(item, dict):
            continue
        ruta = _normalizar_ruta(item.get("ruta"))
        if ruta is None:
            continue
        datos = item.get("datos")
        por_ruta[ruta] = datos if isinstance(datos, dict) else None
    for registro in registros:
        datos = por_ruta.get(_normalizar_ruta(registro["ruta"]))
        for clave in CLAVES_METADATOS_FFPROBE:
            registro[clave] = datos.get(clave) if datos is not None else None
    return registros


def combinar_registros_con_miniaturas(registros, resultado_miniaturas):
    if isinstance(registros, (str, bytes, bytearray)):
        raise TypeError("registros debe ser una colección, no texto")
    try:
        lista = [dict(r) for r in list(registros)]
    except TypeError:
        raise TypeError("registros debe ser una colección iterable") from None
    por_ruta = {}
    for item in ((resultado_miniaturas or {}).get("resultados") or []):
        if not isinstance(item, dict):
            continue
        ruta = _normalizar_ruta(item.get("ruta"))
        if ruta is None:
            continue
        cantidad = item.get("cantidad_miniaturas")
        por_ruta[ruta] = cantidad if isinstance(cantidad, int) else None
    for registro in lista:
        registro["cantidad_miniaturas"] = por_ruta.get(
            _normalizar_ruta(registro.get("ruta"))
        )
    return lista


def _tamano_archivo(ruta):
    try:
        return os.path.getsize(ruta)
    except OSError:
        return None


def obtener_tamanos_archivos(videos, carpeta, on_progreso=None):
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    if not os.path.isdir(carpeta):
        raise FileNotFoundError(f"Carpeta no encontrada: {carpeta}")
    if isinstance(videos, (str, bytes, bytearray)):
        raise TypeError("videos debe ser una colección de nombres, no texto")
    try:
        lista = list(videos)
    except TypeError:
        raise TypeError("videos debe ser una colección iterable") from None
    rutas = [os.path.join(carpeta, nombre) for nombre in lista]
    resultados = []
    total = len(rutas)
    for indice, ruta in enumerate(rutas):
        tamano = None
        mtime_ns = None
        try:
            st = os.stat(ruta)
            tamano = st.st_size
            mtime_ns = st.st_mtime_ns
        except OSError:
            pass
        resultados.append(
            {"ruta": ruta, "tamano_bytes": tamano, "mtime_ns": mtime_ns}
        )
        if on_progreso is not None:
            on_progreso(indice + 1, total)
    return {
        "rutas": rutas,
        "resultados": resultados,
        "procesados": len(resultados),
        "con_tamano": sum(1 for r in resultados if r["tamano_bytes"] is not None),
        "sin_tamano": sum(1 for r in resultados if r["tamano_bytes"] is None),
    }


def combinar_registros_con_tamanos(registros, resultado_tamanos):
    if isinstance(registros, (str, bytes, bytearray)):
        raise TypeError("registros debe ser una colección, no texto")
    try:
        lista = [dict(r) for r in list(registros)]
    except TypeError:
        raise TypeError("registros debe ser una colección iterable") from None
    por_ruta = {}
    for item in ((resultado_tamanos or {}).get("resultados") or []):
        if not isinstance(item, dict):
            continue
        ruta = _normalizar_ruta(item.get("ruta"))
        if ruta is None:
            continue
        tamano = item.get("tamano_bytes")
        mtime = item.get("mtime_ns")
        por_ruta[ruta] = {
            "tamano_bytes": tamano if isinstance(tamano, int) else None,
            "mtime_ns": mtime if isinstance(mtime, int) else None,
        }
    for registro in lista:
        datos = por_ruta.get(_normalizar_ruta(registro.get("ruta")))
        registro["tamano_bytes"] = (
            datos["tamano_bytes"] if datos else None
        )
        registro["mtime_ns"] = datos["mtime_ns"] if datos else None
    return lista


def _asegurar_columnas_videos(conn):
    """Migración aditiva e idempotente de las columnas extra de `videos`."""
    existentes = {fila[1] for fila in conn.execute("PRAGMA table_info(videos)")}
    for nombre_col, tipo in COLUMNAS_EXTRA:
        if nombre_col not in existentes:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {nombre_col} {tipo}")


def _asegurar_tablas_derivados(conn):
    """Migración aditiva e idempotente para trazabilidad B6.11 (videos derivados).

    Tablas:
      - videos_derivados: relación original→derivado (uno a uno, un derivado proviene
        de un único original). Sin CASCADE destructivo: la fila persiste aunque el
        original o el derivado desaparezcan físicamente o de `videos` (orfandad
        histórica). `derivado_video_id UNIQUE` previene duplicados; el bloqueo de
        derivado-de-derivado se valida en capa de servicio.
      - videos_derivados_segmentos: segmentos fuente en orden explícito (para
        B6.7/B6.9 un registro, para B6.10 N registros con `orden`).
    Idempotente: CREATE IF NOT EXISTS + índices IF NOT EXISTS.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos_derivados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            derivado_video_id INTEGER NOT NULL UNIQUE,
            original_video_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL,
            derivado_nombre TEXT NOT NULL,
            derivado_ruta TEXT NOT NULL,
            original_nombre TEXT NOT NULL,
            original_ruta TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_derivados_original
        ON videos_derivados(original_video_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_derivados_derivado
        ON videos_derivados(derivado_video_id)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos_derivados_segmentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            derivacion_id INTEGER NOT NULL,
            segmento_id INTEGER NOT NULL,
            orden INTEGER NOT NULL,
            inicio REAL NOT NULL,
            fin REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_derivados_segmentos_derivacion
        ON videos_derivados_segmentos(derivacion_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_derivados_segmentos_orden
        ON videos_derivados_segmentos(derivacion_id, orden)
    """)


def conectar_bd(ruta_db=None):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    conn = sqlite3.connect(ruta_db)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL
        )
    """)
    _asegurar_columnas_videos(conn)
    _asegurar_tabla_marcadores(conn)
    _asegurar_tabla_segmentos(conn)
    _asegurar_tablas_derivados(conn)
    return conn


def _asegurar_columna_color(conn, tabla):
    """Migración aditiva e idempotente de `color TEXT NULL` (B6.3).

    Añade la columna si falta; no toca datos existentes. Los registros
    históricos quedan en `NULL` (colores por defecto: marcador rojo,
    segmento azul).
    """
    existentes = {
        fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")
    }
    if "color" not in existentes:
        conn.execute(f"ALTER TABLE {tabla} ADD COLUMN color TEXT NULL")


def _asegurar_tabla_marcadores(conn):
    """Migración aditiva e idempotente de la tabla de marcadores (B4.2).

    Crea `marcadores_video` (y su índice) si no existen y añade la columna
    `color` (B6.3). No activa `PRAGMA foreign_keys` ni usa `ON DELETE
    CASCADE`: los marcadores son datos del usuario y su coherencia con
    `videos.id` se gestiona en la capa de servicio, no por borrado
    automático.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marcadores_video (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            tiempo REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_marcadores_video_video_id_tiempo
        ON marcadores_video(video_id, tiempo)
    """)
    _asegurar_columna_color(conn, "marcadores_video")

def _asegurar_tabla_segmentos(conn):
    """Migración aditiva e idempotente de la tabla de segmentos (B5.1).

    Crea `segmentos_video` (y su índice) si no existen y añade la columna
    `color` (B6.3). No activa `PRAGMA foreign_keys` ni usa `ON DELETE
    CASCADE`: los segmentos son datos del usuario y su coherencia con
    `videos.id` se gestiona en la capa de servicio, no por borrado
    automático (misma política de orfandad tolerada que los marcadores).
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS segmentos_video (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            inicio REAL NOT NULL,
            fin REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_segmentos_video_video_id_inicio
        ON segmentos_video(video_id, inicio)
    """)
    _asegurar_columna_color(conn, "segmentos_video")

def obtener_datos_ffprobe(ruta):
    try:
        resultado = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name:format=duration",
                "-of", "default=noprint_wrappers=1",
                ruta,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            **_ARGS_SIN_CONSOLA,
        )
        if resultado.returncode != 0:
            return None
        datos = {}
        for linea in resultado.stdout.splitlines():
            if "=" in linea:
                clave, valor = linea.split("=", 1)
                datos[clave] = valor
        if "width" not in datos or "height" not in datos or "duration" not in datos or "codec_name" not in datos:
            return None
        return {
            "duracion_segundos": float(datos["duration"]),
            "ancho": int(datos["width"]),
            "alto": int(datos["height"]),
            "codec_video": datos["codec_name"],
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

def ffmpeg_disponible():
    return shutil.which("ffmpeg") is not None
def ruta_miniatura(video, indice=1):
    prefijo = _nombre_seguro(os.path.splitext(video)[0])
    return os.path.join(
        ruta_carpeta_miniaturas(),
        f"{prefijo}_{indice:02d}{EXTENSION_MINIATURA}",
    )


def ruta_preview(video, indice):
    prefijo = _nombre_seguro(os.path.splitext(video)[0])
    return os.path.join(
        ruta_carpeta_miniaturas(),
        f"{prefijo}_preview_{indice:02d}{EXTENSION_MINIATURA}",
    )

def _es_archivo_preview(nombre, video):
    return os.path.splitext(nombre)[0].startswith(
        f"{_nombre_seguro(os.path.splitext(video)[0])}_preview_"
    )

def _duracion_utilizable(duracion):
    """Indica si una duración suministrada puede usarse sin FFprobe.

    Debe ser un número real finito mayor que cero (rechaza `None`, bool,
    no numérico, 0, negativos y NaN/infinito). Si no es utilizable, las
    funciones de generación usan el fallback existente (FFprobe interno).
    """
    if isinstance(duracion, bool) or not isinstance(duracion, (int, float)):
        return False
    try:
        numero = float(duracion)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numero) and numero > 0


def _duracion_de_duraciones(duraciones, nombre, ruta_video):
    """Busca la duración de un video en un mapa por ruta o por nombre."""
    if not isinstance(duraciones, dict):
        return None
    if ruta_video in duraciones:
        return duraciones[ruta_video]
    return duraciones.get(nombre)


def calcular_tiempo_miniatura(duracion):
    if duracion is None or duracion <= 0:
        return 1.0
    return max(0.1, min(duracion * 0.1, 10.0))

def miniatura_vigente(ruta_video, ruta_miniatura):
    if not os.path.isfile(ruta_miniatura):
        return False
    return os.path.getmtime(ruta_miniatura) >= os.path.getmtime(ruta_video)

def generar_miniatura(ruta_video, ruta_miniatura, duracion_segundos=None):
    if _duracion_utilizable(duracion_segundos):
        duracion = duracion_segundos
    else:
        datos = obtener_datos_ffprobe(ruta_video)
        duracion = datos["duracion_segundos"] if datos else None
    tiempo = calcular_tiempo_miniatura(duracion)
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(tiempo),
                "-i", ruta_video,
                "-frames:v", "1", "-q:v", "3",
                ruta_miniatura,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            **_ARGS_SIN_CONSOLA,
        )
        return resultado.returncode == 0 and os.path.isfile(ruta_miniatura)
    except (OSError, subprocess.SubprocessError):
        return False

def siguiente_indice_libre(video):
    indice = 1
    while os.path.isfile(ruta_miniatura(video, indice)):
        indice += 1
    return indice

def miniatura_reutilizable(video, ruta_video):
    prefijo = _nombre_seguro(os.path.splitext(video)[0])
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return None
    for nombre in sorted(os.listdir(carpeta)):
        if (
            os.path.splitext(nombre)[0].startswith(prefijo)
            and not _es_archivo_preview(nombre, video)
        ):
            ruta = os.path.join(carpeta, nombre)
            if miniatura_vigente(ruta_video, ruta):
                return ruta
    return None

def asegurar_miniatura(video, ruta_video, duracion_segundos=None):
    if not ffmpeg_disponible() or os.path.getsize(ruta_video) == 0:
        return 0
    if miniatura_reutilizable(video, ruta_video) is not None:
        return 1
    os.makedirs(ruta_carpeta_miniaturas(), exist_ok=True)
    ruta = ruta_miniatura(video, siguiente_indice_libre(video))
    if os.path.isfile(ruta):
        return 0
    return (
        1
        if generar_miniatura(ruta_video, ruta, duracion_segundos)
        else 0
    )

def asegurar_miniaturas(videos, carpeta, on_progreso=None, duraciones=None):
    if isinstance(videos, (str, bytes, bytearray)):
        raise TypeError("videos debe ser una colección de nombres, no texto")
    try:
        lista = list(videos)
    except TypeError:
        raise TypeError("videos debe ser una colección iterable") from None
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    resultados = []
    total = len(lista)
    for indice, nombre in enumerate(lista):
        ruta_video = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta_video):
            resultados.append(
                {"ruta": ruta_video, "asegurada": 0, "cantidad_miniaturas": 0}
            )
            if on_progreso is not None:
                on_progreso(indice + 1, total)
            continue
        duracion = _duracion_de_duraciones(duraciones, nombre, ruta_video)
        asegurada = asegurar_miniatura(nombre, ruta_video, duracion)
        resultados.append(
            {
                "ruta": ruta_video,
                "asegurada": asegurada,
                "cantidad_miniaturas": contar_miniaturas(nombre),
            }
        )
        if on_progreso is not None:
            on_progreso(indice + 1, total)
    return {
        "rutas": [r["ruta"] for r in resultados],
        "resultados": resultados,
        "procesados": len(resultados),
        "con_miniatura": sum(1 for r in resultados if r["cantidad_miniaturas"] > 0),
        "sin_miniatura": sum(1 for r in resultados if r["cantidad_miniaturas"] == 0),
    }

def contar_miniaturas(video):
    prefijo = _nombre_seguro(os.path.splitext(video)[0])
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return 0
    return sum(
        1 for nombre in os.listdir(carpeta)
        if (
            os.path.splitext(nombre)[0].startswith(prefijo)
            and not _es_archivo_preview(nombre, video)
        )
    )

def previews_existentes(video):
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return []
    return [
        ruta_preview(video, indice)
        for indice in range(1, CANTIDAD_PREVIEWS + 1)
        if os.path.isfile(ruta_preview(video, indice))
    ]

def previews_faltantes(video):
    return [
        indice
        for indice in range(1, CANTIDAD_PREVIEWS + 1)
        if not os.path.isfile(ruta_preview(video, indice))
    ]

def calcular_tiempo_preview(duracion, indice=None):
    if duracion is None or duracion <= 0:
        return 1.0
    posicion = 1
    if isinstance(indice, int) and not isinstance(indice, bool) and 1 <= indice <= CANTIDAD_PREVIEWS:
        posicion = indice
    fraccion = posicion / (CANTIDAD_PREVIEWS + 1)
    return max(0.1, min(duracion * fraccion, duracion * 0.95))

def generar_preview(ruta_video, destino, indice=None, duracion_segundos=None):
    if _duracion_utilizable(duracion_segundos):
        duracion = duracion_segundos
    else:
        datos = obtener_datos_ffprobe(ruta_video)
        duracion = datos["duracion_segundos"] if datos else None
    tiempo = calcular_tiempo_preview(duracion, indice)
    try:
        resultado = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(tiempo),
                "-i", ruta_video,
                "-frames:v", "1", "-q:v", "3",
                destino,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            **_ARGS_SIN_CONSOLA,
        )
        return resultado.returncode == 0 and os.path.isfile(destino)
    except (OSError, subprocess.SubprocessError):
        return False

def generar_previews_faltantes(videos, carpeta, duraciones=None):
    if isinstance(videos, (str, bytes, bytearray)):
        raise TypeError("videos debe ser una colección de nombres, no texto")
    try:
        lista = list(videos)
    except TypeError:
        raise TypeError("videos debe ser una colección iterable") from None
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    resultados = []
    for nombre in lista:
        ruta_video = os.path.join(carpeta, nombre)
        faltantes = previews_faltantes(nombre)
        generados = 0
        reutilizados = 0
        errores = 0
        duracion = _duracion_de_duraciones(duraciones, nombre, ruta_video)
        if faltantes:
            os.makedirs(ruta_carpeta_miniaturas(), exist_ok=True)
            base = None
            if os.path.isfile(ruta_video):
                base = miniatura_reutilizable(nombre, ruta_video)
            for indice in faltantes:
                destino = ruta_preview(nombre, indice)
                if (
                    os.path.isfile(ruta_video)
                    and os.path.getsize(ruta_video) > 0
                    and generar_preview(ruta_video, destino, indice, duracion)
                ):
                    generados += 1
                elif base is not None and os.path.isfile(base):
                    try:
                        shutil.copyfile(base, destino)
                        reutilizados += 1
                    except OSError:
                        errores += 1
                else:
                    errores += 1
        previews = previews_existentes(nombre)
        resultados.append(
            {
                "nombre": nombre,
                "ruta": ruta_video,
                "previews": previews,
                "generados": generados,
                "reutilizados": reutilizados,
                "errores": errores,
                "completos": len(previews) >= CANTIDAD_PREVIEWS,
            }
        )
    return {
        "rutas": [r["ruta"] for r in resultados],
        "resultados": resultados,
        "procesados": len(resultados),
        "con_previews": sum(1 for r in resultados if r["previews"]),
        "sin_previews": sum(1 for r in resultados if not r["previews"]),
        "completos": sum(1 for r in resultados if r["completos"]),
        "generados": sum(r["generados"] for r in resultados),
        "reutilizados": sum(r["reutilizados"] for r in resultados),
        "errores": sum(r["errores"] for r in resultados),
    }

def insertar_video(conn, carpeta, nombre):
    extension = os.path.splitext(nombre)[1].lower()
    ruta = os.path.join(carpeta, nombre)
    fecha = datetime.now().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?, ?, ?, ?)",
        (nombre, ruta, extension, fecha),
    )

def actualizar_datos(conn, carpeta, nombre):
    ruta = os.path.join(carpeta, nombre)
    es_vacio = os.path.getsize(ruta) == 0
    datos = None if es_vacio else obtener_datos_ffprobe(ruta)
    miniaturas = contar_miniaturas(nombre)
    tamano_bytes = os.path.getsize(ruta)
    if datos is None:
        conn.execute(
            "UPDATE videos SET duracion_segundos = NULL, ancho = NULL, alto = NULL, codec_video = NULL, cantidad_miniaturas = ?, tamano_bytes = ? WHERE nombre = ?",
            (miniaturas, tamano_bytes, nombre),
        )
    else:
        conn.execute(
            "UPDATE videos SET duracion_segundos = ?, ancho = ?, alto = ?, codec_video = ?, cantidad_miniaturas = ?, tamano_bytes = ? WHERE nombre = ?",
            (datos["duracion_segundos"], datos["ancho"], datos["alto"], datos["codec_video"], miniaturas, tamano_bytes, nombre),
        )

def sincronizar_bd(conn, carpeta):
    en_disco = set(escanear_videos(carpeta))
    en_bd = {fila[0] for fila in conn.execute("SELECT nombre FROM videos")}
    for nombre in en_disco:
        insertar_video(conn, carpeta, nombre)
    for nombre in en_disco:
        asegurar_miniatura(nombre, os.path.join(carpeta, nombre))
        actualizar_datos(conn, carpeta, nombre)
    for nombre in en_bd - en_disco:
        conn.execute("DELETE FROM videos WHERE nombre = ?", (nombre,))

def listar_videos(ruta_db=None):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(
            """
            SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id
            FROM videos
            ORDER BY nombre
            """
        ).fetchall()
    finally:
        conn.close()


def listar_registros_por_nombres(nombres, ruta_db=None):
    """Registros existentes del catálogo localizados por nombre, en una consulta (B4.5 Etapa 3).

    Devuelve un dict `{nombre: {id, nombre, ruta, duracion_segundos, ancho,
    alto, codec_video, tamano_bytes, mtime_ns}}`. La búsqueda es por `nombre`
    (identidad existente del esquema `UNIQUE(nombre)`); la validez posterior se
    decide comparando la ruta normalizada. `nombres` vacío devuelve `{}`.
    """
    if isinstance(nombres, (str, bytes, bytearray)):
        raise TypeError("nombres debe ser una colección, no texto")
    try:
        lista = list(nombres)
    except TypeError:
        raise TypeError("nombres debe ser una colección iterable") from None
    if not lista:
        return {}
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        registros_por_nombre = {}
        filas = conn.execute(
            """
            SELECT id, nombre, ruta, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns
            FROM videos
            WHERE nombre IN ({})
            """.format(",".join("?" * len(lista))),
            lista,
        ).fetchall()
        for fila in filas:
            registros_por_nombre[fila[1]] = {
                "id": fila[0],
                "nombre": fila[1],
                "ruta": fila[2],
                "duracion_segundos": fila[3],
                "ancho": fila[4],
                "alto": fila[5],
                "codec_video": fila[6],
                "tamano_bytes": fila[7],
                "mtime_ns": fila[8],
            }
        return registros_por_nombre
    finally:
        conn.close()


def _es_subcarpeta(padre, ruta):
    if not isinstance(ruta, str) or not ruta:
        return False
    try:
        return os.path.commonpath([padre, ruta]) == padre
    except ValueError:
        return False


def detectar_diferencias(carpeta, ruta_db=None, carpetas_protegidas=None):
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    if not os.path.isdir(carpeta):
        raise FileNotFoundError(f"Carpeta no encontrada: {carpeta}")
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    if carpetas_protegidas is not None:
        if isinstance(carpetas_protegidas, (str, bytes, bytearray)):
            raise TypeError(
                "carpetas_protegidas debe ser una colección, no texto"
            )
        try:
            list(carpetas_protegidas)
        except TypeError:
            raise TypeError(
                "carpetas_protegidas debe ser una colección iterable"
            ) from None
    en_disco = set(escanear_videos(carpeta))
    carpeta_normalizada = os.path.normcase(os.path.normpath(carpeta))
    conn = sqlite3.connect(ruta_db)
    try:
        filas = conn.execute("SELECT nombre, ruta FROM videos").fetchall()
    finally:
        conn.close()
    nombres_en_bd = set()
    presentes = []
    ausentes = []
    for nombre, ruta in filas:
        if not isinstance(nombre, str):
            continue
        nombres_en_bd.add(nombre)
        if nombre in en_disco:
            presentes.append(nombre)
            continue
        if carpetas_protegidas is None:
            ausentes.append(nombre)
            continue
        ruta_normalizada = (
            os.path.normcase(os.path.normpath(ruta))
            if isinstance(ruta, str) and ruta
            else None
        )
        if _es_subcarpeta(carpeta_normalizada, ruta_normalizada):
            ausentes.append(nombre)
    return {
        "carpeta": carpeta,
        "presentes_en_ambos": sorted(presentes),
        "nuevos": sorted(en_disco - nombres_en_bd),
        "ausentes_del_disco": sorted(ausentes),
    }


def _coleccion_nombres(valor, clave):
    if isinstance(valor, (str, bytes, bytearray)):
        raise TypeError(f"{clave} debe ser una colección de nombres, no texto")
    try:
        return sorted(valor)
    except TypeError:
        raise TypeError(f"{clave} debe ser una colección iterable") from None


def preparar_plan_sincronizacion(diferencias):
    if not isinstance(diferencias, dict):
        raise TypeError("diferencias debe ser un diccionario")
    for clave in ("carpeta", "presentes_en_ambos", "nuevos", "ausentes_del_disco"):
        if clave not in diferencias:
            raise ValueError(f"falta la clave obligatoria: {clave}")
    carpeta = diferencias["carpeta"]
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    nuevos = _coleccion_nombres(diferencias["nuevos"], "nuevos")
    presentes = _coleccion_nombres(diferencias["presentes_en_ambos"], "presentes_en_ambos")
    ausentes = _coleccion_nombres(diferencias["ausentes_del_disco"], "ausentes_del_disco")
    return {
        "carpeta": carpeta,
        "a_incorporar": preparar_registros_basicos(nuevos, carpeta),
        "ya_sincronizados": presentes,
        "candidatos_a_eliminar": ausentes,
    }


def _validar_plan_sincronizacion(plan):
    if not isinstance(plan, dict):
        raise TypeError("plan debe ser un diccionario")
    for clave in ("carpeta", "a_incorporar", "ya_sincronizados", "candidatos_a_eliminar"):
        if clave not in plan:
            raise ValueError(f"falta la clave obligatoria: {clave}")
    carpeta = plan["carpeta"]
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    if isinstance(plan["a_incorporar"], (str, bytes, bytearray)):
        raise TypeError("a_incorporar debe ser una colección, no texto")
    try:
        iter(plan["a_incorporar"])
    except TypeError:
        raise TypeError("a_incorporar debe ser una colección iterable") from None
    _coleccion_nombres(plan["ya_sincronizados"], "ya_sincronizados")
    return _coleccion_nombres(plan["candidatos_a_eliminar"], "candidatos_a_eliminar")


def aplicar_incorporaciones(plan, ruta_db=None):
    candidatos = _validar_plan_sincronizacion(plan)
    resultado = guardar_videos(plan["a_incorporar"], ruta_db)
    return {
        "incorporados": resultado["guardados"],
        "nombres": resultado["nombres"],
        "pendientes_eliminacion": len(candidatos),
    }


def eliminar_candidatos(plan, ruta_db=None):
    candidatos = _validar_plan_sincronizacion(plan)
    try:
        incorporados = len(plan["a_incorporar"])
    except TypeError:
        incorporados = None
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        eliminados = []
        for nombre in candidatos:
            cursor = conn.execute("DELETE FROM videos WHERE nombre = ?", (nombre,))
            if cursor.rowcount:
                eliminados.append(nombre)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "eliminados": len(eliminados),
        "nombres": eliminados,
        "incorporados": incorporados,
        "restantes": len(candidatos) - len(eliminados),
    }


def fragmento_orden_sql(clave, direccion):
    """Única autoridad para convertir una clave/dirección válidas en SQL.

    La UI/config no construyen SQL ni envían expresiones: solo claves y
    direcciones de dominio. El fragmento final se interpola únicamente desde
    las constantes internas de las whitelists cerradas `ORDEN_CRITERIOS` y
    `ORDEN_DIRECCIONES`, con desempate final estable `id ASC` y NULLs siempre
    al final (tanto en ASC como en DESC).
    """
    if not isinstance(clave, str):
        raise TypeError("clave debe ser texto")
    if clave not in ORDEN_CRITERIOS:
        raise ValueError(f"criterio de orden desconocido: {clave!r}")
    if not isinstance(direccion, str):
        raise TypeError("direccion debe ser texto")
    if direccion not in ORDEN_DIRECCIONES:
        raise ValueError(f"dirección de orden desconocida: {direccion!r}")
    sentido = "ASC" if direccion == "asc" else "DESC"
    return (
        f"{_ORDEN_EXPRESION_NULO[clave]} ASC, "
        f"{_ORDEN_EXPRESION_CRITERIO[clave]} {sentido}, id ASC"
    )


# Filtros estructurados del catálogo (B6.5) – whitelist cerrada.
# La UI solo puede expresar filtros mediante estas claves; nunca SQL libre.
FILTRO_TODOS = "todos"
FILTRO_CON_MARCADORES = "con_marcadores"
FILTRO_CON_SEGMENTOS = "con_segmentos"
FILTRO_PREFIJO_MARCADOR = "marcador:"
FILTRO_PREFIJO_SEGMENTO = "segmento:"
FILTRO_MARCADOR_SIN_CLASIFICAR = "marcador:sin_clasificar"
FILTRO_SEGMENTO_SIN_CLASIFICAR = "segmento:sin_clasificar"


def _validar_filtro_catalogo(filtro):
    """Valida un filtro estructurado del catálogo (B6.5).

    Acepta `None` o `"todos"` (sin filtro), `"con_marcadores"`,
    `"con_segmentos"`, `"marcador:<color>"` y `"segmento:<color>"` donde
    `<color>` es una clave estable de `COLORES_CLASIFICACION`, y
    `"marcador:sin_clasificar"` / `"segmento:sin_clasificar"` para color
    `IS NULL` (B6.5 UX). Normaliza `"todos"` a `None`. Lanza `TypeError` si
    no es texto/None y `ValueError` si la clave o el color no pertenece a la
    whitelist.
    """
    if filtro is None:
        return None
    if not isinstance(filtro, str):
        raise TypeError("filtro debe ser texto o None")
    if filtro == FILTRO_TODOS or filtro == "":
        return None
    if filtro in (
        FILTRO_CON_MARCADORES,
        FILTRO_CON_SEGMENTOS,
        FILTRO_MARCADOR_SIN_CLASIFICAR,
        FILTRO_SEGMENTO_SIN_CLASIFICAR,
    ):
        return filtro
    if filtro.startswith(FILTRO_PREFIJO_MARCADOR):
        clave = filtro[len(FILTRO_PREFIJO_MARCADOR):]
        if clave not in CLAVES_COLOR_CLASIFICACION:
            raise ValueError(f"color de filtro no reconocido: {clave!r}")
        return filtro
    if filtro.startswith(FILTRO_PREFIJO_SEGMENTO):
        clave = filtro[len(FILTRO_PREFIJO_SEGMENTO):]
        if clave not in CLAVES_COLOR_CLASIFICACION:
            raise ValueError(f"color de filtro no reconocido: {clave!r}")
        return filtro
    raise ValueError(f"filtro no reconocido: {filtro!r}")


def _filtro_catalogo_exists(filtro):
    """Devuelve (fragmento EXISTS, params) para un filtro ya validado (B6.5).

    El fragmento es una condición EXISTS parametrizada (sin interpolación de
    valores libres). Para filtros por color el color se pasa como parámetro
    `?`; para Sin clasificar se usa `color IS NULL` sin parámetro.
    Devuelve `("", [])` para `None` (todos).
    """
    if filtro is None:
        return ("", [])
    if filtro == FILTRO_CON_MARCADORES:
        return (
            "EXISTS (SELECT 1 FROM marcadores_video WHERE marcadores_video.video_id = videos.id)",
            [],
        )
    if filtro == FILTRO_CON_SEGMENTOS:
        return (
            "EXISTS (SELECT 1 FROM segmentos_video WHERE segmentos_video.video_id = videos.id)",
            [],
        )
    if filtro == FILTRO_MARCADOR_SIN_CLASIFICAR:
        return (
            "EXISTS (SELECT 1 FROM marcadores_video WHERE marcadores_video.video_id = videos.id AND color IS NULL)",
            [],
        )
    if filtro == FILTRO_SEGMENTO_SIN_CLASIFICAR:
        return (
            "EXISTS (SELECT 1 FROM segmentos_video WHERE segmentos_video.video_id = videos.id AND color IS NULL)",
            [],
        )
    if filtro.startswith(FILTRO_PREFIJO_MARCADOR):
        color = filtro[len(FILTRO_PREFIJO_MARCADOR):]
        return (
            "EXISTS (SELECT 1 FROM marcadores_video WHERE marcadores_video.video_id = videos.id AND color = ?)",
            [color],
        )
    if filtro.startswith(FILTRO_PREFIJO_SEGMENTO):
        color = filtro[len(FILTRO_PREFIJO_SEGMENTO):]
        return (
            "EXISTS (SELECT 1 FROM segmentos_video WHERE segmentos_video.video_id = videos.id AND color = ?)",
            [color],
        )
    return ("", [])


def listar_videos_paginado(
    limite,
    desplazamiento=0,
    texto=None,
    ruta_db=None,
    orden_clave=None,
    orden_direccion=None,
    filtro=None,
):
    if isinstance(limite, bool) or not isinstance(limite, int):
        raise TypeError("limite debe ser un entero")
    if limite < 1:
        raise ValueError("limite debe ser un entero positivo")
    if isinstance(desplazamiento, bool) or not isinstance(desplazamiento, int):
        raise TypeError("desplazamiento debe ser un entero")
    if desplazamiento < 0:
        raise ValueError("desplazamiento debe ser un entero mayor o igual que cero")
    if texto is not None and not isinstance(texto, str):
        raise TypeError("texto debe ser None o texto")
    if orden_clave is not None and not isinstance(orden_clave, str):
        raise TypeError("orden_clave debe ser None o texto")
    if orden_direccion is not None and not isinstance(orden_direccion, str):
        raise TypeError("orden_direccion debe ser None o texto")
    # `filtro` validado por whitelist cerrada (B6.5) – nada de interpolar valores libres.
    filtro = _validar_filtro_catalogo(filtro)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    clave = ORDEN_CRITERIO_DEFAULT if orden_clave is None else orden_clave
    direccion = ORDEN_DIRECCION_DEFAULT if orden_direccion is None else orden_direccion
    orden = fragmento_orden_sql(clave, direccion)
    # Construcción estructurada del WHERE: texto (LIKE ?) y filtro (EXISTS parametrizado) con AND.
    condiciones = []
    params_where = []
    if texto is not None:
        condiciones.append("nombre LIKE ?")
        params_where.append(f"%{texto}%")
    frag_filtro, params_filtro = _filtro_catalogo_exists(filtro)
    if frag_filtro:
        condiciones.append(frag_filtro)
        params_where.extend(params_filtro)
    where_sql = ""
    if condiciones:
        where_sql = "WHERE " + " AND ".join(condiciones)
    conn = sqlite3.connect(ruta_db)
    try:
        filas = conn.execute(
            f"""
            SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, ruta, id
            FROM videos
            {where_sql}
            ORDER BY {orden}
            LIMIT ? OFFSET ?
            """,
            (*params_where, limite, desplazamiento),
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM videos {where_sql}",
            params_where,
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "videos": filas,
        "total": total,
        "limite": limite,
        "desplazamiento": desplazamiento,
    }

def _validar_registro_video(datos):
    if not isinstance(datos, dict):
        raise TypeError("datos debe ser un diccionario")
    for clave in ("nombre", "ruta", "extension", "fecha_importacion"):
        if clave not in datos:
            raise ValueError(f"falta la clave obligatoria: {clave}")


def _upsert_video(conn, datos):
    conn.execute(
        """
        INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            ruta = excluded.ruta,
            extension = excluded.extension,
            fecha_importacion = excluded.fecha_importacion,
            duracion_segundos = excluded.duracion_segundos,
            ancho = excluded.ancho,
            alto = excluded.alto,
            codec_video = excluded.codec_video,
            cantidad_miniaturas = excluded.cantidad_miniaturas,
            tamano_bytes = excluded.tamano_bytes,
            mtime_ns = excluded.mtime_ns
        """,
        (
            datos["nombre"],
            datos["ruta"],
            datos["extension"],
            datos["fecha_importacion"],
            datos.get("duracion_segundos"),
            datos.get("ancho"),
            datos.get("alto"),
            datos.get("codec_video"),
            datos.get("cantidad_miniaturas"),
            datos.get("tamano_bytes"),
            datos.get("mtime_ns"),
        ),
    )


def guardar_video(datos, ruta_db=None):
    _validar_registro_video(datos)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        _upsert_video(conn, datos)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"guardado": True, "nombre": datos["nombre"]}


def guardar_videos(datos_videos, ruta_db=None, on_progreso=None):
    if isinstance(datos_videos, (str, bytes, bytearray)):
        raise TypeError("datos_videos debe ser una colección, no texto")
    try:
        iterable = list(datos_videos)
    except TypeError:
        raise TypeError("datos_videos debe ser una colección iterable") from None
    registros = []
    for datos in iterable:
        _validar_registro_video(datos)
        registros.append(dict(datos))
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    total = len(registros)
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        for indice, datos in enumerate(registros):
            _upsert_video(conn, datos)
            if on_progreso is not None:
                on_progreso(indice + 1, total)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"guardados": len(registros), "nombres": [d["nombre"] for d in registros]}

def _conectar_repositorio_marcadores(ruta_db):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    _asegurar_tabla_marcadores(conn)
    return conn


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser un entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser un entero positivo")


def _validar_tiempo_marcador(tiempo):
    if isinstance(tiempo, bool) or not isinstance(tiempo, (int, float)):
        raise TypeError("tiempo debe ser numérico")
    if tiempo < 0:
        raise ValueError("tiempo no puede ser negativo")


def _validar_marcador_id(marcador_id):
    if isinstance(marcador_id, bool) or not isinstance(marcador_id, int):
        raise TypeError("marcador_id debe ser un entero")
    if marcador_id <= 0:
        raise ValueError("marcador_id debe ser un entero positivo")


def listar_marcadores(video_id, ruta_db=None):
    """Marcadores persistidos de un video, ordenados por tiempo.

    Devuelve una lista de tuplas `(id, video_id, tiempo, color)`. `color`
    es una clave estable de `COLORES_CLASIFICACION` o `None` (color
    histórico rojo).
    """
    _validar_video_id(video_id)
    conn = _conectar_repositorio_marcadores(ruta_db)
    try:
        return conn.execute(
            """
            SELECT id, video_id, tiempo, color
            FROM marcadores_video
            WHERE video_id = ?
            ORDER BY tiempo
            """,
            (video_id,),
        ).fetchall()
    finally:
        conn.close()


def listar_marcadores_de(video_ids, ruta_db=None):
    """Marcadores persistidos de varios videos (B4.4).

    Devuelve una lista de tuplas `(id, video_id, tiempo, color)` agrupada
    por `video_id` en el orden recibido y, dentro de cada video, ordenada
    por tiempo ascendente. Usa **una sola consulta SQL** (`WHERE video_id IN (...)`),
    sin consultas por video (B6.4 optimización batch).
    """
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser una colección de enteros")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser una colección de enteros")
    for video_id in lista:
        _validar_video_id(video_id)
    if not lista:
        return []
    ids_unicos = list(dict.fromkeys(lista))
    conn = _conectar_repositorio_marcadores(ruta_db)
    try:
        por_video = {}
        for marcador_id, video_de_fila, tiempo, color in conn.execute(
            f"""
            SELECT id, video_id, tiempo, color
            FROM marcadores_video
            WHERE video_id IN ({",".join("?" for _ in ids_unicos)})
            ORDER BY video_id, tiempo, id
            """,
            ids_unicos,
        ).fetchall():
            por_video.setdefault(video_de_fila, []).append(
                (marcador_id, video_de_fila, tiempo, color)
            )
        resultado = []
        for video_id in ids_unicos:
            resultado.extend(por_video.get(video_id, []))
        return resultado
    finally:
        conn.close()


def guardar_marcador(video_id, tiempo, ruta_db=None, color=None):
    """Persiste un marcador y devuelve su `id` de la base.

    `color` es opcional (B6.3): una clave estable de
    `COLORES_CLASIFICACION` o `None`. Se inserta en el mismo INSERT que el
    resto del marcador, nunca en una segunda escritura. Los callers
    históricos sin color siguen funcionando (el color queda `NULL` en la
    base, conservando el color histórico rojo).
    """
    _validar_video_id(video_id)
    _validar_tiempo_marcador(tiempo)
    _validar_color_clasificacion(color)
    conn = _conectar_repositorio_marcadores(ruta_db)
    try:
        cursor = conn.execute(
            "INSERT INTO marcadores_video (video_id, tiempo, color) "
            "VALUES (?, ?, ?)",
            (video_id, tiempo, color),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar_marcador(marcador_id, ruta_db=None):
    """Elimina un marcador por su `id` de la base.

    Devuelve `True` si se eliminó una fila; `False` si no existía.
    """
    _validar_marcador_id(marcador_id)
    conn = _conectar_repositorio_marcadores(ruta_db)
    try:
        cursor = conn.execute(
            "DELETE FROM marcadores_video WHERE id = ?",
            (marcador_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def asignar_color_marcador(marcador_id, clave, ruta_db=None):
    """Asigna (o quita, con `clave=None`) el color de clasificación de un
    marcador (B6.3).

    `clave` debe ser una clave estable de `COLORES_CLASIFICACION` o `None`
    (conserva el color histórico rojo). Devuelve la fila persistida
    `(id, video_id, tiempo, color)` si el marcador existía; `None` si no.
    """
    _validar_marcador_id(marcador_id)
    _validar_color_clasificacion(clave)
    conn = _conectar_repositorio_marcadores(ruta_db)
    try:
        cursor = conn.execute(
            "UPDATE marcadores_video SET color = ? WHERE id = ?",
            (clave, marcador_id),
        )
        conn.commit()
        if cursor.rowcount <= 0:
            return None
        return conn.execute(
            "SELECT id, video_id, tiempo, color "
            "FROM marcadores_video WHERE id = ?",
            (marcador_id,),
        ).fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _conectar_repositorio_segmentos(ruta_db):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    _asegurar_tabla_segmentos(conn)
    return conn


def _validar_inicio_segmento(inicio):
    if isinstance(inicio, bool) or not isinstance(inicio, (int, float)):
        raise TypeError("inicio debe ser numérico")
    if not math.isfinite(inicio):
        raise ValueError("inicio debe ser un número finito")
    if inicio < 0:
        raise ValueError("inicio no puede ser negativo")


def _validar_fin_segmento(inicio, fin):
    if isinstance(fin, bool) or not isinstance(fin, (int, float)):
        raise TypeError("fin debe ser numérico")
    if not math.isfinite(fin):
        raise ValueError("fin debe ser un número finito")
    if not (fin > inicio):
        raise ValueError("fin debe ser mayor que inicio")


def _validar_segmento_id(segmento_id):
    if isinstance(segmento_id, bool) or not isinstance(segmento_id, int):
        raise TypeError("segmento_id debe ser un entero")
    if segmento_id <= 0:
        raise ValueError("segmento_id debe ser un entero positivo")


def listar_segmentos(video_id, ruta_db=None):
    """Segmentos persistidos de un video, ordenados por inicio, fin e id.

    Devuelve una lista de tuplas `(id, inicio, fin, color)`. El `video_id`
    no se incluye porque es redundante en una consulta por video (a
    diferencia de `listar_segmentos_de`, donde sí se devuelve para
    identificar la agrupación). `color` es una clave estable de
    `COLORES_CLASIFICACION` o `None` (color histórico azul).
    """
    _validar_video_id(video_id)
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        return conn.execute(
            """
            SELECT id, inicio, fin, color
            FROM segmentos_video
            WHERE video_id = ?
            ORDER BY inicio, fin, id
            """,
            (video_id,),
        ).fetchall()
    finally:
        conn.close()


def listar_segmentos_de(video_ids, ruta_db=None):
    """Segmentos persistidos de varios videos (preparado para B5.8).

    Devuelve una lista de tuplas `(id, video_id, inicio, fin, color)`
    agrupada por `video_id` en el orden recibido (deduplicado) y, dentro de
    cada video, ordenada por inicio, fin e id ascendente. Usa **una sola
    consulta SQL** (`WHERE video_id IN (...)`), sin consultas por video.
    """
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser una colección de enteros")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser una colección de enteros")
    for video_id in lista:
        _validar_video_id(video_id)
    if not lista:
        return []
    ids_unicos = list(dict.fromkeys(lista))
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        por_video = {}
        for seg_id, video_de_fila, inicio, fin, color in conn.execute(
            f"""
            SELECT id, video_id, inicio, fin, color
            FROM segmentos_video
            WHERE video_id IN ({",".join("?" for _ in ids_unicos)})
            ORDER BY video_id, inicio, fin, id
            """,
            ids_unicos,
        ).fetchall():
            por_video.setdefault(video_de_fila, []).append(
                (seg_id, inicio, fin, color)
            )
        resultado = []
        for video_id in ids_unicos:
            resultado.extend(
                (seg_id, video_id, inicio, fin, color)
                for seg_id, inicio, fin, color in por_video.get(video_id, [])
            )
        return resultado
    finally:
        conn.close()


def guardar_segmento(video_id, inicio, fin, ruta_db=None, color=None):
    """Persiste un segmento y devuelve `(id, inicio, fin)` persistidos.

    `color` es opcional (B6.3): una clave estable de
    `COLORES_CLASIFICACION` o `None`. Se inserta en el mismo INSERT que el
    resto del segmento, nunca en una segunda escritura. Los callers
    históricos sin color siguen funcionando (el color queda `NULL` en la
    base, conservando el color histórico azul). El contrato de retorno no
    cambia: sigue siendo `(id, inicio, fin)`.

    No deduplica: dos segmentos idénticos pueden existir (no hay regla que
    lo prohíba).
    """
    _validar_video_id(video_id)
    _validar_inicio_segmento(inicio)
    _validar_fin_segmento(inicio, fin)
    _validar_color_clasificacion(color)
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        cursor = conn.execute(
            "INSERT INTO segmentos_video (video_id, inicio, fin, color) "
            "VALUES (?, ?, ?, ?)",
            (video_id, inicio, fin, color),
        )
        conn.commit()
        return (cursor.lastrowid, float(inicio), float(fin))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar_segmento(segmento_id, ruta_db=None):
    """Elimina un segmento por su `id` de la base.

    Devuelve `True` si se eliminó una fila; `False` si no existía.
    """
    _validar_segmento_id(segmento_id)
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        cursor = conn.execute(
            "DELETE FROM segmentos_video WHERE id = ?",
            (segmento_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def asignar_color_segmento(segmento_id, clave, ruta_db=None):
    """Asigna (o quita, con `clave=None`) el color de clasificación de un
    segmento (B6.3).

    `clave` debe ser una clave estable de `COLORES_CLASIFICACION` o `None`
    (conserva el color histórico azul). Devuelve la fila persistida
    `(id, inicio, fin, color)` si el segmento existía; `None` si no.
    """
    _validar_segmento_id(segmento_id)
    _validar_color_clasificacion(clave)
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        cursor = conn.execute(
            "UPDATE segmentos_video SET color = ? WHERE id = ?",
            (clave, segmento_id),
        )
        conn.commit()
        if cursor.rowcount <= 0:
            return None
        return conn.execute(
            "SELECT id, inicio, fin, color "
            "FROM segmentos_video WHERE id = ?",
            (segmento_id,),
        ).fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def actualizar_segmento(segmento_id, inicio, fin, ruta_db=None):
    """Actualiza los límites de un segmento persistido por su `id`.

    Conserva `id` y `video_id` (nunca borra/reinserta). Exige `fin > inicio`
    y devuelve `(segmento_id, inicio, fin)` si se actualizó una fila; `None`
    si el segmento no existía en la base.
    """
    _validar_segmento_id(segmento_id)
    _validar_inicio_segmento(inicio)
    _validar_fin_segmento(inicio, fin)
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        cursor = conn.execute(
            "UPDATE segmentos_video SET inicio = ?, fin = ? WHERE id = ?",
            (inicio, fin, segmento_id),
        )
        conn.commit()
        if cursor.rowcount <= 0:
            return None
        return (segmento_id, float(inicio), float(fin))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# === B6.9 Exportación múltiple de segmentos separados ===
# Sentinel explícito para distinguir “sin filtro” de “Sin clasificar (None)”

_SIN_FILTRO_LOTE = object()


def _validar_filtro_color_lote(color):
    """Valida filtro de color para lote (B6.9).

    Acepta sentinel `_SIN_FILTRO_LOTE` (sin filtro), `None` (Sin clasificar =
    color IS NULL) o clave estable de `CLAVES_COLOR_CLASIFICACION`.
    """
    if color is _SIN_FILTRO_LOTE:
        return color
    if color is None:
        return None
    if not isinstance(color, str):
        raise TypeError("color debe ser texto, None o sentinel sin filtro")
    if color not in CLAVES_COLOR_CLASIFICACION:
        raise ValueError(f"color no reconocido para lote: {color!r}")
    return color


def listar_segmentos_por_videos(video_ids, color=_SIN_FILTRO_LOTE, ruta_db=None):
    """Segmentos de un conjunto de video_ids con filtro opcional por color (B6.9).

    `color` distingue explícitamente tres casos mediante sentinel:
      - `_SIN_FILTRO_LOTE` (default): sin filtro, todos los segmentos de los videos.
      - `None`: solo Sin clasificar (color IS NULL).
      - clave estable: solo ese color.

    Devuelve lista de tuplas `(id, video_id, inicio, fin, color)` con orden
    determinista `ORDER BY video_id ASC, inicio ASC, fin ASC, id ASC` en una
    sola consulta batch (sin consultas por video). No carga pixmaps.
    """
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser una colección de enteros")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser una colección de enteros")
    for video_id in lista:
        _validar_video_id(video_id)
    _validar_filtro_color_lote(color)
    if not lista:
        return []
    ids_unicos = list(dict.fromkeys(lista))
    conn = _conectar_repositorio_segmentos(ruta_db)
    try:
        if color is _SIN_FILTRO_LOTE:
            where_color = ""
            params_color = []
        elif color is None:
            where_color = "AND color IS NULL"
            params_color = []
        else:
            where_color = "AND color = ?"
            params_color = [color]
        filas = conn.execute(
            f"""
            SELECT id, video_id, inicio, fin, color
            FROM segmentos_video
            WHERE video_id IN ({",".join("?" for _ in ids_unicos)})
            {where_color}
            ORDER BY video_id ASC, inicio ASC, fin ASC, id ASC
            """,
            ids_unicos + params_color,
        ).fetchall()
        return filas
    finally:
        conn.close()


def listar_videos_por_ids(video_ids, ruta_db=None):
    """Registros de videos por `id` en batch (B6.9, sin SQLite desde UI).

    Devuelve dict `{video_id: {id, nombre, ruta}}`. Orden no relevante;
    la responsabilidad de orden la tiene el caller del lote. Usa una sola
    consulta `WHERE id IN (...)`.
    """
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser una colección de enteros")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser una colección de enteros")
    for video_id in lista:
        _validar_video_id(video_id)
    if not lista:
        return {}
    ids_unicos = list(dict.fromkeys(lista))
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        filas = conn.execute(
            f"""
            SELECT id, nombre, ruta
            FROM videos
            WHERE id IN ({",".join("?" for _ in ids_unicos)})
            """,
            ids_unicos,
        ).fetchall()
        resultado = {}
        for vid, nombre, ruta in filas:
            resultado[vid] = {"id": vid, "nombre": nombre, "ruta": ruta}
        return resultado
    finally:
        conn.close()


# === B6.11 Incorporación al catálogo y trazabilidad de derivados ===

_TIPOS_DERIVADO = frozenset(("individual", "lote", "secuencia"))


def _validar_tipo_derivado(tipo):
    if not isinstance(tipo, str):
        raise TypeError("tipo debe ser texto")
    if tipo not in _TIPOS_DERIVADO:
        raise ValueError(f"tipo de derivado no reconocido: {tipo!r}")
    return tipo


def _conectar_derivados(ruta_db=None):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    _asegurar_tablas_derivados(conn)
    # también asegurar columnas/videos para consistencia
    try:
        _asegurar_columnas_videos(conn)
    except Exception:
        pass
    return conn


def es_video_derivado(video_id, ruta_db=None):
    """Indica si `video_id` corresponde a un video derivado (B6.11)."""
    _validar_video_id(video_id)
    conn = _conectar_derivados(ruta_db)
    try:
        fila = conn.execute(
            "SELECT 1 FROM videos_derivados WHERE derivado_video_id = ?",
            (video_id,),
        ).fetchone()
        return fila is not None
    finally:
        conn.close()


def obtener_derivacion_por_derivado(derivado_video_id, ruta_db=None):
    """Trazabilidad de un derivado: dict con claves `derivacion`, `segmentos` o None (B6.11).

    `derivacion` contiene columnas de `videos_derivados`; `segmentos` es lista
    ordenada por `orden` con `(id, derivacion_id, segmento_id, orden, inicio, fin)`.
    Sin CASCADE: si el original o el derivado ya no existen en `videos`, la fila
    persiste (orfandad histórica).
    """
    _validar_video_id(derivado_video_id)
    conn = _conectar_derivados(ruta_db)
    try:
        fila = conn.execute(
            """
            SELECT id, derivado_video_id, original_video_id, tipo, fecha_creacion,
                   derivado_nombre, derivado_ruta, original_nombre, original_ruta
            FROM videos_derivados
            WHERE derivado_video_id = ?
            """,
            (derivado_video_id,),
        ).fetchone()
        if fila is None:
            return None
        derivacion = {
            "id": fila[0],
            "derivado_video_id": fila[1],
            "original_video_id": fila[2],
            "tipo": fila[3],
            "fecha_creacion": fila[4],
            "derivado_nombre": fila[5],
            "derivado_ruta": fila[6],
            "original_nombre": fila[7],
            "original_ruta": fila[8],
        }
        segmentos = conn.execute(
            """
            SELECT id, derivacion_id, segmento_id, orden, inicio, fin
            FROM videos_derivados_segmentos
            WHERE derivacion_id = ?
            ORDER BY orden ASC, id ASC
            """,
            (derivacion["id"],),
        ).fetchall()
        return {"derivacion": derivacion, "segmentos": segmentos}
    finally:
        conn.close()


def listar_derivaciones_por_original(original_video_id, ruta_db=None):
    """Todas las derivaciones cuyo `original_video_id` coincide (B6.11)."""
    _validar_video_id(original_video_id)
    conn = _conectar_derivados(ruta_db)
    try:
        filas = conn.execute(
            """
            SELECT id, derivado_video_id, original_video_id, tipo, fecha_creacion,
                   derivado_nombre, derivado_ruta, original_nombre, original_ruta
            FROM videos_derivados
            WHERE original_video_id = ?
            ORDER BY id ASC
            """,
            (original_video_id,),
        ).fetchall()
        resultado = []
        for fila in filas:
            resultado.append({
                "id": fila[0],
                "derivado_video_id": fila[1],
                "original_video_id": fila[2],
                "tipo": fila[3],
                "fecha_creacion": fila[4],
                "derivado_nombre": fila[5],
                "derivado_ruta": fila[6],
                "original_nombre": fila[7],
                "original_ruta": fila[8],
            })
        return resultado
    finally:
        conn.close()


def _validar_segmentos_trazabilidad(segmentos):
    if not isinstance(segmentos, (list, tuple)):
        raise TypeError("segmentos debe ser lista")
    if not segmentos:
        raise ValueError("segmentos no puede estar vacía")
    validados = []
    for idx, seg in enumerate(segmentos):
        if not isinstance(seg, dict):
            raise TypeError(f"segmento {idx} debe ser dict")
        sid = seg.get("segmento_id")
        ini = seg.get("inicio")
        fin = seg.get("fin")
        if isinstance(sid, bool) or not isinstance(sid, int) or sid <= 0:
            raise ValueError(f"segmento {idx} segmento_id inválido")
        if not isinstance(ini, (int, float)) or isinstance(ini, bool):
            raise TypeError(f"segmento {idx} inicio debe ser numérico")
        if not isinstance(fin, (int, float)) or isinstance(fin, bool):
            raise TypeError(f"segmento {idx} fin debe ser numérico")
        if not (fin > ini and ini >= 0):
            raise ValueError(f"segmento {idx} rango inválido")
        validados.append({"segmento_id": int(sid), "inicio": float(ini), "fin": float(fin)})
    return validados


def incorporar_video_derivado_al_catalogo(derivado_ruta, original_video_id, segmentos_orden, tipo="individual", ruta_db=None):
    """Alta incremental de un video derivado al catálogo con trazabilidad (B6.11).

    Flujo mínimo seguro:
      - valida archivo existente y no vacío
      - valida tipo y segmentos en orden explícito
      - bloquea derivado-de-derivado (original no puede ser derivado)
      - previene duplicados (nombre UNIQUE y derivado_video_id UNIQUE)
      - obtiene metadata FFprobe del derivado y stats (tamaño/mtime)
      - inserta registro en `videos` (upsert controlado) y relación en
        `videos_derivados` + `videos_derivados_segmentos` en una transacción
      - si falla el alta, conserva el archivo y reporta error de catalogación

    `segmentos_orden`: lista de dicts `{segmento_id, inicio, fin}` en orden explícito
    (para B6.7/B6.9 un elemento; para B6.10 N en orden). Se persiste orden tal cual.

    Devuelve dict `{ok, derivado_video_id, derivacion_id, error, catalog_error}`:
      - ok True → alta exitosa
      - ok False + error → fallo (catalog_error True indica fallo de alta al catálogo
        con archivo conservado; False indica validación previa sin tocar catálogo)
    """
    _validar_tipo_derivado(tipo)
    if not isinstance(derivado_ruta, str) or not derivado_ruta.strip():
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "ruta derivada inválida", "catalog_error": False}
    if not os.path.isfile(derivado_ruta):
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "archivo derivado no encontrado", "catalog_error": False}
    try:
        if os.path.getsize(derivado_ruta) == 0:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "archivo derivado vacío", "catalog_error": False}
    except OSError as exc:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"no se pudo leer derivado: {exc}", "catalog_error": False}
    _validar_video_id(original_video_id)
    try:
        segmentos_val = _validar_segmentos_trazabilidad(segmentos_orden)
    except Exception as exc:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"segmentos inválidos: {exc}", "catalog_error": False}
    # extensión controlada (solo .mp4/.mkv como en B6.7/10)
    ext = os.path.splitext(derivado_ruta)[1].lower()
    if ext not in (".mp4", ".mkv"):
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"extensión no soportada para derivado: {ext!r}", "catalog_error": False}
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"Base de datos no encontrada: {ruta_db}", "catalog_error": True}
    # Corrección mínima B6.11: gestión segura de conexiones sin múltiples close manuales
    # dispersos; un único finally por fase evita doble cierre y fugas.
    conn = None
    derivado_nombre = os.path.basename(derivado_ruta)
    derivado_ruta_abs = os.path.abspath(derivado_ruta)
    orig_nombre = None
    orig_ruta = None
    try:
        conn = _conectar_derivados(ruta_db)
        try:
            conn.execute("SELECT 1 FROM videos LIMIT 1")
        except sqlite3.OperationalError:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "tabla videos no disponible", "catalog_error": True}
        # Validaciones previas sin modificar BD
        fila_orig = conn.execute(
            "SELECT id, nombre, ruta FROM videos WHERE id = ?",
            (original_video_id,),
        ).fetchone()
        if fila_orig is None:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"original_video_id {original_video_id} no existe en catálogo", "catalog_error": False}
        orig_id, orig_nombre, orig_ruta = fila_orig
        fila_es_der = conn.execute(
            "SELECT 1 FROM videos_derivados WHERE derivado_video_id = ?",
            (original_video_id,),
        ).fetchone()
        if fila_es_der is not None:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "bloqueado: el original es a su vez un derivado (derivado-de-derivado no permitido en B6.11)", "catalog_error": False}
        fila_dup_nombre = conn.execute(
            "SELECT id, ruta FROM videos WHERE nombre = ?",
            (derivado_nombre,),
        ).fetchone()
        if fila_dup_nombre is not None:
            dup_id, dup_ruta = fila_dup_nombre
            if os.path.normcase(os.path.normpath(os.path.abspath(dup_ruta))) == os.path.normcase(os.path.normpath(derivado_ruta_abs)):
                return {"ok": False, "derivado_video_id": dup_id, "derivacion_id": None, "error": "derivado ya existe en catálogo (nombre duplicado)", "catalog_error": True}
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"nombre duplicado en catálogo: {derivado_nombre!r} ya existe", "catalog_error": True}
        if os.path.normcase(os.path.normpath(os.path.abspath(orig_ruta))) == os.path.normcase(os.path.normpath(derivado_ruta_abs)):
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "derivado no puede ser el mismo archivo que el original", "catalog_error": False}
        for seg in segmentos_val:
            sid = seg["segmento_id"]
            fila_seg = conn.execute(
                "SELECT video_id, inicio, fin FROM segmentos_video WHERE id = ?",
                (sid,),
            ).fetchone()
            if fila_seg is None:
                return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"segmento_id {sid} no existe", "catalog_error": False}
            vid_seg, ini_seg, fin_seg = fila_seg
            if vid_seg != original_video_id:
                return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"segmento_id {sid} no pertenece al original {original_video_id}", "catalog_error": False}
    except Exception as exc:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"error inesperado en validación: {exc}", "catalog_error": True}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
    # obtener ffprobe fuera de transacción larga (costoso) - archivo se conserva si falla
    datos_ff = obtener_datos_ffprobe(derivado_ruta)
    if datos_ff is None:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "no se pudo obtener metadata FFprobe del derivado", "catalog_error": True}
    dur = datos_ff.get("duracion_segundos")
    ancho = datos_ff.get("ancho")
    alto = datos_ff.get("alto")
    codec = datos_ff.get("codec_video")
    if not isinstance(dur, (int, float)) or not math.isfinite(float(dur)) or float(dur) <= 0:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "duración del derivado inválida", "catalog_error": True}
    try:
        st = os.stat(derivado_ruta)
        tamano = st.st_size
        mtime_ns = st.st_mtime_ns
    except OSError as exc:
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"no se pudo stat derivado: {exc}", "catalog_error": True}
    # Transacción de alta atómica: video + derivación + segmentos
    conn2 = None
    try:
        conn2 = _conectar_derivados(ruta_db)
        conn2.execute("BEGIN")
        fila_dup2 = conn2.execute(
            "SELECT id FROM videos WHERE nombre = ?",
            (derivado_nombre,),
        ).fetchone()
        if fila_dup2 is not None:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": fila_dup2[0], "derivacion_id": None, "error": "nombre duplicado (carrera)", "catalog_error": True}
        fecha_imp = datetime.now().isoformat()
        datos_video = {
            "nombre": derivado_nombre,
            "ruta": derivado_ruta_abs,
            "extension": ext,
            "fecha_importacion": fecha_imp,
            "duracion_segundos": float(dur),
            "ancho": int(ancho) if isinstance(ancho, int) and ancho > 0 else None,
            "alto": int(alto) if isinstance(alto, int) and alto > 0 else None,
            "codec_video": str(codec) if isinstance(codec, str) and codec.strip() else None,
            "cantidad_miniaturas": 0,
            "tamano_bytes": int(tamano),
            "mtime_ns": int(mtime_ns),
        }
        _asegurar_columnas_videos(conn2)
        _upsert_video(conn2, datos_video)
        fila_new = conn2.execute(
            "SELECT id FROM videos WHERE nombre = ?",
            (derivado_nombre,),
        ).fetchone()
        if fila_new is None:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": "no se pudo obtener id del derivado tras insertar", "catalog_error": True}
        derivado_vid = fila_new[0]
        fila_traza = conn2.execute(
            "SELECT id FROM videos_derivados WHERE derivado_video_id = ?",
            (derivado_vid,),
        ).fetchone()
        if fila_traza is not None:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": derivado_vid, "derivacion_id": fila_traza[0], "error": "trazabilidad ya existe para este derivado", "catalog_error": True}
        cur = conn2.execute(
            """
            INSERT INTO videos_derivados
            (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (derivado_vid, original_video_id, tipo, fecha_imp, derivado_nombre, derivado_ruta_abs, orig_nombre, orig_ruta),
        )
        derivacion_id = cur.lastrowid
        for orden, seg in enumerate(segmentos_val):
            conn2.execute(
                """
                INSERT INTO videos_derivados_segmentos
                (derivacion_id, segmento_id, orden, inicio, fin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (derivacion_id, seg["segmento_id"], orden, seg["inicio"], seg["fin"]),
            )
        conn2.commit()
        return {"ok": True, "derivado_video_id": derivado_vid, "derivacion_id": derivacion_id, "error": None, "catalog_error": False}
    except sqlite3.IntegrityError as exc:
        try:
            if conn2 is not None:
                conn2.rollback()
        except Exception:
            pass
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"integridad de catálogo: {exc}", "catalog_error": True}
    except Exception as exc:
        try:
            if conn2 is not None:
                conn2.rollback()
        except Exception:
            pass
        return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"error al dar de alta derivado: {exc}", "catalog_error": True}
    finally:
        if conn2 is not None:
            try:
                conn2.close()
            except Exception:
                pass


def actualizar_nombre_video(video_id, nuevo_nombre, nueva_ruta, ruta_db=None):
    """Helper explícito B7.1 — actualiza nombre y ruta en transacción corta.

    Valida video_id y persiste en una única transacción. No toca filesystem.
    Lanza sqlite3.IntegrityError si viola UNIQUE(nombre).
    """
    _validar_video_id(video_id)
    if not isinstance(nuevo_nombre, str) or not nuevo_nombre:
        raise ValueError("nuevo_nombre debe ser texto no vacío")
    if not isinstance(nueva_ruta, str) or not nueva_ruta:
        raise ValueError("nueva_ruta debe ser texto no vacío")
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            "UPDATE videos SET nombre = ?, ruta = ? WHERE id = ?",
            (nuevo_nombre, nueva_ruta, video_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise ValueError(f"video_id {video_id} no existe")
        conn.commit()
        return {"ok": True, "video_id": video_id, "nombre": nuevo_nombre, "ruta": nueva_ruta}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def obtener_video_por_id(video_id, ruta_db=None):
    """Obtiene un video por id (B7.1)."""
    _validar_video_id(video_id)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        fila = conn.execute(
            "SELECT id, nombre, ruta, extension FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()
        if fila is None:
            return None
        return {"id": fila[0], "nombre": fila[1], "ruta": fila[2], "extension": fila[3]}
    finally:
        conn.close()


def main():
    conn = conectar_bd()
    sincronizar_bd(conn, ruta_carpeta_videos())
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
