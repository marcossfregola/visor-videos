import os
import shutil
import sqlite3
import subprocess
from datetime import datetime

from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos

EXTENSIONES = {".mp4", ".mkv", ".avi"}
EXTENSION_MINIATURA = ".jpg"
COLUMNAS_EXTRA = [
    ("duracion_segundos", "REAL"),
    ("ancho", "INTEGER"),
    ("alto", "INTEGER"),
    ("codec_video", "TEXT"),
    ("cantidad_miniaturas", "INTEGER"),
]

def escanear_videos(carpeta):
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
    prefijo = os.path.splitext(video)[0]
    return os.path.join(
        ruta_carpeta_miniaturas(),
        f"{prefijo}_{indice:02d}{EXTENSION_MINIATURA}",
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
    prefijo = os.path.splitext(video)[0]
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return None
    for nombre in sorted(os.listdir(carpeta)):
        if os.path.splitext(nombre)[0].startswith(prefijo):
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

def contar_miniaturas(video):
    prefijo = os.path.splitext(video)[0]
    carpeta = ruta_carpeta_miniaturas()
    if not os.path.isdir(carpeta):
        return 0
    return sum(
        1 for nombre in os.listdir(carpeta)
        if os.path.splitext(nombre)[0].startswith(prefijo)
    )

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
    if datos is None:
        conn.execute(
            "UPDATE videos SET duracion_segundos = NULL, ancho = NULL, alto = NULL, codec_video = NULL, cantidad_miniaturas = ? WHERE nombre = ?",
            (miniaturas, nombre),
        )
    else:
        conn.execute(
            "UPDATE videos SET duracion_segundos = ?, ancho = ?, alto = ?, codec_video = ?, cantidad_miniaturas = ? WHERE nombre = ?",
            (datos["duracion_segundos"], datos["ancho"], datos["alto"], datos["codec_video"], miniaturas, nombre),
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
            SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas
            FROM videos
            ORDER BY nombre
            """
        ).fetchall()
    finally:
        conn.close()


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
                SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas
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
                SELECT nombre, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas
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
        INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            ruta = excluded.ruta,
            extension = excluded.extension,
            fecha_importacion = excluded.fecha_importacion,
            duracion_segundos = excluded.duracion_segundos,
            ancho = excluded.ancho,
            alto = excluded.alto,
            codec_video = excluded.codec_video,
            cantidad_miniaturas = excluded.cantidad_miniaturas
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
