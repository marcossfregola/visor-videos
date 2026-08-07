import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
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

    # --- A) mecanismo: la sincronización usa la carpeta capturada (override) ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, carpeta_a):
        B = tempfile.TemporaryDirectory()
        try:
            ventana._carpeta_sincronizacion = carpeta_a
            ventana.carpeta_seleccionada = B.name
            ventana._actualizar_botones_carpeta()
            ventana._sincronizacion_pendiente = True
            ventana._iniciar_sincronizacion()
            verifica(
                ventana.tarea_sincronizacion is not None
                and ventana.tarea_sincronizacion.carpeta == carpeta_a,
                "la sincronización usa la carpeta capturada, no la carpeta actual",
                extra=ventana.tarea_sincronizacion.carpeta
                if ventana.tarea_sincronizacion is not None
                else None,
            )
            verifica(
                ventana._carpeta_sincronizacion is None,
                "el override de carpeta se consume y se limpia",
            )
            _esperar_cadena(ventana)
            QApplication.processEvents()
            verifica(
                carpeta_a in ventana.carpetas_escaneadas
                and B.name not in ventana.carpetas_escaneadas,
                "se marca como escaneada la carpeta original, no la nueva",
                extra=sorted(ventana.carpetas_escaneadas),
            )
        finally:
            B.cleanup()

    # --- B) sin override: la sincronización usa la carpeta actual (comportamiento normal) ---
    with _ventana_con(["v01.mp4"]) as (ventana, _):
        B = tempfile.TemporaryDirectory()
        try:
            ventana.carpeta_seleccionada = B.name
            ventana._actualizar_botones_carpeta()
            ventana._sincronizacion_pendiente = True
            ventana._iniciar_sincronizacion()
            verifica(
                ventana.tarea_sincronizacion is not None
                and ventana.tarea_sincronizacion.carpeta == B.name,
                "sin override la sincronización usa la carpeta actual",
            )
            _esperar_cadena(ventana)
        finally:
            B.cleanup()

    # --- C) Pegar con cambio de carpeta durante la cadena incremental ---
    with _ventana_con(["v01.mp4"]) as (ventana, carpeta_a):
        B = tempfile.TemporaryDirectory()
        src = tempfile.TemporaryDirectory()
        try:
            _crear_archivo(os.path.join(src.name, "x.mp4"), "xxx")
            ventana._portapapeles = [os.path.join(src.name, "x.mp4")]
            ventana._actualizar_botones_carpeta()

            orig_guardado = ventana._al_resultado_guardado

            def guardado_con_cambio(resultado):
                ventana.carpeta_seleccionada = B.name
                return orig_guardado(resultado)

            ventana._al_resultado_guardado = guardado_con_cambio
            ventana._atajo_pegar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                "x.mp4" in nombres and "v01.mp4" in nombres,
                "el archivo recién pegado no se elimina del catálogo",
                extra=sorted(nombres),
            )
            verifica(
                carpeta_a in ventana.carpetas_escaneadas
                and B.name not in ventana.carpetas_escaneadas,
                "la sincronización del Pegar usó la carpeta original y no la nueva",
                extra=sorted(ventana.carpetas_escaneadas),
            )
            verifica(
                ventana._carpeta_sincronizacion is None,
                "tras el Pegar el override queda limpio",
            )
        finally:
            ventana._al_resultado_guardado = orig_guardado
            B.cleanup()
            src.cleanup()

    # --- D) regresión: Eliminar normal sigue actualizando el catálogo ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, _):
        qmb_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4"}
            ventana._actualizar_botones_carpeta()
            _DialogoEliminar._respuesta = "eliminar"
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                "v01.mp4" not in nombres and "v02.mp4" in nombres,
                "regresión: el Eliminar normal sigue actualizando el catálogo",
                extra=sorted(nombres),
            )
        finally:
            visor_videos.QMessageBox = qmb_original

    # --- E) regresión: Pegar normal (sin cambio de carpeta) sigue incorporando ---
    with _ventana_con(["v01.mp4"]) as (ventana, carpeta_a):
        src = tempfile.TemporaryDirectory()
        try:
            _crear_archivo(os.path.join(src.name, "y.mp4"), "yyy")
            ventana._portapapeles = [os.path.join(src.name, "y.mp4")]
            ventana._actualizar_botones_carpeta()
            ventana._atajo_pegar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                "y.mp4" in nombres,
                "regresión: el Pegar normal sigue incorporando el archivo",
                extra=sorted(nombres),
            )
        finally:
            src.cleanup()

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
