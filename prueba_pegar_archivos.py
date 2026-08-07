import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication, QMessageBox

import escanear_videos as escanear_mod
import operaciones
import visor_videos
from visor_videos import VisorVideos

_CONTADOR = [0]
_FALLOS = [0]


class _DialogoColision:
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
        return "Omitir" if self._respuesta == "omitir" else "Cancelar"


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
    ruta_v01 = os.path.join(videos.name, "v01.mp4")
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("v01.mp4", ruta_v01, ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
    )
    conn.commit()
    conn.close()
    _crear_archivo(ruta_v01)

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

    # --- A) función pura operaciones.pegar_archivos ---
    temp = tempfile.TemporaryDirectory()
    src = os.path.join(temp.name, "src")
    dest = os.path.join(temp.name, "dest")
    os.makedirs(src)
    os.makedirs(dest)
    _crear_archivo(os.path.join(src, "a.mp4"), "aaa")
    _crear_archivo(os.path.join(src, "b.mp4"), "bbb")
    try:
        res = operaciones.pegar_archivos([os.path.join(src, "a.mp4")], dest)
        verifica(
            res["copiados"] == [os.path.join(src, "a.mp4")]
            and os.path.exists(os.path.join(dest, "a.mp4")),
            "pegar_archivos: pegado simple",
        )
        res = operaciones.pegar_archivos([os.path.join(src, "a.mp4"), os.path.join(src, "b.mp4")], dest)
        verifica(
            len(res["copiados"]) == 1
            and len(res["omitidos"]) == 1
            and os.path.exists(os.path.join(dest, "b.mp4")),
            "pegar_archivos: pegado múltiple con omisión del existente",
        )
        res = operaciones.pegar_archivos([os.path.join(src, "no_existe.mp4")], dest)
        verifica(
            res["copiados"] == [] and len(res["errores"]) == 1,
            "pegar_archivos: origen inexistente registra error y continúa",
        )
        try:
            operaciones.pegar_archivos("a.mp4", dest)
            verifica(False, "pegar_archivos rechaza texto en archivos")
        except TypeError:
            ok("pegar_archivos rechaza texto en archivos (TypeError)")
        try:
            operaciones.pegar_archivos([os.path.join(src, "a.mp4")], "")
            verifica(False, "pegar_archivos rechaza destino vacío")
        except ValueError:
            ok("pegar_archivos rechaza destino vacío (ValueError)")
    finally:
        temp.cleanup()

    # --- B) integración: pegado en segundo plano + resincronización incremental ---
    with _ventana_con() as (ventana, carpeta_videos):
        srcA = tempfile.TemporaryDirectory()
        try:
            _crear_archivo(os.path.join(srcA.name, "x.mp4"), "xxx")
            _crear_archivo(os.path.join(srcA.name, "y.mp4"), "yyy")
            ventana._portapapeles = [
                os.path.join(srcA.name, "x.mp4"),
                os.path.join(srcA.name, "y.mp4"),
            ]
            ventana._actualizar_botones_carpeta()
            QApplication.processEvents()
            verifica(
                ventana.boton_pegar.isEnabled(),
                "botón Pegar habilitado con portapapeles y carpeta válida",
            )
            ventana.boton_pegar.click()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                os.path.exists(os.path.join(carpeta_videos, "x.mp4"))
                and os.path.exists(os.path.join(carpeta_videos, "y.mp4")),
                "los archivos pegados se copian a la carpeta actual",
            )
            verifica(
                ventana.estado_escaneo.text()
                == "Pegado: 2 — Omitidos: 0 — Errores: 0",
                "resumen final de pegado correcto",
                extra=ventana.estado_escaneo.text(),
            )
            # resincronización incremental: la cadena procesa solo los pegados
            termino = _esperar_cadena(ventana)
            QApplication.processEvents()
            nombres = [n for n, _ in ventana.tarjetas]
            verifica(
                termino and "x.mp4" in nombres and "y.mp4" in nombres,
                "resincronización: los archivos pegados se incorporan al catálogo",
                extra=sorted(nombres),
            )
        finally:
            srcA.cleanup()

    # --- C) colisiones: Omitir y Cancelar ---
    with _ventana_con() as (ventana, carpeta_videos):
        srcA = tempfile.TemporaryDirectory()
        qmessagebox_original = visor_videos.QMessageBox
        visor_videos.QMessageBox = _DialogoColision
        try:
            _crear_archivo(os.path.join(srcA.name, "v01.mp4"), "nuevo")
            ventana._portapapeles = [os.path.join(srcA.name, "v01.mp4")]
            ventana._actualizar_botones_carpeta()
            QApplication.processEvents()

            # Cancelar: no inicia tarea ni copia
            _DialogoColision._respuesta = "cancelar"
            ventana.boton_pegar.click()
            QApplication.processEvents()
            verifica(
                not ventana.gestor_operaciones.activo,
                "colisión + Cancelar: no inicia ninguna tarea",
            )

            # Omitir: copia y omite el existente (nunca sobrescribe)
            _DialogoColision._respuesta = "omitir"
            ventana.boton_pegar.click()
            QApplication.processEvents()
            _esperar_ops(ventana)
            verifica(
                ventana.estado_escaneo.text()
                == "Pegado: 0 — Omitidos: 1 — Errores: 0",
                "colisión + Omitir: el existente se omite (sin sobrescribir)",
                extra=ventana.estado_escaneo.text(),
            )
            with open(os.path.join(carpeta_videos, "v01.mp4"), "rb") as f:
                contenido = f.read()
            verifica(
                contenido == b"x",
                "el archivo existente no fue sobrescrito",
            )
        finally:
            visor_videos.QMessageBox = qmessagebox_original
            srcA.cleanup()

    # --- D) portapapeles vacío y carpeta inválida ---
    with _ventana_con() as (ventana, carpeta_videos):
        ventana._portapapeles = []
        ventana._actualizar_botones_carpeta()
        QApplication.processEvents()
        verifica(
            not ventana.boton_pegar.isEnabled(),
            "portapapeles vacío: botón Pegar deshabilitado",
        )
        ventana._portapapeles = [os.path.join(carpeta_videos, "x.mp4")]
        ventana.carpeta_seleccionada = os.path.join(carpeta_videos, "no_existe")
        ventana._actualizar_botones_carpeta()
        QApplication.processEvents()
        verifica(
            not ventana.boton_pegar.isEnabled(),
            "carpeta inválida: botón Pegar deshabilitado",
        )
        ventana.boton_pegar.click()
        QApplication.processEvents()
        verifica(
            not ventana.gestor_operaciones.activo,
            "clic con carpeta inválida no inicia ninguna tarea",
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
