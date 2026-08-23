"""Preparación reproducible del seed DB para el packaging Beta 6.

Genera una biblioteca.db VACIA con el esquema vigente directamente en
dist\\VisorVideos\\biblioteca.db usando la capa productiva (escanear_videos.conectar_bd),
sin copiar la biblioteca.db local de desarrollo (ignorada, puede contener datos).

Verifica:
- PRAGMA integrity_check = ok
- tablas del esquema vigente presentes
- conteos videos/marcadores/segmentos/derivados = 0
- no contiene datos de usuario

Falla ruidosamente (exit 1) ante cualquier error. No oculta excepciones.
Uso: python preparar_empaquetado.py [--dest dist\\VisorVideos\\biblioteca.db]
"""

import argparse
import os
import sqlite3
import sys

import escanear_videos


DESTINO_DEFAULT = os.path.join("dist", "VisorVideos", "biblioteca.db")
TABLAS_ESPERADAS = ("videos", "marcadores_video", "segmentos_video", "videos_derivados", "videos_derivados_segmentos")


def _fail(msg):
    print(f"[preparar_empaquetado] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Genera biblioteca.db vacia para packaging")
    parser.add_argument("--dest", default=DESTINO_DEFAULT, help="Ruta destino de la DB seed")
    args = parser.parse_args()
    dest = os.path.abspath(args.dest)
    parent = os.path.dirname(dest)

    if not os.path.isdir(parent):
        _fail(f"Directorio destino no existe (ejecutar PyInstaller antes): {parent}")

    # No copiar DB local: siempre crear nueva vacia. Eliminar previa si existe.
    if os.path.isfile(dest):
        try:
            os.remove(dest)
        except OSError as exc:
            _fail(f"No se pudo eliminar DB previa {dest}: {exc}")

    # Crear DB vacia con esquema vigente productivo
    try:
        conn = escanear_videos.conectar_bd(dest)
        conn.commit()
        conn.close()
    except Exception as exc:
        _fail(f"Fallo al crear DB vacia con conectar_bd({dest!r}): {type(exc).__name__}: {exc}")

    if not os.path.isfile(dest):
        _fail(f"DB no creada: {dest}")

    # Verificaciones estrictas
    try:
        conn = sqlite3.connect(dest)
    except Exception as exc:
        _fail(f"No se pudo abrir DB generada: {exc}")

    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        if not row or row[0] != "ok":
            _fail(f"PRAGMA integrity_check != ok: {row}")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = {r[0] for r in cur.fetchall()}
        faltantes = [t for t in TABLAS_ESPERADAS if t not in tablas]
        if faltantes:
            _fail(f"Tablas faltantes en seed DB: {faltantes} (halladas: {sorted(tablas)})")

        for tabla in ("videos", "marcadores_video", "segmentos_video", "videos_derivados", "videos_derivados_segmentos"):
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                cnt = cur.fetchone()[0]
            except sqlite3.OperationalError as exc:
                _fail(f"Error al contar {tabla}: {exc}")
            if cnt != 0:
                _fail(f"Seed DB no vacia: {tabla} COUNT={cnt} (esperado 0)")

        # Verificacion adicional: schema columnas vigentes
        cur.execute("PRAGMA table_info(videos)")
        cols = {r[1] for r in cur.fetchall()}
        for col in ("duracion_segundos", "ancho", "alto", "codec_video", "tamano_bytes", "mtime_ns"):
            if col not in cols:
                _fail(f"Columna faltante en videos.{col}")

        cur.execute("SELECT COUNT(*) FROM videos")
        videos = cur.fetchone()[0]
        print(f"[preparar_empaquetado] OK: {dest} creada, integrity_check=ok, videos={videos}, tablas={sorted(tablas)}, size={os.path.getsize(dest)} bytes")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
