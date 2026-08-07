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
from tareas import TareaBase
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
    _llamadas = [0]

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
        self._llamadas[0] += 1
        return 0

    def clickedButton(self):
        return "Eliminar" if self._respuesta == "eliminar" else "Cancelar"


class TareaLenta(TareaBase):
    def _trabajo(self):
        time.sleep(0.5)
        return {"copiados": [], "omitidos": [], "errores": []}


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

    # --- A) los atajos reutilizan los mismos handlers que los botones ---
    with _ventana_con(["v01.mp4", "v02.mp4", "v03.mp4"]) as (ventana, _):
        copias = {"n": 0}
        pegados = {"n": 0}
        eliminados = {"n": 0}
        original_copiar = ventana._iniciar_copia
        original_pegar = ventana._iniciar_pegar
        original_eliminar = ventana._iniciar_eliminar
        ventana._iniciar_copia = lambda: copias.update(n=copias["n"] + 1)
        ventana._iniciar_pegar = lambda: pegados.update(n=pegados["n"] + 1)
        ventana._iniciar_eliminar = lambda: eliminados.update(n=eliminados["n"] + 1)
        try:
            ventana._atajo_copiar.activated.emit()
            ventana._atajo_pegar.activated.emit()
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            verifica(
                copias["n"] == 1 and pegados["n"] == 1 and eliminados["n"] == 1,
                "los atajos reutilizan los handlers de los botones (uno por atajo)",
                extra=f"c={copias['n']} p={pegados['n']} e={eliminados['n']}",
            )
        finally:
            ventana._iniciar_copia = original_copiar
            ventana._iniciar_pegar = original_pegar
            ventana._iniciar_eliminar = original_eliminar

    # --- B) Ctrl+C inicia Copiar (flujo real) ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, carpeta_videos):
        destino = tempfile.TemporaryDirectory()
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: destino.name
        )
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._actualizar_botones_carpeta()
            ventana._atajo_copiar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                os.path.exists(os.path.join(destino.name, "v01.mp4"))
                and os.path.exists(os.path.join(destino.name, "v02.mp4")),
                "Ctrl+C inicia Copiar: archivos copiados al destino",
            )
            verifica(
                "Copiado: 2" in ventana.estado_escaneo.text(),
                "Ctrl+C muestra el resumen de Copiar",
                extra=ventana.estado_escaneo.text(),
            )
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original
            destino.cleanup()

    # --- C) Ctrl+V inicia Pegar (flujo real) ---
    with _ventana_con(["v01.mp4"]) as (ventana, carpeta_videos):
        src = tempfile.TemporaryDirectory()
        try:
            _crear_archivo(os.path.join(src.name, "x.mp4"), "xxx")
            ventana._portapapeles = [os.path.join(src.name, "x.mp4")]
            ventana._actualizar_botones_carpeta()
            ventana._atajo_pegar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                os.path.exists(os.path.join(carpeta_videos, "x.mp4")),
                "Ctrl+V inicia Pegar: archivo copiado a la carpeta actual",
            )
            _esperar_cadena(ventana)
        finally:
            src.cleanup()

    # --- D) Supr inicia Eliminar (flujo real) ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, carpeta_videos):
        qmb_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        try:
            ventana._nombres_seleccionados = {"v01.mp4"}
            ventana._actualizar_botones_carpeta()
            _DialogoEliminar._respuesta = "eliminar"
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                not os.path.exists(os.path.join(carpeta_videos, "v01.mp4")),
                "Supr inicia Eliminar: el archivo se envía a la Papelera",
            )
            _esperar_cadena(ventana)
        finally:
            visor_videos.QMessageBox = qmb_original

    # --- E) sin selección / sin portapapeles: no ocurre ninguna operación ---
    with _ventana_con(["v01.mp4"]) as (ventana, _):
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: "deberia_no_abrirse"
        )
        qmb_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        _DialogoEliminar._llamadas = [0]
        _DialogoEliminar._respuesta = "eliminar"
        try:
            ventana._atajo_copiar.activated.emit()
            ventana._atajo_pegar.activated.emit()
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                not ventana.gestor_operaciones.activo,
                "sin selección ni portapapeles: no inicia ninguna operación",
            )
            verifica(
                not os.path.exists("deberia_no_abrirse"),
                "sin selección: Ctrl+C no abre el diálogo de destino",
            )
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original
            visor_videos.QMessageBox = qmb_original

    # --- F) gestor ocupado bloquea los tres atajos ---
    with _ventana_con(["v01.mp4", "v02.mp4"]) as (ventana, _):
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: "deberia_no_abrirse"
        )
        qmb_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoEliminar
        _DialogoEliminar._llamadas = [0]
        _DialogoEliminar._respuesta = "eliminar"
        try:
            ventana._nombres_seleccionados = {"v01.mp4", "v02.mp4"}
            ventana._portapapeles = []
            ventana._actualizar_botones_carpeta()
            ventana.gestor_operaciones.iniciar(TareaLenta())
            QApplication.processEvents()
            verifica(
                ventana.gestor_operaciones.activo,
                "gestor de operaciones ocupado (tarea lenta en curso)",
            )
            ventana._atajo_copiar.activated.emit()
            ventana._atajo_pegar.activated.emit()
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            verifica(
                not os.path.exists("deberia_no_abrirse")
                and _DialogoEliminar._llamadas == [0],
                "gestor ocupado: los tres atajos no realizan ninguna acción",
            )
            _esperar_ops(ventana)
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original
            visor_videos.QMessageBox = qmb_original

    # --- G) foco en la búsqueda: comportamiento nativo del campo ---
    with _ventana_con(["v01.mp4"]) as (ventana, _):
        qfd_original = visor_videos.QFileDialog.getExistingDirectory
        visor_videos.QFileDialog.getExistingDirectory = (
            lambda *a, **k: "deberia_no_abrirse"
        )
        try:
            ventana.busqueda.setText("v03")
            ventana.busqueda.selectAll()
            ventana.busqueda.setFocus()
            QApplication.processEvents()
            ventana._atajo_copiar.activated.emit()
            QApplication.processEvents()
            verifica(
                QApplication.clipboard().text() == "v03",
                "Ctrl+C con foco en la búsqueda copia el texto del campo",
                extra=QApplication.clipboard().text(),
            )
            verifica(
                not ventana.gestor_operaciones.activo
                and not os.path.exists("deberia_no_abrirse"),
                "Ctrl+C con foco en la búsqueda no inicia ninguna operación",
            )

            QApplication.clipboard().setText("hola")
            ventana.busqueda.setText("abc")
            ventana.busqueda.setCursorPosition(1)
            ventana.busqueda.setFocus()
            QApplication.processEvents()
            ventana._atajo_pegar.activated.emit()
            QApplication.processEvents()
            verifica(
                ventana.busqueda.text() == "aholabc",
                "Ctrl+V con foco en la búsqueda pega en el campo (sin operación)",
                extra=ventana.busqueda.text(),
            )

            ventana.busqueda.setText("abc")
            ventana.busqueda.setCursorPosition(1)
            ventana.busqueda.setFocus()
            QApplication.processEvents()
            ventana._atajo_eliminar.activated.emit()
            QApplication.processEvents()
            verifica(
                ventana.busqueda.text() == "ac",
                "Supr con foco en la búsqueda borra el carácter (sin operación)",
                extra=ventana.busqueda.text(),
            )
            ventana.busqueda.setText("")
            ventana.busqueda.clearFocus()
        finally:
            visor_videos.QFileDialog.getExistingDirectory = qfd_original

    # --- H) compatibilidad con los atajos de B3.13 ---
    with _ventana_con(["v01.mp4", "v02.mp4", "v03.mp4"]) as (ventana, _):
        ventana._atajo_ctrl_a.activated.emit()
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados
            == {"v01.mp4", "v02.mp4", "v03.mp4"},
            "Ctrl+A (B3.13) sigue seleccionando todas las visibles",
        )
        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        verifica(ventana._modo_seleccion, "modo selección activo (preparación)")
        ventana._atajo_esc.activated.emit()
        QApplication.processEvents()
        verifica(
            not ventana._modo_seleccion
            and not ventana.boton_modo_seleccion.isChecked(),
            "Esc (B3.13) sigue saliendo del modo selección",
        )

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
