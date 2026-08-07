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


def _consistentes(ventana):
    for nombre, tarjeta in ventana.tarjetas:
        if tarjeta._check.isChecked() != (nombre in ventana.nombres_seleccionados):
            return False
    return True


@contextlib.contextmanager
def _ventana_con(n):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
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
    for i in range(1, n + 1):
        nombre = f"v{i:02d}.mp4"
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (nombre, f"C:\\{nombre}", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
        )
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
        ventana.activateWindow()

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
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) Ctrl+A sin filtro (modo inactivo) ---
    with _ventana_con(5) as ventana:
        ventana._atajo_ctrl_a.activated.emit()
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4", "v05.mp4"}
            and ventana.resumen_seleccion.text() == "5 de 5 seleccionados"
            and _consistentes(ventana),
            "Ctrl+A sin filtro: todas las visibles (5 de 5) y consistente",
        )
        ventana._atajo_ctrl_a.activated.emit()
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4", "v05.mp4"}
            and ventana.resumen_seleccion.text() == "5 de 5 seleccionados",
            "Ctrl+A repetido: idempotente (no duplica)",
        )
        ventana._limpiar_seleccion()

    # --- B) Ctrl+A con filtro activo (solo visibles) ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v02.mp4", False)
        ventana.filtrar("v01")
        verifica(
            ventana.visibles == ["v01.mp4"],
            "filtro 'v01': solo v01 visible",
        )
        ventana._atajo_ctrl_a.activated.emit()
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4", "v02.mp4"}
            and ventana.resumen_seleccion.text() == "1 de 1 seleccionados"
            and _consistentes(ventana),
            "Ctrl+A con filtro: selecciona solo la visible (v01); v02 oculta sigue seleccionada pero no cuenta en el resumen",
            extra=f"seleccion={sorted(ventana.nombres_seleccionados)} resumen={ventana.resumen_seleccion.text()}",
        )
        ventana.filtrar("")
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "filtro limpio: 2 de 5 (v01 y v02)",
        )

    # --- C) Ctrl+A con foco en la búsqueda: no selecciona tarjetas ---
    with _ventana_con(5) as ventana:
        ventana.busqueda.setText("v03")
        ventana.busqueda.setFocus()
        QApplication.processEvents()
        verifica(
            ventana.busqueda.hasFocus(),
            "el campo de búsqueda tiene el foco",
        )
        ventana._atajo_ctrl_a.activated.emit()
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados == set()
            and ventana.busqueda.selectedText() == "v03"
            and ventana.resumen_seleccion.text() == "0 de 1 seleccionados",
            "Ctrl+A con foco en la búsqueda selecciona el texto del campo (no las tarjetas)",
            extra=f"selected={ventana.busqueda.selectedText()!r}",
        )
        ventana.busqueda.setText("")
        ventana.busqueda.clearFocus()

    # --- D) Ctrl+A con foco en un checkbox del Modo Selección ---
    with _ventana_con(5) as ventana:
        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        dict(ventana.tarjetas)["v02.mp4"]._check.setFocus()
        QApplication.processEvents()
        verifica(
            dict(ventana.tarjetas)["v02.mp4"]._check.hasFocus(),
            "foco sobre un checkbox del modo selección",
        )
        ventana._atajo_ctrl_a.activated.emit()
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4", "v05.mp4"}
            and ventana.resumen_seleccion.text() == "5 de 5 seleccionados"
            and all(t._check.isChecked() for _, t in ventana.tarjetas)
            and _consistentes(ventana),
            "Ctrl+A con foco en un checkbox: selecciona todas las visibles y marca los checks",
        )

    # --- E) Esc con modo activo: sale del modo, conserva selección y oculta checks ---
    with _ventana_con(5) as ventana:
        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        ventana._al_seleccionar_tarjeta("v02.mp4", False)
        ventana._al_seleccionar_tarjeta("v04.mp4", True)
        verifica(
            ventana._modo_seleccion
            and ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "preparación: modo activo y 2 de 5",
        )
        ventana._atajo_esc.activated.emit()
        QApplication.processEvents()
        verifica(
            not ventana._modo_seleccion
            and not ventana.boton_modo_seleccion.isChecked()
            and all(not t._check.isVisible() for _, t in ventana.tarjetas)
            and ventana.nombres_seleccionados == {"v02.mp4", "v04.mp4"}
            and ventana.resumen_seleccion.text() == "2 de 5 seleccionados"
            and _consistentes(ventana),
            "Esc con modo activo: sale del modo, checks ocultos, selección conservada (2 de 5)",
        )

    # --- F) Esc con modo inactivo: no cambia nada ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        ventana._atajo_esc.activated.emit()
        QApplication.processEvents()
        verifica(
            not ventana._modo_seleccion
            and ventana.nombres_seleccionados == {"v01.mp4"}
            and ventana.resumen_seleccion.text() == "1 de 5 seleccionados"
            and all(not t._check.isVisible() for _, t in ventana.tarjetas),
            "Esc con modo inactivo: no altera nada (1 de 5 intacto)",
        )

    # --- G) Esc con foco en la búsqueda ---
    with _ventana_con(5) as ventana:
        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        ventana.busqueda.setFocus()
        QApplication.processEvents()
        ventana._atajo_esc.activated.emit()
        QApplication.processEvents()
        verifica(
            not ventana._modo_seleccion
            and not ventana.boton_modo_seleccion.isChecked(),
            "Esc con foco en la búsqueda: también sale del modo",
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
