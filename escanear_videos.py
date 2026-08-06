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
]

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


def obtener_tamanos_archivos(videos, carpeta):
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
    resultados = [
        {"ruta": ruta, "tamano_bytes": _tamano_archivo(ruta)} for ruta in rutas
    ]
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
        por_ruta[ruta] = tamano if isinstance(tamano, int) else None
    for registro in lista:
        registro["tamano_bytes"] = por_ruta.get(
            _normalizar_ruta(registro.get("ruta"))
        )
    return lista


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
    existentes = {fila[1] for fila in conn.execute("PRAGMA table_info(videos)")}
    for nombre_col, tipo in COLUMNAS_EXTRA:
        if nombre_col not in existentes:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {nombre_col} {tipo}")
    return conn

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

def calcular_tiempo_miniatura(duracion):
    if duracion is None or duracion <= 0:
        return 1.0
    return max(0.1, min(duracion * 0.1, 10.0))

def miniatura_vigente(ruta_video, ruta_miniatura):
    if not os.path.isfile(ruta_miniatura):
        return False
    return os.path.getmtime(ruta_miniatura) >= os.path.getmtime(ruta_video)

def generar_miniatura(ruta_video, ruta_miniatura):
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

def asegurar_miniatura(video, ruta_video):
    if not ffmpeg_disponible() or os.path.getsize(ruta_video) == 0:
        return 0
    if miniatura_reutilizable(video, ruta_video) is not None:
        return 1
    os.makedirs(ruta_carpeta_miniaturas(), exist_ok=True)
    ruta = ruta_miniatura(video, siguiente_indice_libre(video))
    if os.path.isfile(ruta):
        return 0
    return 1 if generar_miniatura(ruta_video, ruta) else 0

def asegurar_miniaturas(videos, carpeta):
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
        if not os.path.isfile(ruta_video):
            resultados.append(
                {"ruta": ruta_video, "asegurada": 0, "cantidad_miniaturas": 0}
            )
            continue
        asegurada = asegurar_miniatura(nombre, ruta_video)
        resultados.append(
            {
                "ruta": ruta_video,
                "asegurada": asegurada,
                "cantidad_miniaturas": contar_miniaturas(nombre),
            }
        )
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

def generar_preview(ruta_video, destino, indice=None):
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

def generar_previews_faltantes(videos, carpeta):
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
                    and generar_preview(ruta_video, destino, indice)
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
            SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes
            FROM videos
            ORDER BY nombre
            """
        ).fetchall()
    finally:
        conn.close()


def detectar_diferencias(carpeta, ruta_db=None):
    if not isinstance(carpeta, str) or not carpeta:
        raise ValueError("carpeta debe ser una ruta de texto no vacía")
    if not os.path.isdir(carpeta):
        raise FileNotFoundError(f"Carpeta no encontrada: {carpeta}")
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    en_disco = set(escanear_videos(carpeta))
    conn = sqlite3.connect(ruta_db)
    try:
        en_bd = {fila[0] for fila in conn.execute("SELECT nombre FROM videos")}
    finally:
        conn.close()
    return {
        "carpeta": carpeta,
        "presentes_en_ambos": sorted(en_disco & en_bd),
        "nuevos": sorted(en_disco - en_bd),
        "ausentes_del_disco": sorted(en_bd - en_disco),
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


def listar_videos_paginado(limite, desplazamiento=0, texto=None, ruta_db=None):
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
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        if texto is None:
            filas = conn.execute(
                """
                SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes
                FROM videos
                ORDER BY nombre
                LIMIT ? OFFSET ?
                """,
                (limite, desplazamiento),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        else:
            patron = f"%{texto}%"
            filas = conn.execute(
                """
                SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes
                FROM videos
                WHERE nombre LIKE ?
                ORDER BY nombre
                LIMIT ? OFFSET ?
                """,
                (patron, limite, desplazamiento),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE nombre LIKE ?",
                (patron,),
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
        INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            ruta = excluded.ruta,
            extension = excluded.extension,
            fecha_importacion = excluded.fecha_importacion,
            duracion_segundos = excluded.duracion_segundos,
            ancho = excluded.ancho,
            alto = excluded.alto,
            codec_video = excluded.codec_video,
            cantidad_miniaturas = excluded.cantidad_miniaturas,
            tamano_bytes = excluded.tamano_bytes
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
        _upsert_video(conn, datos)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"guardado": True, "nombre": datos["nombre"]}


def guardar_videos(datos_videos, ruta_db=None):
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
    try:
        for datos in registros:
            _upsert_video(conn, datos)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"guardados": len(registros), "nombres": [d["nombre"] for d in registros]}

def main():
    conn = conectar_bd()
    sincronizar_bd(conn, ruta_carpeta_videos())
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
