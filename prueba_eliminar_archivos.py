import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import operaciones
import visor_videos
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


@contextlib.contextmanager
def _ventana_con():
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
    for nombre in ("v01.mp4", "v02.mp4"):
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
        ventana._actualizar_botones_carpeta()
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


def _esperar_ops(ventana, timeout_ms=8000):
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


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) función pura operaciones.eliminar_archivos ---
    temp = tempfile.TemporaryDirectory()
    src = os.path.join(temp.name, "src")
    os.makedirs(src)
    try:
        ruta1 = os.path.join(src, "a.mp4")
        ruta2 = os.path.join(src, "b.mp4")
        _crear_archivo(ruta1, "aaa")
        _crear_archivo(ruta2, "bbb")

        res = operaciones.eliminar_archivos([ruta1])
        verifica(
            res["eliminados"] == [ruta1]
            and res["omitidos"] == []
            and res["errores"] == []
            and not os.path.exists(ruta1),
            "eliminar_archivos: eliminación simple a la Papelera",
            extra=res,
        )
        res = operaciones.eliminar_archivos([ruta2])
        verifica(
            res["eliminados"] == [ruta2] and not os.path.exists(ruta2),
            "eliminar_archivos: eliminación individual (2º archivo)",
        )
        ruta3 = os.path.join(src, "c.mp4")
        ruta4 = os.path.join(src, "d.mp4")
        _crear_archivo(ruta3, "ccc")
        _crear_archivo(ruta4, "ddd")
        res = operaciones.eliminar_archivos([ruta3, ruta4])
        verifica(
            res["eliminados"] == [ruta3, ruta4]
            and not os.path.exists(ruta3)
            and not os.path.exists(ruta4),
            "eliminar_archivos: eliminación múltiple",
        )
        res = operaciones.eliminar_archivos([os.path.join(src, "no_existe.mp4")])
        verifica(
            res["eliminados"] == [] and len(res["errores"]) == 1,
            "eliminar_archivos: archivo inexistente registra error y continúa",
        )
        ruta_bloqueada = os.path.join(src, "bloqueado.mp4")
        _crear_archivo(ruta_bloqueada, "zzz")
        with open(ruta_bloqueada, "rb") as f:
            res = operaciones.eliminar_archivos([ruta_bloqueada])
        verifica(
            res["eliminados"] == [] and len(res["errores"]) == 1,
            "eliminar_archivos: archivo bloqueado registra error",
            extra=res,
        )
        verifica(
            os.path.exists(ruta_bloqueada),
            "el archivo bloqueado sigue existiendo (no se eliminó)",
        )
        try:
            operaciones.eliminar_archivos("a.mp4")
            verifica(False, "eliminar_archivos rechaza texto en archivos")
        except TypeError:
            ok("eliminar_archivos rechaza texto en archivos (TypeError)")
    finally:
        temp.cleanup()

    # --- B) cancelación ---
    with _ventana_con() as (ventana, carpeta_videos):
        qmessagebox_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4"}
            ventana._actualizar_botones_carpeta()
            QApplication.processEvents()
            verifica(
                ventana.boton_eliminar.isEnabled(),
                "botón Eliminar habilitado con selección y carpeta válida",
            )
            _DialogoEliminar._respuesta = "cancelar"
            ventana.boton_eliminar.click()
            QApplication.processEvents()
            verifica(
                not ventana.gestor_operaciones.activo,
                "cancelación: no inicia ninguna tarea",
            )
            verifica(
                os.path.exists(os.path.join(carpeta_videos, "v01.mp4")),
                "cancelación: el archivo no fue eliminado",
            )
        finally:
            visor_videos.QMessageBox = qmessagebox_original

    # --- C) eliminación en segundo plano + resumen + actualización incremental ---
    with _ventana_con() as (ventana, carpeta_videos):
        qmessagebox_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._actualizar_botones_carpeta()
            QApplication.processEvents()
            _DialogoEliminar._respuesta = "eliminar"
            original_procesar = ventana._procesar_archivos_eliminados
            ventana._procesar_archivos_eliminados = lambda: None
            ventana.boton_eliminar.click()
            QApplication.processEvents()
            _esperar_ops(ventana)
            ventana._procesar_archivos_eliminados = original_procesar
            verifica(
                ventana.estado_escaneo.text()
                == "Eliminado: 2 — Omitidos: 0 — Errores: 0",
                "resumen final de eliminación correcto",
                extra=ventana.estado_escaneo.text(),
            )
            verifica(
                not os.path.exists(os.path.join(carpeta_videos, "v01.mp4"))
                and not os.path.exists(os.path.join(carpeta_videos, "v02.mp4")),
                "los archivos eliminados dejan de existir en la carpeta",
            )
            # actualización incremental del catálogo (sincronización + recarga)
            ventana._procesar_archivos_eliminados()
            termino = _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                termino and nombres == [],
                "actualización incremental: los eliminados salen del catálogo",
                extra=sorted(nombres),
            )
            verifica(
                ventana.contador.text() == "0 videos",
                "el contador se actualiza tras la eliminación",
                extra=ventana.contador.text(),
            )
            verifica(
                ventana._nombres_seleccionados == set(),
                "la selección restante queda limpia tras eliminar todo",
            )
        finally:
            visor_videos.QMessageBox = qmessagebox_original

    # --- D) eliminación simple con resto en el catálogo ---
    with _ventana_con() as (ventana, carpeta_videos):
        qmessagebox_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4"}
            ventana._actualizar_botones_carpeta()
            QApplication.processEvents()
            _DialogoEliminar._respuesta = "eliminar"
            ventana.boton_eliminar.click()
            QApplication.processEvents()
            _esperar_ops(ventana)
            _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                nombres == ["v02.mp4"],
                "eliminación simple: solo el eliminado sale del catálogo",
                extra=sorted(nombres),
            )
            verifica(
                ventana.contador.text() == "1 video",
                "el contador refleja el catálogo restante",
                extra=ventana.contador.text(),
            )
            verifica(
                os.path.exists(os.path.join(carpeta_videos, "v02.mp4")),
                "el archivo no eliminado permanece en la carpeta",
            )
        finally:
            visor_videos.QMessageBox = qmessagebox_original

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
