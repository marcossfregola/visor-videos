import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import operaciones
import visor_videos
from tareas import GestorTareas, TareaBase
from visor_videos import TareaCopiarArchivos, TareaEliminarArchivos, TareaPegarArchivos, VisorVideos

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


class _DialogoEliminar:
    Question = 4
    AcceptRole = 0
    RejectRole = 1
    _respuesta = "cancelar"

    def __init__(self, *args, **kwargs):
        self._botones = []

    def setIcon(self, icono):
        pass

    def setWindowTitle(self, titulo):
        pass

    def setText(self, texto):
        pass

    def addButton(self, texto, rol):
        self._botones.append(texto)
        return texto

    def setDefaultButton(self, boton):
        pass

    def exec(self):
        return 0

    def clickedButton(self):
        return "Eliminar" if self._respuesta == "eliminar" else "Cancelar"


class TareaLenta(TareaBase):
    def _trabajo(self):
        time.sleep(0.5)
        return {}


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


def _esperar_ops(ventana, timeout_ms=10000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if not ventana.gestor_operaciones.activo and ventana.gestor_operaciones.hilo is None:
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return True


def _esperar_cadena(ventana, timeout_ms=20000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if not ventana.gestor.activo and ventana.gestor.hilo is None:
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return not ventana.gestor.activo


def _correr_con_progreso(tarea, timeout_ms=10000):
    g = GestorTareas()
    progresos = []
    bucle = QEventLoop()
    flags = {"timeout": False}

    def al_progreso(p, t):
        progresos.append((p, t))

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    g.tarea_progreso.connect(al_progreso)
    g.tarea_finalizada.connect(fin)
    QTimer.singleShot(timeout_ms, por_si_acaso)
    ok = g.iniciar(tarea)
    if ok:
        bucle.exec()
    g.cerrar()
    return progresos, ok, flags


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) callbacks opcionales en las funciones puras ---
    temp = tempfile.TemporaryDirectory()
    origen = os.path.join(temp.name, "origen")
    destino = os.path.join(temp.name, "destino")
    os.makedirs(origen)
    os.makedirs(destino)
    for n in ("a.mp4", "b.mp4", "c.mp4"):
        _crear_archivo(os.path.join(origen, n))
    _crear_archivo(os.path.join(destino, "a.mp4"))
    try:
        # copiar_archivos (a ya existe en destino → omitido)
        avances = []
        res_con = operaciones.copiar_archivos(
            origen, ["a.mp4", "b.mp4", "c.mp4"], destino,
            lambda p, t: avances.append((p, t)),
        )
        destino_b = os.path.join(temp.name, "destino_b")
        os.makedirs(destino_b)
        _crear_archivo(os.path.join(destino_b, "a.mp4"))
        res_sin = operaciones.copiar_archivos(
            origen, ["a.mp4", "b.mp4", "c.mp4"], destino_b
        )
        verifica(
            avances == [(1, 3), (2, 3), (3, 3)]
            and res_con == res_sin
            and len(res_con["copiados"]) == 2
            and len(res_con["omitidos"]) == 1,
            "copiar_archivos emite (procesado,total) por archivo (incluye omitidos) y conserva el resultado sin callback",
            extra=avances,
        )
        # pegar_archivos
        pegar_origen = os.path.join(temp.name, "pegar_src")
        os.makedirs(pegar_origen)
        for n in ("x.mp4", "y.mp4"):
            _crear_archivo(os.path.join(pegar_origen, n))
        pegar_destino = os.path.join(temp.name, "pegar_dest")
        os.makedirs(pegar_destino)
        avances = []
        res_con = operaciones.pegar_archivos(
            [os.path.join(pegar_origen, "x.mp4"), os.path.join(pegar_origen, "y.mp4")],
            pegar_destino,
            lambda p, t: avances.append((p, t)),
        )
        pegar_destino_b = os.path.join(temp.name, "pegar_dest_b")
        os.makedirs(pegar_destino_b)
        res_sin = operaciones.pegar_archivos(
            [os.path.join(pegar_origen, "x.mp4"), os.path.join(pegar_origen, "y.mp4")],
            pegar_destino_b,
        )
        verifica(
            avances == [(1, 2), (2, 2)] and res_con == res_sin,
            "pegar_archivos emite (procesado,total) por archivo y conserva el resultado sin callback",
            extra=avances,
        )
        # eliminar_archivos
        elim_src = os.path.join(temp.name, "elim_src")
        os.makedirs(elim_src)
        rutas_elim = []
        for n in ("d.mp4", "e.mp4", "f.mp4"):
            r = os.path.join(elim_src, n)
            _crear_archivo(r)
            rutas_elim.append(r)
        avances = []
        res_con = operaciones.eliminar_archivos(
            rutas_elim, lambda p, t: avances.append((p, t))
        )
        verifica(
            avances == [(1, 3), (2, 3), (3, 3)]
            and len(res_con["eliminados"]) == 3,
            "eliminar_archivos emite (procesado,total) por archivo",
            extra=avances,
        )
    finally:
        temp.cleanup()

    # --- B) relay de progreso a través de las tareas ---
    temp = tempfile.TemporaryDirectory()
    origen = os.path.join(temp.name, "origen")
    destino = os.path.join(temp.name, "destino")
    os.makedirs(origen)
    os.makedirs(destino)
    for n in ("a.mp4", "b.mp4", "c.mp4"):
        _crear_archivo(os.path.join(origen, n))
    try:
        prog, ok, fl = _correr_con_progreso(
            TareaCopiarArchivos(origen, ["a.mp4", "b.mp4", "c.mp4"], destino)
        )
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaCopiarArchivos reenvía el progreso por archivo",
            extra=prog,
        )
        prog, ok, fl = _correr_con_progreso(
            TareaPegarArchivos(
                [os.path.join(origen, "a.mp4"), os.path.join(origen, "b.mp4")],
                destino,
            )
        )
        verifica(
            ok and not fl["timeout"] and prog == [(1, 2), (2, 2)],
            "TareaPegarArchivos reenvía el progreso por archivo",
            extra=prog,
        )
        elim_rutas = [os.path.join(origen, n) for n in ("a.mp4", "b.mp4", "c.mp4")]
        prog, ok, fl = _correr_con_progreso(TareaEliminarArchivos(elim_rutas))
        verifica(
            ok and not fl["timeout"] and prog == [(1, 3), (2, 3), (3, 3)],
            "TareaEliminarArchivos reenvía el progreso por archivo",
            extra=prog,
        )
    finally:
        temp.cleanup()

    # --- C) la barra de la ventana se vuelve determinada durante las operaciones ---
    with _ventana_con(["v01.mp4", "v02.mp4", "v03.mp4"]) as (ventana, _):
        destino = tempfile.TemporaryDirectory()
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: destino.name
        )
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4", "v03.mp4"}
            ventana._actualizar_botones_carpeta()
            ventana._mostrar_progreso("Copiando…")
            estados = []
            ventana.gestor_operaciones.tarea_progreso.connect(
                lambda p, t: estados.append(
                    (ventana.barra_progreso.maximum(), ventana.barra_progreso.value())
                )
            )
            ventana._atajo_copiar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                estados == [(3, 1), (3, 2), (3, 3)],
                "Copiar vuelve determinada la barra de la ventana",
                extra=estados,
            )
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original
            destino.cleanup()

    with _ventana_con(["v01.mp4"]) as (ventana, carpeta_videos):
        src = tempfile.TemporaryDirectory()
        try:
            _crear_archivo(os.path.join(src.name, "x.mp4"), "xxx")
            _crear_archivo(os.path.join(src.name, "y.mp4"), "yyy")
            ventana._portapapeles = [
                os.path.join(src.name, "x.mp4"),
                os.path.join(src.name, "y.mp4"),
            ]
            ventana._actualizar_botones_carpeta()
            ventana._mostrar_progreso("Pegando…")
            estados = []
            ventana.gestor_operaciones.tarea_progreso.connect(
                lambda p, t: estados.append(
                    (ventana.barra_progreso.maximum(), ventana.barra_progreso.value())
                )
            )
            ventana._atajo_pegar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                estados == [(2, 1), (2, 2)],
                "Pegar vuelve determinada la barra de la ventana",
                extra=estados,
            )
            _esperar_cadena(ventana)
        finally:
            src.cleanup()

    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, _):
        qmb_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._actualizar_botones_carpeta()
            ventana._mostrar_progreso("Eliminando…")
            estados = []
            ventana.gestor_operaciones.tarea_progreso.connect(
                lambda p, t: estados.append(
                    (ventana.barra_progreso.maximum(), ventana.barra_progreso.value())
                )
            )
            _DialogoEliminar._respuesta = "eliminar"
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                estados == [(2, 1), (2, 2)],
                "Eliminar vuelve determinada la barra de la ventana",
                extra=estados,
            )
            _esperar_cadena(ventana)
        finally:
            visor_videos.QMessageBox = qmb_original

    # --- D) exclusión mutua con el pipeline principal ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, _):
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: "deberia_no_abrirse"
        )
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._portapapeles = ["no_existe.mp4"]
            ventana._actualizar_botones_carpeta()
            ventana.gestor.iniciar(TareaLenta())
            QApplication.processEvents()
            verifica(ventana.gestor.activo, "pipeline principal ocupado")
            verifica(
                not ventana.boton_copiar.isEnabled()
                and not ventana.boton_pegar.isEnabled()
                and not ventana.boton_eliminar.isEnabled(),
                "los botones de operaciones se deshabilitan con el pipeline activo",
            )
            ventana._atajo_copiar.activated.emit()
            ventana._atajo_pegar.activated.emit()
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            verifica(
                not ventana.gestor_operaciones.activo
                and not os.path.exists("deberia_no_abrirse"),
                "los atajos de operaciones no hacen nada con el pipeline activo",
            )
            _esperar_cadena(ventana)
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original

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
