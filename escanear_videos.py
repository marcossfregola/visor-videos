import os
import sqlite3
import subprocess
from datetime import datetime

NOMBRE_DB = "biblioteca.db"
EXTENSIONES = {".mp4", ".mkv", ".avi"}
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

def conectar_bd():
    conn = sqlite3.connect(NOMBRE_DB)
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

def contar_miniaturas(video):
    prefijo = os.path.splitext(video)[0]
    if not os.path.isdir("miniaturas"):
        return 0
    return sum(
        1 for nombre in os.listdir("miniaturas")
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
        actualizar_datos(conn, carpeta, nombre)
    for nombre in en_bd - en_disco:
        conn.execute("DELETE FROM videos WHERE nombre = ?", (nombre,))

def listar_videos():
    conn = sqlite3.connect(NOMBRE_DB)
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

def main():
    conn = conectar_bd()
    sincronizar_bd(conn, "videos_prueba")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
