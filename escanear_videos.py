import math
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime

from rutas import normalizar_ruta_clave, ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos

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


def _asegurar_ruta_normalizada(conn):
    """Migración B8.1: columna `ruta_normalizada` + población + UNIQUE.

    Aditiva e idempotente. Crea `ruta_normalizada TEXT`, puebla para filas
    existentes usando exclusivamente `rutas.normalizar_ruta_clave`, valida
    explícitamente rutas NULL/vacías/relativas/colisiones (GROUP BY
    `ruta_normalizada HAVING COUNT(*) > 1`) y crea `UNIQUE(ruta_normalizada)`
    sin eliminar todavía `UNIQUE(nombre)`. Preserva `videos.id`,
    `sqlite_sequence`, marcadores/segmentos/derivados y FK.

    Ante colisión real preserves datos y lanza error diagnóstico sin
    correcciones destructivas.

    B8.1 auditoría A: rutas relativas heredadas se detectan explícitamente y
    no se convierten silenciosamente con abspath.

    B8.1 auditoría C: una vez migrada (columna existe + índice único + sin NULL),
    la apertura posterior no recorre globalmente la tabla.
    """
    existentes = {fila[1] for fila in conn.execute("PRAGMA table_info(videos)")}
    col_existed = "ruta_normalizada" in existentes
    if not col_existed:
        conn.execute("ALTER TABLE videos ADD COLUMN ruta_normalizada TEXT")
    else:
        # Camino rápido: si columna ya existía y el índice único ya existe, no hacer scan global
        # Comprobación de esquema necesaria pero sin SELECT global
        try:
            idx_list = conn.execute("PRAGMA index_list(videos)").fetchall()
        except Exception:
            idx_list = []
        idx_names = {row[1] for row in idx_list} if idx_list else set()
        if "idx_videos_ruta_normalizada" in idx_names:
            # Si el índice ya existe, asumimos migración ya completada; evitar scan global
            # No validar contenido fila por fila en cada conectar_bd
            return
    # Camino de migración: poblar y validar (solo cuando columna nueva o índice faltante)
    filas = conn.execute("SELECT id, ruta, ruta_normalizada FROM videos").fetchall()
    # Validación explícita: NULL / vacías / relativas (auditoría A)
    for vid, ruta, _rn in filas:
        if ruta is None:
            raise ValueError(
                f"B8.1 precondición: video id={vid} tiene ruta NULL, "
                "no se puede crear ruta_normalizada sin pérdida"
            )
        if not isinstance(ruta, str) or not ruta.strip():
            raise ValueError(
                f"B8.1 precondición: video id={vid} tiene ruta vacía, "
                "no se puede crear ruta_normalizada sin pérdida"
            )
        ruta_stripped = ruta.strip()
        if not os.path.isabs(ruta_stripped):
            raise ValueError(
                f"B8.1 precondición: video id={vid} tiene ruta relativa {ruta!r}, "
                "no se puede migrar silenciosamente con abspath (depende de CWD). "
                "Corrija la ruta a absoluta antes de migrar. Se preservan todos los datos."
            )
    norm_por_id = {}
    colisiones = {}
    for vid, ruta, _rn in filas:
        try:
            norm = normalizar_ruta_clave(ruta)
        except Exception as exc:
            raise ValueError(
                f"B8.1 no se pudo normalizar ruta id={vid} ruta={ruta!r}: {exc}"
            ) from None
        if norm is None or not norm.strip():
            raise ValueError(f"B8.1 ruta_normalizada vacía para id={vid} ruta={ruta!r}")
        norm_por_id[vid] = norm
        colisiones.setdefault(norm, []).append(vid)
    duplicados = {k: v for k, v in colisiones.items() if len(v) > 1}
    if duplicados:
        detalle = "; ".join(f"{norm!r} -> ids {ids}" for norm, ids in duplicados.items())
        raise ValueError(
            "B8.1 colisión de ruta_normalizada: distintas representaciones "
            f"normalizan igual sin pérdida automática: {detalle}. Se preservan todos los datos."
        )
    # Poblar valores faltantes o desactualizados
    for vid, norm in norm_por_id.items():
        current = next((rn for i, _r, rn in filas if i == vid), None)
        if current != norm:
            conn.execute(
                "UPDATE videos SET ruta_normalizada = ? WHERE id = ?", (norm, vid)
            )
    # Crear unicidad para ruta_normalizada sin eliminar UNIQUE(nombre)
    try:
        idx_list2 = conn.execute("PRAGMA index_list(videos)").fetchall()
    except Exception:
        idx_list2 = []
    idx_names2 = {row[1] for row in idx_list2} if idx_list2 else set()
    if "idx_videos_ruta_normalizada" not in idx_names2:
        # Verificación pre-CREATE por GROUP BY en estado ya poblado
        filas_dup = conn.execute("""
            SELECT ruta_normalizada, COUNT(*) c FROM videos
            WHERE ruta_normalizada IS NOT NULL
            GROUP BY ruta_normalizada HAVING c > 1
        """).fetchall()
        if filas_dup:
            detalle = "; ".join(f"{rn!r} x{c}" for rn, c in filas_dup)
            raise ValueError(
                "B8.1 colisión GROUP BY ruta_normalizada HAVING COUNT(*) > 1: "
                f"{detalle}. Se preservan todos los datos."
            )
        try:
            conn.execute(
                "CREATE UNIQUE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)"
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"B8.1 no se pudo crear UNIQUE(ruta_normalizada) por colisión: {exc}. "
                "Se preservan todos los datos."
            ) from None


def _estado_cutover_identidad_b83(conn):
    """Detector estructural B8.3 por PRAGMA index_list/index_info/table_info.

    Clasificación mínima:
      - `pre`: UNIQUE(nombre) de una sola columna, UNIQUE idx_videos_ruta_normalizada sobre ruta_normalizada, ruta_normalizada nullable
      - `post`: sin UNIQUE(nombre), idx_videos_ruta_normalizada UNIQUE sobre ruta_normalizada, ruta_normalizada NOT NULL
      - `invalido`: cualquier otra combinación relevante -> ValueError

    No asume nombre exacto de sqlite_autoindex; usa index_list+index_info.
    Si `origin` está disponible se usa como señal adicional no exclusiva.
    """
    # tabla videos debe existir
    try:
        table_info = conn.execute("PRAGMA table_info('videos')").fetchall()
    except Exception as exc:
        raise ValueError(f"B8.3 detector: no se pudo leer PRAGMA table_info(videos): {exc}") from None
    if not table_info:
        raise ValueError("B8.3 detector: tabla videos no existe")
    col_por_nombre = {row[1]: row for row in table_info}
    if "ruta_normalizada" not in col_por_nombre:
        raise ValueError("B8.3 estado invalido: falta columna ruta_normalizada")
    # notnull flag es row[3] (1 = NOT NULL)
    ruta_notnull = col_por_nombre["ruta_normalizada"][3] == 1
    # index_list: seq, name, unique, origin, partial
    try:
        idx_list = conn.execute("PRAGMA index_list('videos')").fetchall()
    except Exception as exc:
        raise ValueError(f"B8.3 detector: no se pudo leer PRAGMA index_list: {exc}") from None
    unique_single_nombre = []
    has_idx_ruta_unique = False
    has_composite_nombre = False
    unique_indexes_detalle = []
    for row in idx_list:
        try:
            seq, name, unique, origin, partial = row
        except ValueError:
            # fallback si columnas difieren
            if len(row) >= 3:
                name = row[1]
                unique = row[2]
                origin = row[3] if len(row) > 3 else None
            else:
                continue
        if unique != 1:
            continue
        # obtener columnas del índice
        try:
            info = conn.execute(f"PRAGMA index_info('{name}')").fetchall()
        except Exception:
            info = []
        if not info:
            try:
                xinfo = conn.execute(f"PRAGMA index_xinfo('{name}')").fetchall()
                # filtrar columnas ocultas si existen (cid <0)
                # xinfo: seqno, cid, name
                info = [r for r in xinfo if len(r) > 2 and r[2] is not None]
            except Exception:
                info = []
        cols = []
        for r in info:
            # r: seqno, cid, name
            if len(r) >= 3:
                cname = r[2]
                if cname is not None:
                    cols.append(cname)
        unique_indexes_detalle.append((name, unique, origin, cols))
        if "nombre" in cols:
            if len(cols) == 1 and cols[0] == "nombre":
                unique_single_nombre.append(name)
            else:
                has_composite_nombre = True
        if name == "idx_videos_ruta_normalizada" and len(cols) == 1 and cols[0] == "ruta_normalizada":
            has_idx_ruta_unique = True
        # también detectar UNIQUE sobre ruta_normalizada con otro nombre (no debería existir)
        # pero la clasificación exige exactamente idx_videos_ruta_normalizada
    if has_composite_nombre:
        raise ValueError("B8.3 estado invalido: existe UNIQUE compuesto que incluye nombre")
    if len(unique_single_nombre) > 1:
        raise ValueError(f"B8.3 estado invalido: múltiples UNIQUE sobre nombre: {unique_single_nombre}")
    if not has_idx_ruta_unique:
        raise ValueError("B8.3 estado invalido: falta índice UNIQUE idx_videos_ruta_normalizada sobre ruta_normalizada")
    has_unique_nombre = len(unique_single_nombre) == 1
    if has_unique_nombre:
        if ruta_notnull:
            raise ValueError("B8.3 estado invalido: UNIQUE(nombre) presente pero ruta_normalizada es NOT NULL (mezcla pre/post)")
        return "pre"
    else:
        if not ruta_notnull:
            raise ValueError("B8.3 estado invalido: sin UNIQUE(nombre) pero ruta_normalizada es nullable (post requiere NOT NULL)")
        return "post"


