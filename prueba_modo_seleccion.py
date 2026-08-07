import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import Tarjeta, VisorVideos

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


def _fila(nombre):
    return (nombre, 100.0, 1920, 1080, "h264", 1, 1024)


def _fila_bd(nombre):
    n, d, ancho, alto, codec, miniaturas, tamano = _fila(nombre)
    return (
        n, f"C:\\{n}", os.path.splitext(n)[1].lower(), "2026-08-06T00:00:00",
        d, ancho, alto, codec, miniaturas, tamano,
    )


def _consistentes(ventana):
    for nombre, tarjeta in ventana.tarjetas:
        if tarjeta._check.isChecked() != (nombre in ventana._nombres_seleccionados):
            return False
    return True


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
    nombres = [f"v{i:02d}.mp4" for i in range(1, n + 1)]
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [_fila_bd(nombre) for nombre in nombres],
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

    # --- A) tarjeta directa: checkbox oculto, mostrar/set, sin reentrada ---
    with _miniaturas_temporales():
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        tarjeta = Tarjeta(("v01.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
        contenedor = QWidget()
        contenedor.setLayout(QVBoxLayout())
        contenedor.layout().addWidget(tarjeta)
        contenedor.show()
        QApplication.processEvents()
        try:
            verifica(
                not tarjeta._check.isVisible(),
                "checkbox oculto por defecto",
            )
            tarjeta.mostrar_check(True)
            QApplication.processEvents()
            verifica(
                tarjeta._check.isVisible(),
                "mostrar_check(True) muestra el checkbox",
            )
            emitidos = []
            tarjeta.seleccion_check.connect(lambda n, m: emitidos.append((n, m)))
            tarjeta.set_check(True)
            verifica(
                tarjeta._check.isChecked() and emitidos == [],
                "set_check marca con blockSignals (sin señal de retorno)",
            )
            tarjeta._check.setChecked(False)
            verifica(
                emitidos == [("v01.mp4", False)],
                "toggle real del checkbox emite seleccion_check",
                extra=emitidos,
            )
        finally:
            contenedor.close()

    # --- B) ventana: modo, sincronización, simple/Ctrl/Shift, consistencia ---
    with _ventana_con(5) as ventana:
        verifica(
            not ventana._modo_seleccion,
            "modo desactivado inicialmente",
        )
        verifica(
            all(not t._check.isVisible() for _, t in ventana.tarjetas),
            "checks ocultos con modo desactivado",
        )
        verifica(
            ventana.resumen_seleccion.text() == "0 de 5 seleccionados",
            "resumen inicial: 0 de 5",
        )

        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        verifica(
            ventana._modo_seleccion
            and all(t._check.isVisible() for _, t in ventana.tarjetas),
            "activar modo: checks visibles en todas las tarjetas",
        )
        verifica(
            _consistentes(ventana),
            "consistencia check <-> selección (modo activo, nada seleccionado)",
        )

        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        verifica(
            dict(ventana.tarjetas)["v01.mp4"]._check.isChecked()
            and ventana.resumen_seleccion.text() == "1 de 5 seleccionados"
            and _consistentes(ventana),
            "selección simple: check de v01 marcado y resumen 1 de 5",
        )

        ventana._al_seleccionar_tarjeta("v02.mp4", True)
        verifica(
            dict(ventana.tarjetas)["v02.mp4"]._check.isChecked()
            and ventana.resumen_seleccion.text() == "2 de 5 seleccionados"
            and _consistentes(ventana),
            "Ctrl+clic: check de v02 marcado y resumen 2 de 5",
        )

        ventana._al_seleccion_por_rango("v04.mp4")
        verifica(
            ventana.resumen_seleccion.text() == "3 de 5 seleccionados"
            and _consistentes(ventana),
            "Shift+clic rango (v02-v04): 3 de 5 y consistente",
        )

        ventana.boton_modo_seleccion.setChecked(False)
        QApplication.processEvents()
        verifica(
            not ventana._modo_seleccion
            and all(not t._check.isVisible() for _, t in ventana.tarjetas)
            and ventana.resumen_seleccion.text() == "3 de 5 seleccionados"
            and _consistentes(ventana),
            "desactivar modo: checks ocultos, selección intacta (3 de 5)",
        )

        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        # deselección vía checkbox (v03)
        dict(ventana.tarjetas)["v03.mp4"]._check.setChecked(False)
        QApplication.processEvents()
        verifica(
            "v03.mp4" not in ventana.nombres_seleccionados
            and not dict(ventana.tarjetas)["v03.mp4"]._seleccionada
            and ventana.resumen_seleccion.text() == "2 de 5 seleccionados"
            and _consistentes(ventana),
            "checkbox desmarcado quita la selección (v03) y el borde",
        )
        # selección vía checkbox (v05)
        dict(ventana.tarjetas)["v05.mp4"]._check.setChecked(True)
        QApplication.processEvents()
        verifica(
            "v05.mp4" in ventana.nombres_seleccionados
            and dict(ventana.tarjetas)["v05.mp4"]._seleccionada
            and ventana.resumen_seleccion.text() == "3 de 5 seleccionados"
            and _consistentes(ventana),
            "checkbox marcado selecciona la tarjeta (v05)",
            extra=(
                f"seleccion={sorted(ventana.nombres_seleccionados)} "
                f"resumen={ventana.resumen_seleccion.text()} "
                f"consistente={_consistentes(ventana)} "
                f"v05_seleccionada={dict(ventana.tarjetas)['v05.mp4']._seleccionada}"
            ),
        )

    # --- C) sin reentrada: una sola incorporación por acción ---
    with _ventana_con(5) as ventana:
        ventana._al_check_tarjeta("v01.mp4", True)
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4"}
            and ventana.resumen_seleccion.text() == "1 de 5 seleccionados"
            and _consistentes(ventana),
            "check -> selección agrega una sola vez (sin reentrada)",
        )
        ventana._al_check_tarjeta("v01.mp4", True)
        verifica(
            ventana.nombres_seleccionados == {"v01.mp4"},
            "repetir la misma acción no duplica la selección",
        )

    # --- D) restauración tras recarga y búsqueda, con modo activo ---
    with _ventana_con(5) as ventana:
        ventana.boton_modo_seleccion.setChecked(True)
        QApplication.processEvents()
        ventana._al_seleccionar_tarjeta("v02.mp4", False)
        ventana._al_seleccionar_tarjeta("v04.mp4", True)
        ventana._reemplazar_tarjetas(
            [_fila(f"v{i:02d}.mp4") for i in range(1, 6)]
        )
        QApplication.processEvents()
        verifica(
            ventana.nombres_seleccionados == {"v02.mp4", "v04.mp4"}
            and all(t._check.isVisible() for _, t in ventana.tarjetas)
            and _consistentes(ventana)
            and ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "recarga con modo activo: checks visibles, selección restaurada y consistente",
        )

        ventana.filtrar("v04")
        verifica(
            ventana.visibles == ["v04.mp4"]
            and ventana.resumen_seleccion.text() == "1 de 1 seleccionados"
            and _consistentes(ventana),
            "búsqueda: resumen solo de visibles y checks consistentes",
        )
        ventana.filtrar("")
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados"
            and _consistentes(ventana),
            "búsqueda limpia: 2 de 5 y consistente",
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
