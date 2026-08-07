import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from tareas_videos import TareaFFprobe
from visor_videos import VisorVideos

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


def _crear_archivo(ruta, contenido="x"):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido.encode())


@contextlib.contextmanager
def _ventana_con(nombres):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    videos = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
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
    for nombre in nombres:
        ruta = os.path.join(videos.name, nombre)
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (nombre, ruta, ".mp4", "2026-08-07T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
        )
        _crear_archivo(ruta)
    conn.commit()
    conn.close()

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    try:
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

        esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)
        ventana.carpeta_seleccionada = videos.name
        ventana.busqueda.clearFocus()
        ventana._actualizar_botones_carpeta()
        QApplication.processEvents()
        yield ventana, videos.name
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        ventana.gestor_operaciones.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) comportamiento de la barra a nivel de ventana ---
    with _ventana_con(["v01.mp4"]) as (ventana, _):
        ventana._mostrar_progreso("Etapa de prueba")
        verifica(
            ventana.barra_progreso.minimum() == 0
            and ventana.barra_progreso.maximum() == 0
            and ventana.barra_progreso.format() == "Etapa de prueba"
            and ventana._progreso_detallado is False
            and ventana.barra_progreso.isVisible(),
            "_mostrar_progreso guarda el texto, deja indeterminada y resetea el flag",
        )
        ventana._al_progreso_pipeline(3, 5)
        verifica(
            ventana.barra_progreso.maximum() == 5
            and ventana.barra_progreso.value() == 3
            and ventana.barra_progreso.format()
            == "Etapa de prueba %v de %m (%p%)"
            and ventana._progreso_detallado is True,
            "la primera emisión aplica el formato detallado etapa + N de M + porcentaje",
            extra=ventana.barra_progreso.format(),
        )
        ventana._al_progreso_pipeline(4, 5)
        verifica(
            ventana.barra_progreso.value() == 4
            and ventana.barra_progreso.format()
            == "Etapa de prueba %v de %m (%p%)",
            "las emisiones siguientes actualizan el valor sin repetir setFormat",
        )
        ventana._mostrar_progreso("Otra etapa")
        verifica(
            ventana.barra_progreso.format() == "Otra etapa"
            and ventana.barra_progreso.maximum() == 0
            and ventana._progreso_detallado is False,
            "una nueva etapa vuelve al texto simple e indeterminado (sin arrastre)",
        )
        # total <= 0 no cambia el formato (etapa indeterminada)
        ventana._al_progreso_pipeline(0, 0)
        ventana._al_progreso_pipeline(0, -1)
        verifica(
            ventana.barra_progreso.format() == "Otra etapa"
            and ventana.barra_progreso.maximum() == 0
            and ventana._progreso_detallado is False,
            "emisiones con total <= 0 no aplican el formato detallado",
        )

    # --- B) integración: el progreso de una tarea del pipeline aplica el formato detallado ---
    with _ventana_con(["v01.mp4"]) as (ventana, _):
        temp = tempfile.TemporaryDirectory()
        carpeta = os.path.join(temp.name, "c")
        os.makedirs(carpeta)
        rutas = []
        for n in ("x1.mp4", "x2.mp4", "x3.mp4"):
            r = os.path.join(carpeta, n)
            _crear_archivo(r)
            rutas.append(r)
        try:
            ventana._mostrar_progreso("Leyendo metadatos…")
            estados = []
            ventana.gestor.tarea_progreso.connect(
                lambda p, t: estados.append(
                    (
                        ventana.barra_progreso.maximum(),
                        ventana.barra_progreso.value(),
                        ventana.barra_progreso.format(),
                    )
                )
            )
            ventana.gestor.iniciar(TareaFFprobe(rutas))
            fin = time.monotonic() + 8
            while time.monotonic() < fin:
                QApplication.processEvents()
                if not ventana.gestor.activo and ventana.gestor.hilo is None:
                    break
                time.sleep(0.02)
            QApplication.processEvents()
            detalle = all(
                m == 3
                and v == p
                and f == "Leyendo metadatos… %v de %m (%p%)"
                for (m, v, f), p in zip(estados, (1, 2, 3))
            )
            verifica(
                len(estados) == 3
                and detalle,
                "la barra del pipeline muestra rango, valor y formato detallado en cada emisión",
                extra=estados,
            )
        finally:
            temp.cleanup()

    # --- C) integración: operaciones de archivos también aplican el formato detallado ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, _):
        destino = tempfile.TemporaryDirectory()
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: destino.name
        )
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._actualizar_botones_carpeta()
            ventana._mostrar_progreso("Copiando…")
            formatos = []
            ventana.gestor_operaciones.tarea_progreso.connect(
                lambda p, t: formatos.append(ventana.barra_progreso.format())
            )
            ventana._atajo_copiar.activated.emit()
            QApplication.processEvents()
            fin = time.monotonic() + 8
            while time.monotonic() < fin:
                QApplication.processEvents()
                if (
                    not ventana.gestor_operaciones.activo
                    and ventana.gestor_operaciones.hilo is None
                ):
                    break
                time.sleep(0.02)
            QApplication.processEvents()
            verifica(
                len(formatos) == 2
                and all(f == "Copiando… %v de %m (%p%)" for f in formatos),
                "la barra de Copiar aplica el formato detallado por archivo",
                extra=formatos,
            )
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original
            destino.cleanup()

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