def _ejecutar_cutover_identidad_b83_en_transaccion(conn):
    """Núcleo único B8.3: rebuild dentro de transacción existente.

    Contrato:
    - REQUIERE conn.in_transaction == True; si no, ValueError claro.
    - Asume que _asegurar_columnas_videos y _asegurar_ruta_normalizada ya dejaron
      la DB en estado estructural pre o post detectable.
    - Si detector post: devuelve False / no hace rebuild.
    - Si pre: ejecuta TODO el rebuild B8.3 dentro de la transacción EXISTENTE,
      SIN BEGIN, SIN commit, SIN rollback, SIN tocar PRAGMA foreign_keys.
    - Toda la lógica duplicada (prevalidación rutas, duplicados, residual table,
      seq_anterior, CREATE nueva, copy explícita, count/MAX/nulos, DROP/RENAME,
      índice, seq_final) vive SOLO aquí.
    - Si falla, lanza; el caller dueño de la transacción hace rollback.
    - No muta atributos en sqlite3.Connection.
    """
    if not conn.in_transaction:
        raise ValueError("B8.3 _ejecutar_cutover_identidad_b83_en_transaccion: requiere transacción abierta (conn.in_transaction==True)")
    estado = _estado_cutover_identidad_b83(conn)
    if estado == "post":
        return False
    # estado == "pre" -> validaciones y rebuild inline
    filas = conn.execute("SELECT id, ruta, ruta_normalizada FROM videos").fetchall()
    for vid, ruta, rn in filas:
        if rn is None or (isinstance(rn, str) and not rn.strip()):
            raise ValueError(f"B8.3 precondición: ruta_normalizada NULL/vacía para id={vid}, se preservan datos intactos")
        if ruta is None or (isinstance(ruta, str) and not ruta.strip()):
            raise ValueError(f"B8.3 precondición: ruta NULL/vacía para id={vid}")
        try:
            esperada = normalizar_ruta_clave(ruta)
        except Exception as exc:
            raise ValueError(f"B8.3 precondición: no se pudo normalizar ruta id={vid} ruta={ruta!r}: {exc}") from None
        if rn != esperada:
            raise ValueError(f"B8.3 precondición: ruta_normalizada incorrecta para id={vid}: got {rn!r} esperado {esperada!r}")
    vistos = {}
    duplicados = {}
    for vid, ruta, rn in filas:
        if rn in vistos:
            duplicados.setdefault(rn, []).append(vid)
            if rn not in duplicados or vistos[rn] not in duplicados[rn]:
                duplicados[rn].insert(0, vistos[rn])
        else:
            vistos[rn] = vid
    dup_db = conn.execute("""
        SELECT ruta_normalizada, COUNT(*) c FROM videos
        WHERE ruta_normalizada IS NOT NULL
        GROUP BY ruta_normalizada HAVING c > 1
    """).fetchall()
    if dup_db or duplicados:
        detalle_db = "; ".join(f"{rn!r} x{c}" for rn, c in dup_db) if dup_db else ""
        detalle_mem = "; ".join(f"{rn!r} -> ids {ids}" for rn, ids in duplicados.items()) if duplicados else ""
        detalle = "; ".join(filter(None, [detalle_db, detalle_mem]))
        raise ValueError(f"B8.3 colisión ruta_normalizada detectada, abortando sin modificar schema: {detalle}")
    existe_new = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='videos_b83_new'").fetchone()
    if existe_new is not None:
        raise ValueError("B8.3 abortado: existe tabla videos_b83_new residual; se requiere intervención manual, no se eliminará a ciegas")
    seq_anterior = None
    try:
        row_seq = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='videos'").fetchone()
        if row_seq:
            seq_anterior = row_seq[0]
    except sqlite3.OperationalError as exc:
        if "no such table: sqlite_sequence" in str(exc).lower():
            seq_anterior = None
        else:
            raise
    # Rebuild SIN tocar PRAGMA foreign_keys ni BEGIN/commit
    conn.execute("""
        CREATE TABLE videos_b83_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL,
            duracion_segundos REAL,
            ancho INTEGER,
            alto INTEGER,
            codec_video TEXT,
            cantidad_miniaturas INTEGER,
            tamano_bytes INTEGER,
            mtime_ns INTEGER,
            ruta_normalizada TEXT NOT NULL
        )
    """)
    conn.execute("""
        INSERT INTO videos_b83_new (id, nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns, ruta_normalizada)
        SELECT id, nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns, ruta_normalizada
        FROM videos
    """)
    cnt_orig = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    cnt_new = conn.execute("SELECT COUNT(*) FROM videos_b83_new").fetchone()[0]
    if cnt_orig != cnt_new:
        raise ValueError(f"B8.3 validación count mismatch origen={cnt_orig} destino={cnt_new}")
    max_orig = conn.execute("SELECT MAX(id) FROM videos").fetchone()[0]
    max_new = conn.execute("SELECT MAX(id) FROM videos_b83_new").fetchone()[0]
    if max_orig != max_new:
        raise ValueError(f"B8.3 validación MAX(id) mismatch origen={max_orig} destino={max_new}")
    nulos = conn.execute("SELECT COUNT(*) FROM videos_b83_new WHERE ruta_normalizada IS NULL").fetchone()[0]
    if nulos != 0:
        raise ValueError(f"B8.3 validación: {nulos} filas con ruta_normalizada NULL en destino")
    conn.execute("DROP TABLE videos")
    conn.execute("ALTER TABLE videos_b83_new RENAME TO videos")
    conn.execute("CREATE UNIQUE INDEX idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
    max_id_actual = max_new if max_new is not None else 0
    seq_prev_val = seq_anterior if isinstance(seq_anterior, int) else 0
    seq_final = max(seq_prev_val, max_id_actual)
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        if seq_final > 0 or cnt_new > 0:
            conn.execute("INSERT INTO sqlite_sequence(name, seq) VALUES('videos', ?)", (seq_final,))
    except sqlite3.OperationalError as exc:
        if "no such table: sqlite_sequence" in str(exc).lower():
            if seq_final == 0:
                pass
            else:
                raise RuntimeError(f"B8.3 no se pudo preservar sqlite_sequence seq={seq_final}: {exc!r}") from exc
        else:
            raise
    return True


def _asegurar_cutover_identidad_b83(conn):
    """Wrapper autónomo B8.3 para conectar_bd/migración explícita.

    - detector post => return rápido sin commits.
    - si pre, exigir conexión fuera de transacción.
    - leer PRAGMA foreign_keys ANTES de BEGIN.
    - si se decide desactivar, hacerlo ANTES de BEGIN; confirmar con PRAGMA
      foreign_keys que tomó efecto. Si no puede, abortar antes del rebuild.
    - BEGIN IMMEDIATE, llamar al núcleo único, commit; ante error rollback.
    - restaurar foreign_keys DESPUÉS de terminar la transacción al valor original
      y verificarlo.
    - integrity_check / foreign_key_check post-commit.
    - sin except Exception: pass que oculte fallos.
    """
    estado = _estado_cutover_identidad_b83(conn)
    if estado == "post":
        return False
    if conn.in_transaction:
        raise ValueError("B8.3 _asegurar_cutover_identidad_b83: se invocó con transacción abierta (conn.in_transaction=True); el caller debe preparar la conexión fuera de transacción sin commit sorpresa")
    fk_antes = conn.execute("PRAGMA foreign_keys").fetchone()
    if fk_antes is None or not isinstance(fk_antes, (list, tuple)) or len(fk_antes) < 1:
        raise ValueError(f"B8.3 no se pudo leer PRAGMA foreign_keys: retorno inesperado {fk_antes!r}")
    fk_val = fk_antes[0]
    if fk_val not in (0, 1):
        raise ValueError(f"B8.3 PRAGMA foreign_keys valor inesperado {fk_val!r}")
    original_fk = fk_val
    restaurar_fk = bool(fk_val)
    if restaurar_fk:
        conn.execute("PRAGMA foreign_keys=OFF")
        chk = conn.execute("PRAGMA foreign_keys").fetchone()
        if chk is None or not isinstance(chk, (list, tuple)) or len(chk) < 1:
            raise ValueError(f"B8.3 no se pudo verificar PRAGMA foreign_keys tras OFF: {chk!r}")
        if chk[0] != 0:
            try:
                conn.execute("PRAGMA foreign_keys=ON" if original_fk else "PRAGMA foreign_keys=OFF")
            except Exception as exc_try:
                raise RuntimeError(f"B8.3 no se pudo desactivar foreign_keys y restore inicial falló: {exc_try!r}") from exc_try
            raise ValueError(f"B8.3 no se pudo desactivar foreign_keys antes de rebuild, PRAGMA sigue {chk[0]}")
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ejecutar_cutover_identidad_b83_en_transaccion(conn)
        conn.commit()
    except Exception as exc_orig:
        try:
            conn.rollback()
        except Exception as exc_rb:
            if restaurar_fk:
                try:
                    conn.execute("PRAGMA foreign_keys=ON")
                    chk_rb = conn.execute("PRAGMA foreign_keys").fetchone()
                    if chk_rb is None or chk_rb[0] != original_fk:
                        raise ValueError(f"B8.3 no se pudo restaurar foreign_keys tras rollback fallido, quedó {chk_rb}")
                except Exception as exc_fk:
                    raise RuntimeError(f"B8.3 rollback falló tras error original {exc_orig!r}: {exc_rb!r}; restore FK falló: {exc_fk!r}") from exc_orig
            raise RuntimeError(f"B8.3 rollback falló tras error original {exc_orig!r}: {exc_rb!r}") from exc_orig
        if restaurar_fk:
            try:
                conn.execute("PRAGMA foreign_keys=ON")
                chk2 = conn.execute("PRAGMA foreign_keys").fetchone()
                if chk2 is None or chk2[0] != original_fk:
                    raise ValueError(f"B8.3 no se pudo restaurar foreign_keys a {original_fk}, quedó {chk2}")
            except Exception as exc_restore:
                raise RuntimeError(f"B8.3 restore foreign_keys falló tras error original {exc_orig!r}: {exc_restore!r}") from exc_orig
        raise
    if restaurar_fk:
        conn.execute("PRAGMA foreign_keys=ON")
        chk2 = conn.execute("PRAGMA foreign_keys").fetchone()
        if chk2 is None or chk2[0] != original_fk:
            raise ValueError(f"B8.3 no se pudo restaurar foreign_keys a {original_fk}, quedó {chk2}")
    chk = conn.execute("PRAGMA integrity_check").fetchone()
    if chk and chk[0] != "ok":
        raise ValueError(f"B8.3 integrity_check falló post-migración: {chk[0]!r}")
    fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_check:
        raise ValueError(f"B8.3 foreign_key_check no vacío post-migración: {fk_check}")
    return True


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
            nombre TEXT NOT NULL,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL,
            duracion_segundos REAL,
            ancho INTEGER,
            alto INTEGER,
            codec_video TEXT,
            cantidad_miniaturas INTEGER,
            tamano_bytes INTEGER,
            mtime_ns INTEGER,
            ruta_normalizada TEXT NOT NULL
        )
    """)
    _asegurar_columnas_videos(conn)
    _asegurar_ruta_normalizada(conn)
    # DB nueva nace post-cutover con índice único explícito (si _asegurar_ruta no lo creó por fast-path, crear aquí)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_ruta_normalizada ON videos(ruta_normalizada)")
    # Confirmar migraciones previas para permitir BEGIN IMMEDIATE limpio en B8.3
    if conn.in_transaction:
        conn.commit()
    _asegurar_cutover_identidad_b83(conn)
    # Si el cutover hizo COMMIT interno, la conexión queda fuera de transacción; asegurar que tablas auxiliares se crean en autocommit
    if conn.in_transaction:
        conn.commit()
    _asegurar_tabla_marcadores(conn)
    _asegurar_tabla_segmentos(conn)
    _asegurar_tablas_derivados(conn)
    if conn.in_transaction:
        conn.commit()
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
        base = os.path.splitext(nombre)[0]
        # B7.4 fix-027: match preciso _<digitos> para evitar colisión entre video y video_001
        if not base.startswith(prefijo + "_"):
            continue
        if _es_archivo_preview(nombre, video):
            continue
        suffix = base[len(prefijo):]  # _NN
        if not suffix.startswith("_"):
            continue
        rest = suffix[1:]
        if not rest.isdigit():
            continue
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
    def _es_miniatura(nombre):
        base = os.path.splitext(nombre)[0]
        if not base.startswith(prefijo + "_"):
            return False
        if _es_archivo_preview(nombre, video):
            return False
        suffix = base[len(prefijo):]
        if not suffix.startswith("_"):
            return False
        return suffix[1:].isdigit()
    return sum(1 for nombre in os.listdir(carpeta) if _es_miniatura(nombre))

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


# ── B8.2 — Caché por video_id (namespace v<id>_<NN>.jpg) ──
def _validar_video_id_cache(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, int):
        raise TypeError("video_id debe ser entero")
    if video_id <= 0:
        raise ValueError("video_id debe ser positivo")


def ruta_miniatura_id(video_id, indice=1):
    """B8.2 ruta de miniatura por video_id: v<id>_<NN>.jpg"""
    _validar_video_id_cache(video_id)
    if not isinstance(indice, int) or isinstance(indice, bool) or indice < 1:
        raise ValueError("indice debe ser entero >=1")
    return os.path.join(ruta_carpeta_miniaturas(), f"v{video_id}_{indice:02d}{EXTENSION_MINIATURA}")


def ruta_preview_id(video_id, indice):
    """B8.2 ruta de preview por video_id: v<id>_preview_<NN>.jpg"""
    _validar_video_id_cache(video_id)
    if not isinstance(indice, int) or isinstance(indice, bool) or indice < 1:
        raise ValueError("indice debe ser entero >=1")
    return os.path.join(ruta_carpeta_miniaturas(), f"v{video_id}_preview_{indice:02d}{EXTENSION_MINIATURA}")


def _es_archivo_preview_id(nombre_archivo, video_id):
    return os.path.splitext(nombre_archivo)[0].startswith(f"v{video_id}_preview_")

def _es_miniatura_id(nombre_archivo, video_id):
    base = os.path.splitext(nombre_archivo)[0]
    pref = f"v{video_id}_"
    if not base.startswith(pref):
        return False
    if _es_archivo_preview_id(nombre_archivo, video_id):
        return False
    suffix = base[len(pref):]
    return suffix.isdigit()

def contar_miniaturas_por_id(video_id):
    _validar_video_id_cache(video_id)
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return 0
    return sum(1 for n in os.listdir(carpeta) if _es_miniatura_id(n, video_id))

def siguiente_indice_libre_por_id(video_id):
    _validar_video_id_cache(video_id)
    indice = 1
    while os.path.isfile(ruta_miniatura_id(video_id, indice)):
        indice += 1
    return indice

def miniatura_reutilizable_por_id(video_id, ruta_video):
    """B8.2 contrato canónico: solo la miniatura principal v<id>_01.jpg es vigente.

    Itera solo la canónica determinista sin FS pesado (1 stat), no acumula _02.
    Si _01 no existe o está stale, retorna None para que el caller regenere canónica.
    """
    _validar_video_id_cache(video_id)
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return None
    ruta = ruta_miniatura_id(video_id, 1)
    if os.path.isfile(ruta) and miniatura_vigente(ruta_video, ruta):
        return ruta
    return None

def _previews_canonicos_reales_por_id(video_id):
    """B8.3A enumerador privado — todos los previews canónicos reales v<id>_preview_<NN>.jpg.

    - Valida video_id.
    - Obtiene carpeta cache; si no existe retorna [] (no es fallo).
    - Enumera exclusivamente con regex exacta ^v<id>_preview_(\\d+)\\.jpg$ case-insensitive.
    - v1 no captura v10 (regex anclada con id exacto).
    - Ignora legacy por nombre.
    - Ordena por índice numérico.
    - No depende de CANTIDAD_PREVIEWS.
    - Si os.listdir falla por OSError en carpeta existente, PROPAGA OSError para que
      el caller (replicar_cache_por_id) reporte fallo determinista.
    - Errores al comprobar archivo individual pueden ignorar solo ese archivo.
    """
    _validar_video_id_cache(video_id)
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return []
    # Si carpeta existe y listdir falla, propagar OSError (no silenciar como vacío)
    archivos = os.listdir(carpeta)  # propaga OSError
    pat = re.compile(rf"^v{re.escape(str(video_id))}_preview_(\d+)\.jpg$", re.IGNORECASE)
    pares = []
    for fname in archivos:
        m = pat.match(fname)
        if not m:
            continue
        try:
            idx = int(m.group(1))
        except ValueError:
            continue
        if idx < 1:
            continue
        ruta = os.path.join(carpeta, fname)
        try:
            if not os.path.isfile(ruta):
                continue
        except OSError:
            continue
        pares.append((idx, ruta))
    pares.sort(key=lambda x: x[0])
    return [p for _, p in pares]


def previews_existentes_por_id(video_id):
    """B8.2 — previews existentes configurados 1..CANTIDAD_PREVIEWS (contrato compartido).

    Solo los previews configurados que existen en FS. No enumera todos los reales.
    """
    _validar_video_id_cache(video_id)
    return [ruta_preview_id(video_id, i) for i in range(1, CANTIDAD_PREVIEWS + 1) if os.path.isfile(ruta_preview_id(video_id, i))]

def previews_faltantes_por_id(video_id):
    _validar_video_id_cache(video_id)
    return [i for i in range(1, CANTIDAD_PREVIEWS+1) if not os.path.isfile(ruta_preview_id(video_id, i))]

def _duracion_de_duraciones_por_id(duraciones, video_id, ruta_video):
    if not isinstance(duraciones, dict):
        return None
    if ruta_video in duraciones:
        return duraciones[ruta_video]
    # también soportar clave por video_id
    if video_id in duraciones:
        return duraciones[video_id]
    return None

def asegurar_miniatura_por_id(video_id, ruta_video, duracion_segundos=None):
    """B8.2 contrato canónico: principal es v<id>_01.jpg; si está stale se reemplaza atómicamente.

    No acumula _02 para la principal. Operación segura: genera a temporal + os.replace,
    no destruye vigente previa sin reemplazo válido. No toca legacy.
    """
    _validar_video_id_cache(video_id)
    if not ffmpeg_disponible() or not os.path.isfile(ruta_video) or os.path.getsize(ruta_video)==0:
        return 0
    destino = ruta_miniatura_id(video_id, 1)
    if os.path.isfile(destino) and miniatura_vigente(ruta_video, destino):
        return 1
    os.makedirs(ruta_carpeta_miniaturas(), exist_ok=True)
    # Generar a temporal adyacente para replace atómico (no borrar stale hasta validar)
    carpeta = ruta_carpeta_miniaturas()
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=EXTENSION_MINIATURA, prefix=f"tmp_v{video_id}_", dir=carpeta)
        os.close(fd)
        # generar_miniatura escribe directamente a ruta destino; le damos tmp
        # Necesita FFmpeg real; si falla, limpiar tmp y no tocar destino
        ok = generar_miniatura(ruta_video, tmp_path, duracion_segundos)
        if not ok or not os.path.isfile(tmp_path) or os.path.getsize(tmp_path)==0:
            try:
                if tmp_path and os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return 0
        # Reemplazo atómico: preserva destino previo hasta tener reemplazo válido
        try:
            os.replace(tmp_path, destino)
        except OSError:
            try:
                if tmp_path and os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return 0
        return 1 if os.path.isfile(destino) and os.path.getsize(destino)>0 else 0
    except (OSError, ValueError, TypeError):
        try:
            if tmp_path and os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return 0

def asegurar_miniaturas_por_id(video_ids, rutas_por_id, on_progreso=None, duraciones=None, nombres_por_id=None):
    """B8.2 asegura miniaturas por video_id (usa rutas por id, no nombres).

    Si `nombres_por_id` se provee, intenta migrar caché legacy (copia) antes de decidir
    si necesita FFmpeg, preservando legacy y siendo idempotente. Fallos de migración
    quedan observables en el resultado (campo migracion_fallos/errores) sin borrar origen.
    """
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser colección, no texto")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser colección iterable") from None
    for vid in lista:
        _validar_video_id_cache(vid)
    if rutas_por_id is None or not isinstance(rutas_por_id, dict):
        raise TypeError("rutas_por_id debe ser dict video_id->ruta")
    resultados=[]
    total=len(lista)
    migracion_fallos_total=0
    migracion_copiados_total=0
    migracion_ya_existentes_total=0
    migracion_detalles=[]
    for idx, vid in enumerate(lista):
        ruta_video = rutas_por_id.get(vid)
        if not isinstance(ruta_video, str) or not ruta_video or not os.path.isfile(ruta_video):
            resultados.append({"video_id": vid, "ruta": ruta_video, "asegurada":0, "cantidad_miniaturas": contar_miniaturas_por_id(vid), "migracion_fallos":0})
            if on_progreso: on_progreso(idx+1,total)
            continue
        mig_fallos=0
        mig_res=None
        if nombres_por_id and vid in nombres_por_id:
            try:
                mig_res = migrar_cache_legacy_a_id(vid, nombres_por_id[vid])
                mig_fallos = int(mig_res.get("fallos",0)) if isinstance(mig_res, dict) else 0
                migracion_fallos_total += mig_fallos
                migracion_copiados_total += int(mig_res.get("copiados",0)) if isinstance(mig_res, dict) else 0
                migracion_ya_existentes_total += int(mig_res.get("ya_existentes",0)) if isinstance(mig_res, dict) else 0
                if isinstance(mig_res, dict):
                    migracion_detalles.append({"video_id": vid, "migracion": mig_res})
            except (OSError, ValueError, TypeError) as exc:
                print(f"[B8.2] migrar_cache_legacy_a_id miniatura vid={vid} error: {exc}")
                mig_fallos = 1
                migracion_fallos_total += 1
                migracion_detalles.append({"video_id": vid, "error": str(exc), "estado":"excepcion"})
        dur = _duracion_de_duraciones_por_id(duraciones, vid, ruta_video)
        aseg = asegurar_miniatura_por_id(vid, ruta_video, dur)
        item={"video_id": vid, "ruta": ruta_video, "asegurada": aseg, "cantidad_miniaturas": contar_miniaturas_por_id(vid), "migracion_fallos": mig_fallos}
        if mig_res is not None:
            item["migracion"] = mig_res
        # reflejar fallo observable también en errores si hubo fallo
        if mig_fallos>0:
            item["errores"] = mig_fallos
        resultados.append(item)
        if on_progreso: on_progreso(idx+1,total)
    return {"video_ids": lista, "resultados": resultados, "procesados": len(resultados), "con_miniatura": sum(1 for r in resultados if r["cantidad_miniaturas"]>0), "sin_miniatura": sum(1 for r in resultados if r["cantidad_miniaturas"]==0), "migracion_fallos": migracion_fallos_total, "migracion_copiados": migracion_copiados_total, "migracion_ya_existentes": migracion_ya_existentes_total, "migracion_detalles": migracion_detalles, "errores": migracion_fallos_total}

def generar_previews_faltantes_por_id(video_ids, rutas_por_id, duraciones=None, nombres_por_id=None):
    if isinstance(video_ids, (str, bytes, bytearray)):
        raise TypeError("video_ids debe ser colección, no texto")
    try:
        lista = list(video_ids)
    except TypeError:
        raise TypeError("video_ids debe ser colección iterable") from None
    for vid in lista:
        _validar_video_id_cache(vid)
    if rutas_por_id is None or not isinstance(rutas_por_id, dict):
        raise TypeError("rutas_por_id debe ser dict")
    resultados=[]
    migracion_fallos_total=0
    migracion_copiados_total=0
    migracion_detalles=[]
    for vid in lista:
        mig_fallos=0
        mig_res=None
        if nombres_por_id and vid in nombres_por_id:
            try:
                if len(previews_existentes_por_id(vid)) < CANTIDAD_PREVIEWS:
                    mig_res = migrar_cache_legacy_a_id(vid, nombres_por_id[vid])
                    mig_fallos = int(mig_res.get("fallos",0)) if isinstance(mig_res, dict) else 0
                    migracion_fallos_total += mig_fallos
                    migracion_copiados_total += int(mig_res.get("copiados",0)) if isinstance(mig_res, dict) else 0
                    if isinstance(mig_res, dict):
                        migracion_detalles.append({"video_id": vid, "migracion": mig_res})
            except (OSError, ValueError, TypeError) as exc:
                print(f"[B8.2] migrar_cache_legacy_a_id previews vid={vid} error: {exc}")
                mig_fallos = 1
                migracion_fallos_total += 1
                migracion_detalles.append({"video_id": vid, "error": str(exc), "estado":"excepcion"})
        ruta_video = rutas_por_id.get(vid)
        faltantes = previews_faltantes_por_id(vid)
        generados=reutilizados=errores=0
        dur = _duracion_de_duraciones_por_id(duraciones, vid, ruta_video if isinstance(ruta_video,str) else "")
        if faltantes and isinstance(ruta_video,str) and ruta_video:
            os.makedirs(ruta_carpeta_miniaturas(), exist_ok=True)
            base=None
            if os.path.isfile(ruta_video):
                base=miniatura_reutilizable_por_id(vid, ruta_video)
            for indice in faltantes:
                dest=ruta_preview_id(vid, indice)
                if os.path.isfile(ruta_video) and os.path.getsize(ruta_video)>0 and generar_preview(ruta_video, dest, indice, dur):
                    generados+=1
                elif base is not None and os.path.isfile(base):
                    try:
                        shutil.copyfile(base, dest)
                        reutilizados+=1
                    except OSError:
                        errores+=1
                else:
                    errores+=1
        # incorporar fallos de migración como errores observables (sin ocultar)
        if mig_fallos>0:
            errores += mig_fallos
        previews=previews_existentes_por_id(vid)
        item={"video_id": vid, "ruta": ruta_video, "previews": previews, "generados":generados, "reutilizados":reutilizados, "errores":errores, "completos": len(previews)>=CANTIDAD_PREVIEWS, "migracion_fallos": mig_fallos}
        if mig_res is not None:
            item["migracion"] = mig_res
        resultados.append(item)
    return {"video_ids": lista, "resultados": resultados, "procesados": len(resultados), "con_previews": sum(1 for r in resultados if r["previews"]), "sin_previews": sum(1 for r in resultados if not r["previews"]), "completos": sum(1 for r in resultados if r["completos"]), "generados": sum(r["generados"] for r in resultados), "reutilizados": sum(r["reutilizados"] for r in resultados), "errores": sum(r["errores"] for r in resultados), "migracion_fallos": migracion_fallos_total, "migracion_copiados": migracion_copiados_total, "migracion_detalles": migracion_detalles}

def migrar_cache_legacy_a_id(video_id, nombre):
    """B8.2 migra copia no destructiva de caché legacy (por nombre) a namespace por id.

    Copia cada archivo legacy `prefix_*.jpg` y `prefix_preview_*.jpg` a `v<id>_*.jpg`.
    Idempotente, no borra legacy, valida copia. Fallo en un archivo no afecta otros.
    Retorna dict con copiados, ya_existentes, fallos.
    """
    _validar_video_id_cache(video_id)
    if not isinstance(nombre, str) or not nombre:
        raise ValueError("nombre debe ser texto no vacío")
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return {"copiados":0, "ya_existentes":0, "fallos":0, "detalles":[]}
    pref = _nombre_seguro(os.path.splitext(nombre)[0])
    detalles=[]
    copiados=ya_existentes=fallos=0
    try:
        archivos = os.listdir(carpeta)
    except OSError:
        return {"copiados":0, "ya_existentes":0, "fallos":0, "detalles":[]}
    for fname in archivos:
        base, ext = os.path.splitext(fname)
        if ext.lower() != EXTENSION_MINIATURA:
            continue
        # detectar si es legacy de este nombre
        if not base.startswith(pref + "_"):
            continue
        # distinguir preview vs miniatura
        is_preview = base.startswith(pref + "_preview_")
        if is_preview:
            suffix = base[len(pref + "_preview_"):]
            if not suffix.isdigit():
                continue
            try:
                idx = int(suffix)
            except ValueError:
                continue
            dest_name = f"v{video_id}_preview_{idx:02d}{EXTENSION_MINIATURA}"
        else:
            suffix = base[len(pref)+1:]
            if not suffix.isdigit():
                continue
            # evitar confundir preview ya filtrado
            if "_preview_" in base:
                continue
            try:
                idx = int(suffix)
            except ValueError:
                continue
            dest_name = f"v{video_id}_{idx:02d}{EXTENSION_MINIATURA}"
        src = os.path.join(carpeta, fname)
        dst = os.path.join(carpeta, dest_name)
        if os.path.isfile(dst):
            ya_existentes+=1
            detalles.append({"src": fname, "dst": dest_name, "estado":"ya_existe"})
            continue
        # B8.2 atomic: copiar a temporal adyacente + os.replace para evitar carrera check+copyfile
        tmp_dst = None
        try:
            fd, tmp_dst = tempfile.mkstemp(suffix=EXTENSION_MINIATURA, prefix=f"tmp_mig_v{video_id}_", dir=carpeta)
            os.close(fd)
            try:
                shutil.copyfile(src, tmp_dst)
            except OSError as exc:
                fallos+=1
                detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo_copy:{exc}"})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            # validar temporal
            try:
                if not os.path.isfile(tmp_dst) or os.path.getsize(tmp_dst)==0:
                    fallos+=1
                    detalles.append({"src": fname, "dst": dest_name, "estado":"fallo_validacion_tmp"})
                    try:
                        if tmp_dst and os.path.isfile(tmp_dst):
                            os.remove(tmp_dst)
                    except OSError:
                        pass
                    continue
            except OSError as exc:
                fallos+=1
                detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo_stat:{exc}"})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            # replace atómico: si dst apareció entre tanto (carrera), ya_existentes
            if os.path.isfile(dst):
                ya_existentes+=1
                detalles.append({"src": fname, "dst": dest_name, "estado":"ya_existe_carrera"})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            try:
                os.replace(tmp_dst, dst)
            except OSError as exc:
                fallos+=1
                detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo_replace:{exc}"})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            # validar destino final
            try:
                if os.path.isfile(dst) and os.path.getsize(dst)>0:
                    copiados+=1
                    detalles.append({"src": fname, "dst": dest_name, "estado":"copiado"})
                else:
                    fallos+=1
                    detalles.append({"src": fname, "dst": dest_name, "estado":"fallo_validacion_dst"})
            except OSError as exc:
                fallos+=1
                detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo_validacion2:{exc}"})
        except OSError as exc:
            fallos+=1
            detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo_tmp:{exc}"})
            try:
                if tmp_dst and os.path.isfile(tmp_dst):
                    os.remove(tmp_dst)
            except OSError:
                pass
        except (ValueError, TypeError) as exc:
            fallos+=1
            detalles.append({"src": fname, "dst": dest_name, "estado":f"fallo:{exc}"})
            try:
                if tmp_dst and os.path.isfile(tmp_dst):
                    os.remove(tmp_dst)
            except OSError:
                pass
    # limpieza huérfanos: ningún tmp_mig_* debe quedar (defensivo, ya limpiados)
    return {"copiados": copiados, "ya_existentes": ya_existentes, "fallos": fallos, "detalles": detalles}


def replicar_cache_por_id(video_id_origen, video_id_destino):
    """B8.3A — réplica canónica de caché entre dos video_id distintos (no destructiva).

    Copia miniatura v<origen>_01.jpg -> v<destino>_01.jpg y cada preview
    v<origen>_preview_<NN>.jpg -> v<destino>_preview_<NN>.jpg si origen existe
    y destino no existe. Usa temporales adyacentes + os.replace para carrera
    segura, no borra origen, no sobrescribe destino existente. No genera FFmpeg.

    Retorna dict {copiados, ya_existentes, fallos, detalles} con listas por archivo.
    Si origen == destino retorna sin operación (0 copiados).
    """
    _validar_video_id_cache(video_id_origen)
    _validar_video_id_cache(video_id_destino)
    if video_id_origen == video_id_destino:
        return {"copiados": 0, "ya_existentes": 0, "fallos": 0, "detalles": [], "mini_copiadas": 0, "preview_copiadas": 0}
    carpeta = ruta_carpeta_miniaturas()
    if not isinstance(carpeta, str) or not carpeta or not os.path.isdir(carpeta):
        return {"copiados": 0, "ya_existentes": 0, "fallos": 0, "detalles": [], "mini_copiadas": 0, "preview_copiadas": 0}
    pares = []
    # miniatura 01 canónica
    src_mini = ruta_miniatura_id(video_id_origen, 1)
    dst_mini = ruta_miniatura_id(video_id_destino, 1)
    if os.path.isfile(src_mini):
        pares.append((src_mini, dst_mini, False, 1))
    # B8.3A — previews REALES via enumerador privado aislado, no limitado por CANTIDAD_PREVIEWS
    fallo_enumeracion = None
    previews_reales = []
    try:
        previews_reales = _previews_canonicos_reales_por_id(video_id_origen)
    except OSError as exc:
        fallo_enumeracion = exc
        previews_reales = []
    if fallo_enumeracion is None:
        for src_p in previews_reales:
            fname = os.path.basename(src_p)
            m = re.match(rf"^v{re.escape(str(video_id_origen))}_preview_(\d+)\.jpg$", fname, re.IGNORECASE)
            if not m:
                continue
            try:
                idx = int(m.group(1))
            except ValueError:
                continue
            if idx < 1:
                continue
            if not os.path.isfile(src_p):
                continue
            dst_p = ruta_preview_id(video_id_destino, idx)
            pares.append((src_p, dst_p, True, idx))
    if not pares:
        if fallo_enumeracion is not None:
            return {"copiados": 0, "ya_existentes": 0, "fallos": 1, "detalles": [{"src": "", "dst": "", "estado": f"fallo_enumeracion_previews:{fallo_enumeracion}", "preview": True}], "mini_copiadas": 0, "preview_copiadas": 0}
        return {"copiados": 0, "ya_existentes": 0, "fallos": 0, "detalles": [], "mini_copiadas": 0, "preview_copiadas": 0}
    copiados = ya_existentes = 0
    fallos = 1 if fallo_enumeracion is not None else 0
    mini_copiadas = preview_copiadas = 0
    detalles = []
    if fallo_enumeracion is not None:
        detalles.append({"src": "", "dst": "", "estado": f"fallo_enumeracion_previews:{fallo_enumeracion}", "preview": True})
    for src, dst, es_preview, idx in pares:
        if os.path.isfile(dst):
            ya_existentes += 1
            detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": "ya_existe", "preview": es_preview})
            continue
        tmp_dst = None
        try:
            fd, tmp_dst = tempfile.mkstemp(suffix=EXTENSION_MINIATURA, prefix=f"tmp_rep_v{video_id_destino}_", dir=carpeta)
            os.close(fd)
            try:
                shutil.copyfile(src, tmp_dst)
            except OSError as exc:
                fallos += 1
                detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": f"fallo_copy:{exc}", "preview": es_preview})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            try:
                if not os.path.isfile(tmp_dst) or os.path.getsize(tmp_dst) == 0:
                    fallos += 1
                    detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": "fallo_validacion_tmp", "preview": es_preview})
                    try:
                        if tmp_dst and os.path.isfile(tmp_dst):
                            os.remove(tmp_dst)
                    except OSError:
                        pass
                    continue
            except OSError as exc:
                fallos += 1
                detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": f"fallo_stat:{exc}", "preview": es_preview})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            if os.path.isfile(dst):
                ya_existentes += 1
                detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": "ya_existe_carrera", "preview": es_preview})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            try:
                os.replace(tmp_dst, dst)
            except OSError as exc:
                fallos += 1
                detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": f"fallo_replace:{exc}", "preview": es_preview})
                try:
                    if tmp_dst and os.path.isfile(tmp_dst):
                        os.remove(tmp_dst)
                except OSError:
                    pass
                continue
            try:
                if os.path.isfile(dst) and os.path.getsize(dst) > 0:
                    copiados += 1
                    if es_preview:
                        preview_copiadas += 1
                    else:
                        mini_copiadas += 1
                    detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": "copiado", "preview": es_preview})
                else:
                    fallos += 1
                    detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": "fallo_validacion_dst", "preview": es_preview})
            except OSError as exc:
                fallos += 1
                detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": f"fallo_validacion2:{exc}", "preview": es_preview})
        except OSError as exc:
            fallos += 1
            detalles.append({"src": os.path.basename(src) if 'src' in locals() else str(src), "dst": os.path.basename(dst) if 'dst' in locals() else str(dst), "estado": f"fallo_tmp:{exc}", "preview": es_preview})
            try:
                if tmp_dst and os.path.isfile(tmp_dst):
                    os.remove(tmp_dst)
            except OSError:
                pass
        except (ValueError, TypeError) as exc:
            fallos += 1
            detalles.append({"src": os.path.basename(src), "dst": os.path.basename(dst), "estado": f"fallo:{exc}", "preview": es_preview})
            try:
                if tmp_dst and os.path.isfile(tmp_dst):
                    os.remove(tmp_dst)
            except OSError:
                pass
    return {"copiados": copiados, "ya_existentes": ya_existentes, "fallos": fallos, "detalles": detalles, "mini_copiadas": mini_copiadas, "preview_copiadas": preview_copiadas}


# alias histórico B8.2 si existe para compatibilidad externa
copiar_cache_entre_ids = replicar_cache_por_id

def migrar_toda_cache_legacy(ruta_db=None):
    """Migra toda la caché legacy para todos los videos (batch)."""
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        filas = conn.execute("SELECT id, nombre FROM videos").fetchall()
    finally:
        conn.close()
    total_copiados=0
    for vid, nombre in filas:
        res = migrar_cache_legacy_a_id(vid, nombre)
        total_copiados+=res["copiados"]
    return {"videos": len(filas), "copiados": total_copiados}

def insertar_video(conn, carpeta, nombre):
    extension = os.path.splitext(nombre)[1].lower()
    ruta = os.path.join(carpeta, nombre)
    fecha = datetime.now().isoformat()
    try:
        ruta_norm = normalizar_ruta_clave(ruta)
    except Exception as exc:
        raise ValueError(f"B8.3 insertar_video: no se pudo normalizar ruta {ruta!r}: {exc}") from exc
    if not ruta_norm or not ruta_norm.strip():
        raise ValueError(f"B8.3 insertar_video: ruta_normalizada vacía para {ruta!r}")
    conn.execute(
        "INSERT OR IGNORE INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?, ?, ?, ?, ?)",
        (nombre, ruta, ruta_norm, extension, fecha),
    )

def actualizar_datos(conn, carpeta, nombre):
    ruta = os.path.join(carpeta, nombre)
    try:
        ruta_norm = normalizar_ruta_clave(ruta)
    except Exception as exc:
        raise ValueError(f"B8.3 actualizar_datos: no se pudo normalizar ruta {ruta!r}: {exc}") from exc
    if not ruta_norm or not ruta_norm.strip():
        raise ValueError(f"B8.3 actualizar_datos: ruta_normalizada vacía para {ruta!r}")
    es_vacio = os.path.getsize(ruta) == 0
    datos = None if es_vacio else obtener_datos_ffprobe(ruta)
    miniaturas = contar_miniaturas(nombre)
    tamano_bytes = os.path.getsize(ruta)
    if datos is None:
        conn.execute(
            "UPDATE videos SET duracion_segundos = NULL, ancho = NULL, alto = NULL, codec_video = NULL, cantidad_miniaturas = ?, tamano_bytes = ? WHERE ruta_normalizada = ?",
            (miniaturas, tamano_bytes, ruta_norm),
        )
    else:
        conn.execute(
            "UPDATE videos SET duracion_segundos = ?, ancho = ?, alto = ?, codec_video = ?, cantidad_miniaturas = ?, tamano_bytes = ? WHERE ruta_normalizada = ?",
            (datos["duracion_segundos"], datos["ancho"], datos["alto"], datos["codec_video"], miniaturas, tamano_bytes, ruta_norm),
        )

def sincronizar_bd(conn, carpeta):
    # B8.3A: scope-segura por ruta_normalizada + _es_subcarpeta; nunca borra fuera del árbol objetivo
    carpeta_abs = os.path.abspath(carpeta)
    try:
        carpeta_norm = normalizar_ruta_clave(carpeta_abs)
    except Exception as exc:
        raise ValueError(f"B8.3 sincronizar_bd: no se pudo normalizar carpeta {carpeta!r}: {exc}") from exc
    if not carpeta_norm or not carpeta_norm.strip():
        raise ValueError(f"B8.3 sincronizar_bd: carpeta_norm vacía para {carpeta!r}")
    en_disco = set(escanear_videos(carpeta))
    en_disco_norm = {}
    for nombre in en_disco:
        ruta = os.path.join(carpeta, nombre)
        try:
            norm = normalizar_ruta_clave(ruta)
        except Exception as exc:
            raise ValueError(f"B8.3 sincronizar_bd: no se pudo normalizar ruta en disco {ruta!r}: {exc}") from exc
        if not norm or not norm.strip():
            raise ValueError(f"B8.3 sincronizar_bd: ruta_normalizada vacía para {ruta!r}")
        en_disco_norm[norm] = nombre
    filas = conn.execute("SELECT id, ruta, ruta_normalizada FROM videos").fetchall()
    en_bd_norm_scope = set()
    # validar y colectar solo filas dentro del scope
    for fid, ruta, ruta_norm in filas:
        if ruta_norm is None or (isinstance(ruta_norm, str) and not ruta_norm.strip()):
            raise ValueError(f"B8.3 sincronizar_bd: ruta_normalizada NULL/vacía para id={fid}, se preservan datos")
        norm = ruta_norm
        # solo considerar para eliminación las que están dentro del árbol objetivo
        if _es_subcarpeta(carpeta_norm, norm):
            en_bd_norm_scope.add(norm)
    for norm, nombre in en_disco_norm.items():
        insertar_video(conn, carpeta, nombre)
    for norm, nombre in en_disco_norm.items():
        asegurar_miniatura(nombre, os.path.join(carpeta, nombre))
        actualizar_datos(conn, carpeta, nombre)
    # borrar solo dentro del scope, por ruta_normalizada exacta
    for norm in en_bd_norm_scope - set(en_disco_norm.keys()):
        conn.execute("DELETE FROM videos WHERE ruta_normalizada = ?", (norm,))

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


def listar_registros_por_rutas(rutas, ruta_db=None):
    """Registros por ruta_normalizada (B8.3), inequívoco para homónimos.

    `rutas` es colección de rutas absolutas (o relativas). Devuelve dict
    `{ruta_normalizada: {id, nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns}}`.
    Búsqueda por `ruta_normalizada` (identidad física única). `rutas` vacío -> {}.
    """
    if isinstance(rutas, (str, bytes, bytearray)):
        raise TypeError("rutas debe ser una colección, no texto")
    try:
        lista = list(rutas)
    except TypeError:
        raise TypeError("rutas debe ser una colección iterable") from None
    if not lista:
        return {}
    norms = []
    for r in lista:
        if not isinstance(r, str) or not r:
            continue
        try:
            n = normalizar_ruta_clave(r)
        except Exception:
            continue
        norms.append(n)
    if not norms:
        return {}
    # deduplicar para consulta
    norms_unicos = list(dict.fromkeys(norms))
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        por_norm = {}
        filas = conn.execute(
            """
            SELECT id, nombre, ruta, ruta_normalizada, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns
            FROM videos
            WHERE ruta_normalizada IN ({})
            """.format(",".join("?" * len(norms_unicos))),
            norms_unicos,
        ).fetchall()
        for fila in filas:
            por_norm[fila[3]] = {
                "id": fila[0],
                "nombre": fila[1],
                "ruta": fila[2],
                "ruta_normalizada": fila[3],
                "duracion_segundos": fila[4],
                "ancho": fila[5],
                "alto": fila[6],
                "codec_video": fila[7],
                "tamano_bytes": fila[8],
                "mtime_ns": fila[9],
            }
        return por_norm
    finally:
        conn.close()


# alias para compatibilidad con spec (ruta_normalizada -> clave)
listar_registros_por_rutas_normalizadas = listar_registros_por_rutas


def obtener_video_por_ruta_normalizada(ruta, ruta_db=None):
    """Helper B8.3A — lookup inequívoco por ruta física normalizada.

    Normaliza `ruta` vía `normalizar_ruta_clave`, busca por `ruta_normalizada`
    (identidad física única) y devuelve dict `{id, nombre, ruta, ruta_normalizada,
    extension, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns}`
    o None si no existe. No busca por `nombre`. Propaga errores de
    normalización/schema (ValueError, FileNotFoundError) sin silenciar.
    """
    if not isinstance(ruta, str) or not ruta.strip():
        raise ValueError("ruta debe ser texto no vacío")
    ruta_norm = normalizar_ruta_clave(ruta)
    if not ruta_norm or not ruta_norm.strip():
        raise ValueError(f"B8.3 ruta_normalizada vacía para {ruta!r}")
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = conectar_bd(ruta_db)
    try:
        fila = conn.execute(
            """
            SELECT id, nombre, ruta, ruta_normalizada, extension, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns
            FROM videos WHERE ruta_normalizada = ?
            """,
            (ruta_norm,),
        ).fetchone()
        if fila is None:
            return None
        return {
            "id": fila[0],
            "nombre": fila[1],
            "ruta": fila[2],
            "ruta_normalizada": fila[3],
            "extension": fila[4],
            "duracion_segundos": fila[5],
            "ancho": fila[6],
            "alto": fila[7],
            "codec_video": fila[8],
            "tamano_bytes": fila[9],
            "mtime_ns": fila[10],
        }
    finally:
        conn.close()


def buscar_colision_ruta_video(ruta, ruta_db=None, excluir_id=None):
    """Helper B8.3A — detecta colisión exacta de destino físico normalizado.

    Normaliza `ruta`, busca fila con misma `ruta_normalizada`. Si `excluir_id`
    no es None, ignora esa fila (mismo video, no-op válido). Devuelve dict del
    video colisionante o None si destino libre. No busca por nombre.
    """
    if excluir_id is not None:
        if isinstance(excluir_id, bool) or not isinstance(excluir_id, int):
            raise TypeError("excluir_id debe ser entero o None")
        if excluir_id <= 0:
            raise ValueError("excluir_id debe ser positivo")
    rec = obtener_video_por_ruta_normalizada(ruta, ruta_db)
    if rec is None:
        return None
    if excluir_id is not None and rec["id"] == excluir_id:
        return None
    return rec


def _es_subcarpeta(padre, ruta):
    if not isinstance(ruta, str) or not ruta:
        return False
    try:
        return os.path.commonpath([padre, ruta]) == padre
    except ValueError:
        return False


def eliminar_registros_de_carpetas_retiradas(ruta_db, carpetas_retiradas):
    """Helper puro backend B8.3A — elimina solo filas bajo carpetas retiradas.

    - Valida colección de carpetas strings.
    - Normaliza cada carpeta con normalizar_ruta_clave(os.path.abspath(...)).
    - Abre DB en capa backend, no UI.
    - SELECT id,ruta_normalizada; si NULL/vacía -> error visible, no adivinar por nombre.
    - Elimina SOLO filas cuya ruta_normalizada esté bajo alguna carpeta retirada usando _es_subcarpeta.
    - DELETE por id o ruta_normalizada exacta.
    - Transacción única, rollback visible en error, commit único.
    - Devuelve resumen determinista {eliminados, ids, rutas, carpetas_retiradas}.
    - No toca carpetas activas ni filas bajo carpetas nunca declaradas retiradas.
    """
    import threading
    if isinstance(carpetas_retiradas, (str, bytes, bytearray)):
        raise TypeError("carpetas_retiradas debe ser colección, no texto")
    try:
        lista = list(carpetas_retiradas) if carpetas_retiradas else []
    except TypeError:
        raise TypeError("carpetas_retiradas debe ser colección iterable") from None
    if not lista:
        return {"eliminados": 0, "ids": [], "rutas": [], "carpetas_retiradas": [], "thread_id": threading.get_ident(), "is_main_thread": threading.current_thread() is threading.main_thread()}
    carpetas_norm = []
    for c in lista:
        if not isinstance(c, str) or not c.strip():
            raise ValueError(f"carpeta retirada inválida: {c!r}")
        try:
            norm = normalizar_ruta_clave(os.path.abspath(c))
        except Exception as exc:
            raise ValueError(f"no se pudo normalizar carpeta retirada {c!r}: {exc}") from exc
        if not norm or not norm.strip():
            raise ValueError(f"carpeta retirada normalizada vacía: {c!r}")
        carpetas_norm.append(norm)
    # deduplicar
    carpetas_norm = list(dict.fromkeys(carpetas_norm))
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        # Validar que ninguna fila tenga ruta_normalizada NULL/vacía antes de borrar
        filas = conn.execute("SELECT id, ruta_normalizada FROM videos").fetchall()
        for fid, rn in filas:
            if rn is None or (isinstance(rn, str) and not rn.strip()):
                raise ValueError(f"ruta_normalizada NULL/vacía para id={fid}, no se puede decidir identidad exacta")
        borrar_ids = []
        borrar_rutas = []
        for fid, rn in filas:
            if not isinstance(rn, str) or not rn:
                continue
            for p in carpetas_norm:
                if _es_subcarpeta(p, rn):
                    borrar_ids.append(fid)
                    borrar_rutas.append(rn)
                    break
        if not borrar_ids:
            return {"eliminados": 0, "ids": [], "rutas": [], "carpetas_retiradas": list(lista), "thread_id": threading.get_ident(), "is_main_thread": threading.current_thread() is threading.main_thread()}
        # Transacción única
        try:
            conn.execute("BEGIN IMMEDIATE")
            for fid in borrar_ids:
                conn.execute("DELETE FROM videos WHERE id = ?", (fid,))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        return {"eliminados": len(borrar_ids), "ids": borrar_ids, "rutas": borrar_rutas, "carpetas_retiradas": list(lista), "thread_id": threading.get_ident(), "is_main_thread": threading.current_thread() is threading.main_thread()}
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    # B8.3: comparar por ruta_normalizada / normalizar_ruta_clave
    en_disco_nombres = set(escanear_videos(carpeta))
    en_disco_norm = {}
    en_disco_norm_set = set()
    for nombre in en_disco_nombres:
        ruta = os.path.join(carpeta, nombre)
        try:
            norm = normalizar_ruta_clave(ruta)
        except Exception:
            continue
        en_disco_norm[norm] = nombre
        en_disco_norm_set.add(norm)
    try:
        carpeta_norm = normalizar_ruta_clave(carpeta)
    except Exception:
        carpeta_norm = os.path.normcase(os.path.normpath(os.path.abspath(carpeta)))
    conn = sqlite3.connect(ruta_db)
    try:
        try:
            filas = conn.execute("SELECT nombre, ruta, ruta_normalizada FROM videos").fetchall()
        except sqlite3.OperationalError as e:
            if "no such column" in str(e).lower() and "ruta_normalizada" in str(e).lower():
                filas_raw = conn.execute("SELECT nombre, ruta FROM videos").fetchall()
                filas = [(n, r, None) for n, r in filas_raw]
            else:
                raise
    finally:
        conn.close()
    # construir sets por ruta_normalizada
    db_norm_to_info = {}
    db_norm_set = set()
    for nombre, ruta, ruta_norm in filas:
        norm = None
        if isinstance(ruta_norm, str) and ruta_norm:
            norm = ruta_norm
        elif isinstance(ruta, str) and ruta:
            try:
                norm = normalizar_ruta_clave(ruta)
            except Exception:
                continue
        if not norm:
            continue
        db_norm_set.add(norm)
        # guardar nombre para reporte (puede haber homónimos con mismo nombre pero distinto norm, mapeamos por norm)
        db_norm_to_info[norm] = nombre
    # B8.3A — protección por ruta_normalizada exacta, no por nombre
    protegidas_norm = []
    if carpetas_protegidas is not None:
        for c in list(carpetas_protegidas):
            if not isinstance(c, str) or not c.strip():
                continue
            try:
                pn = normalizar_ruta_clave(os.path.abspath(c))
            except Exception:
                try:
                    pn = os.path.normcase(os.path.normpath(os.path.abspath(c)))
                except Exception:
                    continue
            if pn:
                protegidas_norm.append(pn)
    # Filtrar protegidas que son ancestros de la carpeta actual: no deben proteger filas bajo la carpeta actual
    # Ej: procesando B con protegidas=[A] donde A es padre de B, filas bajo B también están bajo A pero deben considerarse ausentes de B
    protegidas_filtradas = []
    for pn in protegidas_norm:
        try:
            if _es_subcarpeta(pn, carpeta_norm):
                continue
        except Exception:
            pass
        protegidas_filtradas.append(pn)
    protegidas_norm = protegidas_filtradas
    presentes = []
    ausentes = []
    ausentes_rutas_normalizadas = []
    for nombre, ruta, ruta_norm in filas:
        norm = None
        if isinstance(ruta_norm, str) and ruta_norm:
            norm = ruta_norm
        elif isinstance(ruta, str) and ruta:
            try:
                norm = normalizar_ruta_clave(ruta)
            except Exception:
                continue
        if not norm:
            continue
        if norm in en_disco_norm_set:
            presentes.append(nombre)
            continue
        # Solo candidatos dentro del scope de carpeta
        if not _es_subcarpeta(carpeta_norm, norm):
            continue
        # Si está bajo alguna protegida, no es ausente de este scope
        protegido = False
        for pn in protegidas_norm:
            if _es_subcarpeta(pn, norm):
                protegido = True
                break
        if protegido:
            continue
        ausentes.append(nombre)
        ausentes_rutas_normalizadas.append(norm)
    nuevos = []
    for norm, nombre in en_disco_norm.items():
        if norm not in db_norm_set:
            nuevos.append(nombre)
    return {
        "carpeta": carpeta,
        "presentes_en_ambos": sorted(presentes),
        "nuevos": sorted(nuevos),
        "ausentes_del_disco": sorted(ausentes),
        "ausentes_rutas_normalizadas": sorted(ausentes_rutas_normalizadas),
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
    # B8.3A identidad exacta: transportar rutas normalizadas aditivas si existen
    candidatos_rutas = None
    if "ausentes_rutas_normalizadas" in diferencias:
        val = diferencias["ausentes_rutas_normalizadas"]
        if isinstance(val, (str, bytes, bytearray)):
            raise TypeError("ausentes_rutas_normalizadas debe ser colección, no texto")
        try:
            lista_r = list(val)
        except TypeError:
            raise TypeError("ausentes_rutas_normalizadas debe ser colección iterable") from None
        # validar strings
        candidatos_rutas = []
        for r in lista_r:
            if not isinstance(r, str) or not r.strip():
                raise ValueError(f"ruta normalizada inválida en ausentes_rutas_normalizadas: {r!r}")
            candidatos_rutas.append(r)
        candidatos_rutas = sorted(set(candidatos_rutas))
    else:
        candidatos_rutas = []
    return {
        "carpeta": carpeta,
        "a_incorporar": preparar_registros_basicos(nuevos, carpeta),
        "ya_sincronizados": presentes,
        "candidatos_a_eliminar": ausentes,
        "candidatos_a_eliminar_rutas": candidatos_rutas,
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
    carpeta = plan.get("carpeta")
    try:
        incorporados = len(plan["a_incorporar"])
    except TypeError:
        incorporados = None
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    # B8.3A — identidad exacta por ruta_normalizada, nunca por nombre global
    # Si plan no trae candidatos_a_eliminar_rutas, no se puede decidir identidad exacta -> error visible / cero borrados
    rutas_exactas = plan.get("candidatos_a_eliminar_rutas")
    if rutas_exactas is None:
        # Compatibilidad: si no hay rutas exactas y candidatos no vacío, exigir identidad exacta
        if candidatos:
            raise ValueError("eliminar_candidatos requiere candidatos_a_eliminar_rutas con identidad exacta por ruta_normalizada; no se permite borrar por nombre global (homónimos inequívocos)")
        rutas_exactas = []
    if isinstance(rutas_exactas, (str, bytes, bytearray)):
        raise TypeError("candidatos_a_eliminar_rutas debe ser colección, no texto")
    try:
        lista_rutas = list(rutas_exactas) if rutas_exactas else []
    except TypeError:
        raise TypeError("candidatos_a_eliminar_rutas debe ser colección iterable") from None
    # Validar y normalizar cada ruta exacta (ya deberían estar normalizadas, pero validar)
    rutas_norm = []
    for r in lista_rutas:
        if not isinstance(r, str) or not r.strip():
            raise ValueError(f"ruta normalizada candidata inválida: {r!r}")
        # Si ya parece normalizada (viene de detectar_diferencias), usar tal cual tras validar no vacía
        # Para robustez, si no está normalizada, intentar normalizar
        try:
            # Intentar verificar que es subcarpeta o al menos ruta válida; no re-normalizar ciegamente si ya es norm
            # Si r es absoluta, normalizar; si es relativa, error visible
            if os.path.isabs(r):
                # Si r ya es normalizada, normalizar de nuevo debe ser idempotente
                nr = normalizar_ruta_clave(r)
                rutas_norm.append(nr)
            else:
                # Puede ser ruta normalizada que incluye unidad en Windows pero isabs False en linux? Caso raro
                # Tratar como error visible si no es absoluta ni normalizada
                nr = normalizar_ruta_clave(os.path.abspath(r))
                rutas_norm.append(nr)
        except Exception as exc:
            raise ValueError(f"no se pudo validar ruta candidata {r!r}: {exc}") from exc
    rutas_norm = list(dict.fromkeys(rutas_norm))
    conn = sqlite3.connect(ruta_db)
    try:
        eliminados = []
        eliminados_rutas = []
        # Validar que no haya filas con ruta_normalizada NULL/vacía (integridad)
        # Si hay, error visible, no adivinar
        filas_check = conn.execute("SELECT id, ruta_normalizada FROM videos").fetchall()
        for fid, rn in filas_check:
            if rn is None or (isinstance(rn, str) and not rn.strip()):
                raise ValueError(f"ruta_normalizada NULL/vacía para id={fid}, no se puede eliminar por identidad exacta")
        for norm in rutas_norm:
            cursor = conn.execute("DELETE FROM videos WHERE ruta_normalizada = ?", (norm,))
            if cursor.rowcount:
                eliminados.append(norm)
                eliminados_rutas.append(norm)
        conn.commit()
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
    # Mantener compatibilidad de retorno: "nombres" sigue siendo lista de identificadores eliminados (ahora rutas)
    # Para consumidores históricos que esperaban basenames, devolvemos basenames derivados de rutas eliminadas + lista legacy candidatos que coincidían
    # Pero la eliminación real fue por ruta exacta
    nombres_eliminados = []
    for rn in eliminados_rutas:
        try:
            nombres_eliminados.append(os.path.basename(rn))
        except Exception:
            nombres_eliminados.append(rn)
    return {
        "eliminados": len(eliminados),
        "nombres": nombres_eliminados,
        "rutas": eliminados_rutas,
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


def _normalizar_carpeta_para_filtro(carpeta):
    """Normaliza carpeta para filtro SQL Windows-safe (B7.2 fix-017).

    Devuelve carpeta normalizada sin trailing sep (salvo raíz vacía -> None) usando
    normcase+normpath+abspath para case-insensitive en Windows y separadores
    coherentes. Para raíz C:\\ -> 'C:' (luego se reconstruye C:\\ en SQL).
    """
    if not isinstance(carpeta, str) or not carpeta.strip():
        return None
    try:
        abs_path = os.path.abspath(carpeta)
        norm = os.path.normcase(os.path.normpath(abs_path))
        # normpath ya quita trailing salvo raíz; uniformar quitando cualquier trailing restante
        # para que SQL construya prefijo con + '\\' de forma consistente (evita C:\\ vs C:\\\\)
        # Mantener 'C:' para raíz en lugar de 'C:\\'
        if len(norm) > 0:
            # quitar trailing / y \ (pero conservar 'C:' si resulta)
            stripped = norm.rstrip("/\\")
            if not stripped:
                return None
            # Si era raíz tipo 'C:\\' -> norm='C:\\' -> stripped='C:' -> devolver 'C:'
            # Si era '/' (Linux root) -> stripped='' -> None
            return stripped
        return None
    except Exception:
        return None


def _construir_filtro_carpeta_sql(carpeta, incluir_subcarpetas=False):
    """Fragmento WHERE para filtrar por carpeta de forma Windows-safe (B7.2 fix-017).

    - Usa lower(replace(...,'/','\\')) para case-insensitive y separadores.
    - Evita LIKE 'A%' ingenuo que confunde C:\\Videos\\A con C:\\Videos\\AB
      exigiendo separador tras carpeta.
    - Inmediata (default): ruta bajo carpeta con exactamente un nivel
      (prefix + filename sin separador extra).
    - Recursiva: ruta normalizada empieza con carpeta + sep (instr ==1).
    Devuelve (fragmento, params).
    """
    if carpeta is None:
        return ("", [])
    # Soportar lista de carpetas (selección personalizada)
    if isinstance(carpeta, (list, tuple, set)):
        fragmentos = []
        params = []
        for c in carpeta:
            frag, p = _construir_filtro_carpeta_sql(c, incluir_subcarpetas)
            if frag:
                fragmentos.append(f"({frag})")
                params.extend(p)
        if not fragmentos:
            return ("", [])
        return ("(" + " OR ".join(fragmentos) + ")", params)
    if not isinstance(carpeta, str):
        return ("", [])
    norm = _normalizar_carpeta_para_filtro(carpeta)
    if norm is None:
        return ("", [])
    if incluir_subcarpetas:
        # Recursiva: instr(lower(replace(ruta,'/','\\')), lower(replace(? || '\\','/','\\'))) =1
        # ? es norm sin trailing; se añade '\\' en SQL para exigir separador
        frag = "instr(lower(replace(ruta, '/', '\\')), lower(replace(? || '\\', '/', '\\'))) = 1"
        return (frag, [norm])
    else:
        # Inmediata: ruta empieza con carpeta+sep y resto sin separador
        # remainder = substr(ruta_normalizada, length(prefix)+1) debe no contener '\'
        frag = "(instr(lower(replace(ruta, '/', '\\')), lower(replace(? || '\\', '/', '\\'))) = 1 AND instr(substr(lower(replace(ruta, '/', '\\')), length(replace(? || '\\', '/', '\\')) + 1), '\\') = 0)"
        # Necesita norm dos veces (para instr y para length)
        return (frag, [norm, norm])


def listar_videos_paginado(
    limite,
    desplazamiento=0,
    texto=None,
    ruta_db=None,
    orden_clave=None,
    orden_direccion=None,
    filtro=None,
    carpeta=None,
    incluir_subcarpetas=False,
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
    # B7.2 fix-017: carpeta (Windows-safe, inmediata por defecto, no LIKE 'A%' sobre AB)
    if carpeta is not None and not isinstance(carpeta, (str, list, tuple, set)):
        raise TypeError("carpeta debe ser texto, lista o None")
    if incluir_subcarpetas is not None and not isinstance(incluir_subcarpetas, bool):
        raise TypeError("incluir_subcarpetas debe ser booleano")
    condiciones = []
    params_where = []
    if texto is not None:
        condiciones.append("nombre LIKE ?")
        params_where.append(f"%{texto}%")
    frag_filtro, params_filtro = _filtro_catalogo_exists(filtro)
    if frag_filtro:
        condiciones.append(frag_filtro)
        params_where.extend(params_filtro)
    # Filtro por carpeta (si se provee) — se evalúa en SQL antes de LIMIT/OFFSET
    if carpeta is not None:
        # Si carpeta es lista/tupla/set vacía -> sin filtro (compatibilidad: lista vacía = sin videos? Tratamos como sin filtro para no romper carga inicial sin carpeta)
        # Para evitar confusión, solo filtrar si hay al menos un elemento válido
        frag_carpeta, params_carpeta = _construir_filtro_carpeta_sql(carpeta, incluir_subcarpetas=bool(incluir_subcarpetas))
        if frag_carpeta:
            condiciones.append(frag_carpeta)
            params_where.extend(params_carpeta)
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
    # B8.3 identidad por ruta_normalizada: ON CONFLICT(ruta_normalizada) con nombre mutable
    ruta = datos["ruta"]
    ruta_normalizada = normalizar_ruta_clave(ruta)
    conn.execute(
        """
        INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ruta_normalizada) DO UPDATE SET
            nombre = excluded.nombre,
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
            ruta,
            ruta_normalizada,
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
    video_id = None
    try:
        # B8.3A: única transacción observable para T07/T09; NO tocar PRAGMA foreign_keys aquí.
        # El esquema actual no tiene FKs físicas hacia videos; el rebuild inline es seguro con FK ON.
        conn.execute("BEGIN IMMEDIATE")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        _ejecutar_cutover_identidad_b83_en_transaccion(conn)
        _upsert_video(conn, datos)
        ruta_norm = normalizar_ruta_clave(datos["ruta"])
        fila = conn.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?", (ruta_norm,)
        ).fetchone()
        video_id = fila[0] if fila else None
        conn.commit()
    except Exception as exc_orig:
        try:
            conn.rollback()
        except Exception as exc_rb:
            raise RuntimeError(f"B8.3 guardar_video rollback falló tras error original {exc_orig!r}: {exc_rb!r}") from exc_orig
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"guardado": True, "nombre": datos["nombre"], "video_id": video_id, "id": video_id}


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
    ids = []
    por_nombre = {}
    por_ruta_normalizada = {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        _ejecutar_cutover_identidad_b83_en_transaccion(conn)
        for indice, datos in enumerate(registros):
            _upsert_video(conn, datos)
            ruta_norm = normalizar_ruta_clave(datos["ruta"])
            fila = conn.execute(
                "SELECT id FROM videos WHERE ruta_normalizada = ?", (ruta_norm,)
            ).fetchone()
            vid = fila[0] if fila else None
            ids.append(vid)
            por_nombre[datos["nombre"]] = vid
            por_ruta_normalizada[ruta_norm] = vid
            if on_progreso is not None:
                on_progreso(indice + 1, total)
        conn.commit()
    except Exception as exc_orig:
        try:
            conn.rollback()
        except Exception as exc_rb:
            raise RuntimeError(f"B8.3 guardar_videos rollback falló tras error original {exc_orig!r}: {exc_rb!r}") from exc_orig
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "guardados": len(registros),
        "nombres": [d["nombre"] for d in registros],
        "ids": ids,
        "video_ids": list(ids),
        "por_nombre": dict(por_nombre),
        "por_ruta_normalizada": dict(por_ruta_normalizada),
    }

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
    _asegurar_columnas_videos(conn)
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
        # B8.3: validación por ruta_normalizada, homónimo en otra ruta permitido
        try:
            derivado_norm = normalizar_ruta_clave(derivado_ruta_abs)
        except Exception as exc:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 no se pudo normalizar ruta derivada {derivado_ruta_abs!r}: {exc}", "catalog_error": False}
        if not derivado_norm or not derivado_norm.strip():
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 ruta_normalizada vacía para {derivado_ruta_abs!r}", "catalog_error": False}
        fila_dup_ruta = conn.execute(
            "SELECT id, nombre, ruta FROM videos WHERE ruta_normalizada = ?",
            (derivado_norm,),
        ).fetchone()
        if fila_dup_ruta is not None:
            dup_id = fila_dup_ruta[0]
            return {"ok": False, "derivado_video_id": dup_id, "derivacion_id": None, "error": "derivado ya existe en catálogo (ruta duplicada)", "catalog_error": True}
        # mismo archivo que original (comparación normalizada)
        try:
            orig_norm = normalizar_ruta_clave(orig_ruta)
        except Exception as exc:
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 no se pudo normalizar ruta original {orig_ruta!r}: {exc}", "catalog_error": False}
        if derivado_norm == orig_norm:
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
    # Transacción de alta atómica: video + derivación + segmentos (B8.3 por ruta_normalizada)
    conn2 = None
    try:
        conn2 = _conectar_derivados(ruta_db)
        conn2.execute("BEGIN")
        try:
            derivado_norm2 = normalizar_ruta_clave(derivado_ruta_abs)
        except Exception as exc:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 no se pudo normalizar ruta derivada {derivado_ruta_abs!r}: {exc}", "catalog_error": False}
        if not derivado_norm2 or not derivado_norm2.strip():
            conn2.rollback()
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 ruta_normalizada vacía para {derivado_ruta_abs!r}", "catalog_error": False}
        fila_dup2 = conn2.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?",
            (derivado_norm2,),
        ).fetchone()
        if fila_dup2 is not None:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": fila_dup2[0], "derivacion_id": None, "error": "ruta duplicada (carrera)", "catalog_error": True}
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
        try:
            derivado_norm_new = normalizar_ruta_clave(derivado_ruta_abs)
        except Exception as exc:
            conn2.rollback()
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 no se pudo normalizar ruta derivada {derivado_ruta_abs!r}: {exc}", "catalog_error": False}
        if not derivado_norm_new or not derivado_norm_new.strip():
            conn2.rollback()
            return {"ok": False, "derivado_video_id": None, "derivacion_id": None, "error": f"B8.3 ruta_normalizada vacía para {derivado_ruta_abs!r}", "catalog_error": False}
        fila_new = conn2.execute(
            "SELECT id FROM videos WHERE ruta_normalizada = ?",
            (derivado_norm_new,),
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

    B8.1 dual-write: actualiza conjuntamente ruta_normalizada vía
    normalizar_ruta_clave. Valida video_id y persiste en una única transacción.
    No toca filesystem. Lanza sqlite3.IntegrityError si viola UNIQUE(nombre)
    o UNIQUE(ruta_normalizada).
    """
    _validar_video_id(video_id)
    if not isinstance(nuevo_nombre, str) or not nuevo_nombre:
        raise ValueError("nuevo_nombre debe ser texto no vacío")
    if not isinstance(nueva_ruta, str) or not nueva_ruta:
        raise ValueError("nueva_ruta debe ser texto no vacío")
    ruta_normalizada = normalizar_ruta_clave(nueva_ruta)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        cur = conn.execute(
            "UPDATE videos SET nombre = ?, ruta = ?, ruta_normalizada = ? WHERE id = ?",
            (nuevo_nombre, nueva_ruta, ruta_normalizada, video_id),
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


def actualizar_ruta_video(video_id, nueva_ruta, ruta_db=None):
    """Helper corto B7.2 — actualiza únicamente ruta en transacción.

    B8.1 dual-write: actualiza conjuntamente ruta_normalizada.
    Valida video_id y persiste en una única transacción. No toca filesystem.
    Lanza ValueError si video_id no existe.
    """
    _validar_video_id(video_id)
    if not isinstance(nueva_ruta, str) or not nueva_ruta.strip():
        raise ValueError("nueva_ruta debe ser texto no vacío")
    ruta_abs = os.path.abspath(nueva_ruta)
    ruta_normalizada = normalizar_ruta_clave(nueva_ruta)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        cur = conn.execute(
            "UPDATE videos SET ruta = ?, ruta_normalizada = ? WHERE id = ?",
            (ruta_abs, ruta_normalizada, video_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise ValueError(f"video_id {video_id} no existe")
        conn.commit()
        return {"ok": True, "video_id": video_id, "ruta": ruta_abs}
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


def actualizar_cantidad_miniaturas(video_id, cantidad, ruta_db=None):
    """B8.1 — actualiza exclusivamente `cantidad_miniaturas` por `video_id`.

    Usa `UPDATE ... WHERE id = ?` con semántica `COALESCE` para preservar el
    valor existente cuando `cantidad` no es válido (None/no-int). No modifica
    nombre, ruta, ruta_normalizada, metadata ni relaciones.
    """
    _validar_video_id(video_id)
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    # Normalizar cantidad: solo int >=0 es válido; otros se preservan (COALESCE con NULL)
    cantidad_valida = cantidad if isinstance(cantidad, int) and not isinstance(cantidad, bool) and cantidad >= 0 else None
    conn = sqlite3.connect(ruta_db)
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        # COALESCE: si cantidad_valida es None, conserva existente
        cur = conn.execute(
            "UPDATE videos SET cantidad_miniaturas = COALESCE(?, cantidad_miniaturas) WHERE id = ?",
            (cantidad_valida, video_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            raise ValueError(f"video_id {video_id} no existe")
        conn.commit()
        # Devolver valor persistido (para verificación)
        fila = conn.execute(
            "SELECT cantidad_miniaturas FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return {"ok": True, "video_id": video_id, "cantidad_miniaturas": fila[0] if fila else None}
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


def actualizar_cantidad_miniaturas_batch(actualizaciones, ruta_db=None):
    """B8.1 — actualización batch de `cantidad_miniaturas` por `video_id`.

    `actualizaciones`: iterable de dicts `{video_id, cantidad}` o tuplas `(video_id, cantidad)`.
    Aplica `UPDATE ... WHERE id = ?` por fila con `COALESCE` idéntico a
    `actualizar_cantidad_miniaturas`. No modifica otros campos. Retorna
    `{"actualizados": n, "detalles": [...]}`.
    """
    if isinstance(actualizaciones, (str, bytes, bytearray)):
        raise TypeError("actualizaciones debe ser colección iterable")
    try:
        lista = list(actualizaciones)
    except TypeError:
        raise TypeError("actualizaciones debe ser colección iterable") from None
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    actualizados = 0
    detalles = []
    try:
        conn.execute("BEGIN")
        _asegurar_columnas_videos(conn)
        _asegurar_ruta_normalizada(conn)
        for item in lista:
            if isinstance(item, dict):
                vid = item.get("video_id", item.get("id"))
                cant = item.get("cantidad_miniaturas", item.get("cantidad"))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                vid, cant = item[0], item[1]
            else:
                raise TypeError("cada actualización debe ser dict o tupla (video_id, cantidad)")
            _validar_video_id(vid)
            cant_valida = cant if isinstance(cant, int) and not isinstance(cant, bool) and cant >= 0 else None
            cur = conn.execute(
                "UPDATE videos SET cantidad_miniaturas = COALESCE(?, cantidad_miniaturas) WHERE id = ?",
                (cant_valida, vid),
            )
            if cur.rowcount:
                actualizados += 1
                detalles.append({"video_id": vid, "cantidad_miniaturas": cant_valida})
        conn.commit()
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
    return {"actualizados": actualizados, "detalles": detalles}


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
