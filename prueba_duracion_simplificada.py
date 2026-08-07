import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication, QLabel

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import Tarjeta, VisorVideos, formatear_tiempo

_CONTADOR = [0]
_FALLOS = [0]


def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]


def ok(mensaje):
    _paso()
    print(f"T{_CONTADOR[0]:02d} OK - {mensaje}")


def falla(mensaje, extra=None):
    _FALLOS[0] += 1
    _paso()
    texto = f"T{_CONTADOR[0]:02d} ERROR - {mensaje}"
    if extra is not None:
        texto += f" ({extra})"
    print(texto)


def verifica(condicion, descripcion, extra=None):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion, extra)


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()


def _campos_de(tarjeta):
    campos = {}
    for etiqueta in tarjeta.findChildren(QLabel):
        texto = etiqueta.text()
        if not texto.startswith("<b>"):
            continue
        partes = texto.split("</b>")
        clave = partes[0][len("<b>"):]
        campos[clave] = partes[1].strip()
    return campos


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- 1) formato m:ss / h:mm:ss (reutiliza formatear_tiempo) ---
    casos = [
        (5, "0:05"),
        (41.070833, "0:41"),
        (65, "1:05"),
        (15 * 60 + 42, "15:42"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (2 * 3600 + 35 * 60 + 18, "2:35:18"),
    ]
    for segundos, esperado in casos:
        verifica(
            formatear_tiempo(segundos) == esperado,
            f"formatear_tiempo({segundos}) = {esperado}",
        )

    # --- 2) Tarjeta con duración válida: m:ss / h:mm:ss ---
    with _miniaturas_temporales():
        for duracion, esperado in [(5.0, "0:05"), (65.0, "1:05"), (9318.0, "2:35:18")]:
            tarjeta = Tarjeta(("clip.mp4", duracion, 640, 360, "h264", 1, 1024))
            campos = _campos_de(tarjeta)
            verifica(
                campos.get("Duración:") == esperado,
                f"tarjeta duración {duracion} muestra {esperado}",
                extra=campos.get("Duración:"),
            )
            verifica(
                campos.get("Resolución:") == "640x360"
                and campos.get("Codec:") == "h264"
                and campos.get("Miniaturas:") == "1",
                f"duración {duracion}: Resolución/Codec/Miniaturas intactos",
            )

    # --- 3) duración inexistente o inválida: No disponible ---
    with _miniaturas_temporales():
        for duracion in (None, 0, -5, True, "abc"):
            tarjeta = Tarjeta(("clip.mp4", duracion, 640, 360, "h264", 1, 1024))
            campos = _campos_de(tarjeta)
            verifica(
                campos.get("Duración:") == "No disponible",
                f"duración {duracion!r} muestra 'No disponible'",
                extra=campos.get("Duración:"),
            )

    # --- 4) integración con VisorVideos (duración desde catálogo) ---
    with _miniaturas_temporales():
        temp = tempfile.TemporaryDirectory()
        ruta_db = os.path.join(temp.name, "catalogo.db")
        ruta_config = os.path.join(temp.name, "config.json")
        try:
            conn = sqlite3.connect(ruta_db)
            conn.execute(
                """
                CREATE TABLE videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL UNIQUE,
                    ruta TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    fecha_importacion TEXT NOT NULL,
                    duracion_segundos REAL,
                    ancho INTEGER,
                    alto INTEGER,
                    codec_video TEXT,
                    cantidad_miniaturas INTEGER,
                    tamano_bytes INTEGER
                )
                """
            )
            conn.executemany(
                "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("corto.mp4", "C:\\corto.mp4", ".mp4", "2026-08-06T00:00:00", 5.0, 640, 360, "h264", 1, 1024),
                    ("minutos.mp4", "C:\\minutos.mp4", ".mp4", "2026-08-06T00:00:00", 942.0, 640, 360, "h264", 1, 1024),
                    ("hora.mp4", "C:\\hora.mp4", ".mp4", "2026-08-06T00:00:00", 9318.0, 640, 360, "h264", 1, 1024),
                    ("desconocido.mp4", "C:\\desconocido.mp4", ".mp4", "2026-08-06T00:00:00", None, 640, 360, "h264", 0, 1024),
                ],
            )
            conn.commit()
            conn.close()

            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.resize(900, 600)
            ventana.show()

            def esperar(predicado, intentos=300):
                for _ in range(intentos):
                    QApplication.processEvents()
                    if predicado():
                        return True
                    time.sleep(0.02)
                QApplication.processEvents()
                return predicado()

            try:
                esperar(
                    lambda: ventana._carga_completada
                    and ventana.gestor.hilo is None
                )
                verifica(
                    len(ventana.tarjetas) == 4,
                    "integración: 4 tarjetas cargadas",
                )
                esperado_por_nombre = {
                    "corto.mp4": "0:05",
                    "minutos.mp4": "15:42",
                    "hora.mp4": "2:35:18",
                    "desconocido.mp4": "No disponible",
                }
                for nombre, esperado in esperado_por_nombre.items():
                    campos = _campos_de(dict(ventana.tarjetas)[nombre])
                    verifica(
                        campos.get("Duración:") == esperado,
                        f"integración: {nombre} muestra '{esperado}'",
                        extra=campos.get("Duración:"),
                    )
            finally:
                ventana.close()
                ventana.gestor.cerrar()
                ventana.gestor_previews.cerrar()
        finally:
            temp.cleanup()

    total = _CONTADOR[0] - 1
    errores = _FALLOS[0]
    print(f"TOTAL={total - errores}/{total}")
    if errores == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
