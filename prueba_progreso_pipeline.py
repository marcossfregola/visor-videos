import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import escanear_videos
import visor_videos
from tareas import GestorTareas
from tareas_videos import (
    TareaFFprobe,
    TareaGuardarVideos,
    TareaMiniaturas,
    TareaTamanosArchivos,
)
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


def _esquema(conn):
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


def _registro(nombre, ruta):
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": ".mp4",
        "fecha_importacion": "2026-08-07T00:00:00",
    }


def _correr_con_progreso(tarea, timeout_ms=8000):
    g = GestorTareas()
    progresos = []
    resultados = []
    bucle = QEventLoop()
    flags = {"timeout": False}

    def al_progreso(p, t):
        progresos.append((p, t))

    def al_resultado(valor):
        resultados.append(valor)

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    g.tarea_progreso.connect(al_progreso)
    g.tarea_resultado.connect(al_resultado)
    g.tarea_finalizada.connect(fin)
    QTimer.singleShot(timeout_ms, por_si_acaso)
    ok = g.iniciar(tarea)
    if ok:
        bucle.exec()
    g.cerrar()
    return progresos, resultados, ok, flags


@contextlib.contextmanager
def _ventana_con():
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
    conn = sqlite3.connect(ruta_db)
    _esquema(conn)
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
        yield ventana
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        ventana.gestor_operaciones.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) callbacks opcionales en las funciones puras ---
    temp = tempfile.TemporaryDirectory()
    carpeta = os.path.join(temp.name, "carpeta")
    os.makedirs(carpeta)
    ruta_db = os.path.join(temp.name, "db.db")
    conn = sqlite3.connect(ruta_db)
    _esquema(conn)
    conn.commit()
    conn.close()
    for nombre in ("a.bin", "b.bin", "c.bin"):
        _crear_archivo(os.path.join(carpeta, nombre))
    try:
        # obtener_tamanos_archivos
        avances = []
        res_con = escanear_videos.obtener_tamanos_archivos(
            ["a.bin", "b.bin", "c.bin"], carpeta,
            lambda p, t: avances.append((p, t)),
        )
        res_sin = escanear_videos.obtener_tamanos_archivos(
            ["a.bin", "b.bin", "c.bin"], carpeta
        )
        verifica(
            avances == [(1, 3), (2, 3), (3, 3)]
            and res_con == res_sin,
            "obtener_tamanos_archivos emite (procesado,total) y conserva el resultado sin callback",
            extra=avances,
        )
        # asegurar_miniaturas (sin reales: short-circuit por archivo)
        avances = []
        res_con = escanear_videos.asegurar_miniaturas(
            ["a.bin", "b.bin", "c.bin"], carpeta,
            lambda p, t: avances.append((p, t)),
        )
        res_sin = escanear_videos.asegurar_miniaturas(
            ["a.bin", "b.bin", "c.bin"], carpeta
        )
        verifica(
            avances == [(1, 3), (2, 3), (3, 3)]
            and res_con == res_sin,
            "asegurar_miniaturas emite por ítem y conserva el resultado sin callback",
            extra=avances,
        )
        # guardar_videos
        avances = []
        registros = [
            _registro("a.mp4", os.path.join(carpeta, "a.bin")),
            _registro("b.mp4", os.path.join(carpeta, "b.bin")),
        ]
        res_con = escanear_videos.guardar_videos(
            registros, ruta_db, lambda p, t: avances.append((p, t))
        )
        res_sin = escanear_videos.guardar_videos(
            registros, ruta_db
        )
        verifica(
            avances == [(1, 2), (2, 2)]
            and res_con == res_sin,
            "guardar_videos emite durante el guardado y conserva el resultado sin callback",
            extra=avances,
        )
    finally:
        temp.cleanup()

    # --- B) relay de progreso a través de las tareas (GestorTareas) ---
    temp = tempfile.TemporaryDirectory()
    carpeta = os.path.join(temp.name, "carpeta")
    os.makedirs(carpeta)
    for n in ("v01.mp4", "v02.mp4", "v03.mp4"):
        _crear_archivo(os.path.join(carpeta, n))
    ruta_db = os.path.join(temp.name, "db.db")
    conn = sqlite3.connect(ruta_db)
    _esquema(conn)
    conn.commit()
    conn.close()
    try:
        rutas = [os.path.join(carpeta, n) for n in ("v01.mp4", "v02.mp4", "v03.mp4")]
        prog, res, ok, fl = _correr_con_progreso(TareaFFprobe(rutas))
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaFFprobe reenvía el progreso por ruta",
            extra=prog,
        )
        prog, res, ok, fl = _correr_con_progreso(
            TareaTamanosArchivos(["v01.mp4", "v02.mp4", "v03.mp4"], carpeta)
        )
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaTamanosArchivos reenvía el progreso por video",
            extra=prog,
        )
        prog, res, ok, fl = _correr_con_progreso(
            TareaMiniaturas(["v01.mp4", "v02.mp4", "v03.mp4"], carpeta)
        )
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaMiniaturas reenvía el progreso por video",
            extra=prog,
        )
        prog, res, ok, fl = _correr_con_progreso(
            TareaGuardarVideos(
                [
                    _registro("a.mp4", os.path.join(carpeta, "v01.mp4")),
                    _registro("b.mp4", os.path.join(carpeta, "v02.mp4")),
                    _registro("c.mp4", os.path.join(carpeta, "v03.mp4")),
                ],
                ruta_db,
            )
        )
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaGuardarVideos reenvía el progreso por registro",
            extra=prog,
        )
    finally:
        temp.cleanup()

    # --- C) visor: reset indeterminado + handler determina la barra ---
    with _ventana_con() as ventana:
        ventana._mostrar_progreso("Etapa…")
        verifica(
            ventana.barra_progreso.minimum() == 0
            and ventana.barra_progreso.maximum() == 0
            and ventana.barra_progreso.isVisible(),
            "_mostrar_progreso deja la barra indeterminada (rango 0-0) y visible",
        )
        ventana._al_progreso_pipeline(2, 5)
        verifica(
            ventana.barra_progreso.maximum() == 5
            and ventana.barra_progreso.value() == 2,
            "el handler convierte (procesado,total) en rango y valor determinados",
        )
        ventana._mostrar_progreso("Otra…")
        verifica(
            ventana.barra_progreso.minimum() == 0
            and ventana.barra_progreso.maximum() == 0,
            "un nuevo _mostrar_progreso no arrastra el rango determinado previo",
        )

    # --- D) integración: el progreso de una tarea actualiza la barra de la ventana ---
    with _ventana_con() as ventana:
        temp = tempfile.TemporaryDirectory()
        carpeta = os.path.join(temp.name, "c")
        os.makedirs(carpeta)
        rutas = []
        for n in ("x1.mp4", "x2.mp4", "x3.mp4"):
            r = os.path.join(carpeta, n)
            _crear_archivo(r)
            rutas.append(r)
        try:
            ventana._mostrar_progreso("Prueba…")
            estados = []
            ventana.gestor.tarea_progreso.connect(
                lambda p, t: estados.append(
                    (ventana.barra_progreso.maximum(), ventana.barra_progreso.value())
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
            verifica(
                estados == [(3, 1), (3, 2), (3, 3)],
                "el progreso de la tarea actualiza la barra determinada de la ventana",
                extra=estados,
            )
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
