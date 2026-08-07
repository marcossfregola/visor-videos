import contextlib
import os
import sqlite3
import sys
import tempfile

from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from arbol_navegacion import ArbolNavegacion
from seleccion_carpetas import SeleccionCarpetas
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


def _crear_dirs(rutas):
    for r in rutas:
        os.makedirs(r, exist_ok=True)


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


def _nodo(arbol, ruta):
    return arbol._buscar_ruta(arbol.topLevelItem(0), ruta)


@contextlib.contextmanager
def _ventana_con(ruta_config):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
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
        QApplication.processEvents()
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

    temp = tempfile.TemporaryDirectory()
    cfg = os.path.join(temp.name, "config.json")
    base = os.path.join(temp.name, "carpetas")
    a = os.path.join(base, "a")
    b = os.path.join(base, "b")
    c = os.path.join(base, "c")
    _crear_dirs([a, b, c])
    try:
        sel = SeleccionCarpetas(ruta_config=cfg)
        arbol = ArbolNavegacion(seleccion=sel)
        arbol.resize(300, 400)
        arbol.show()
        arbol.activateWindow()
        QApplication.processEvents()
        raiz = arbol.topLevelItem(0)
        for ruta in (a, b, c):
            arbol._crear_nodo_carpeta(raiz, ruta)
        QApplication.processEvents()

        nodo_a = _nodo(arbol, a)
        nodo_b = _nodo(arbol, b)
        nodo_c = _nodo(arbol, c)

        # --- A) modo desactivado: idéntico al árbol actual ---
        verifica(
            all(
                not (nodo.flags() & Qt.ItemIsUserCheckable)
                for nodo in (nodo_a, nodo_b, nodo_c)
            ),
            "con el modo desactivado no hay checkboxes en los nodos",
        )
        navegaciones = []
        arbol.ruta_seleccionada.connect(navegaciones.append)
        arbol.setCurrentItem(nodo_b)
        QApplication.processEvents()
        verifica(
            arbol.carpeta_actual() == b
            and navegaciones == [b]
            and sel.obtener_seleccion() == set(),
            "navegación normal intacta y la selección no cambia con el modo desactivado",
            extra=navegaciones,
        )

        # --- B) modo activado: checks reflejan la selección ---
        arbol.set_modo_seleccion(True)
        QApplication.processEvents()
        verifica(
            all(
                (nodo.flags() & Qt.ItemIsUserCheckable)
                for nodo in (nodo_a, nodo_b, nodo_c)
            )
            and all(
                nodo.checkState(0) == Qt.Unchecked
                for nodo in (nodo_a, nodo_b, nodo_c)
            ),
            "con el modo activado los nodos muestran checks desmarcados",
        )

        # marcar/desmarcar modifica únicamente la selección
        nodo_a.setCheckState(0, Qt.Checked)
        QApplication.processEvents()
        verifica(
            sel.obtener_seleccion() == {a},
            "marcar un checkbox agrega la ruta a la selección",
        )
        verifica(
            arbol.carpeta_actual() == b,
            "marcar un checkbox no cambia la carpeta activa",
        )
        sel_persistida = SeleccionCarpetas(ruta_config=cfg)
        verifica(
            sel_persistida.obtener_seleccion() == {a},
            "la selección queda persistida al marcar",
        )
        nodo_a.setCheckState(0, Qt.Unchecked)
        QApplication.processEvents()
        verifica(
            sel.obtener_seleccion() == set(),
            "desmarcar un checkbox quita la ruta de la selección",
        )

        # seleccionar previamente y reflejarlo en los checks al activar el modo
        sel.seleccionar(b)
        arbol.set_modo_seleccion(False)
        arbol.set_modo_seleccion(True)
        QApplication.processEvents()
        verifica(
            nodo_b.checkState(0) == Qt.Checked
            and nodo_a.checkState(0) == Qt.Unchecked,
            "al activar el modo los checks reflejan el estado de la selección",
        )

        # --- C) independencia: selección no toca la navegación y viceversa ---
        arbol.setCurrentItem(nodo_c)
        QApplication.processEvents()
        verifica(
            arbol.carpeta_actual() == c
            and sel.obtener_seleccion() == {b},
            "cambiar la carpeta activa no altera la selección",
        )

        # clic real sobre el checkbox no cambia la carpeta activa
        arbol.setCurrentItem(nodo_c)
        QApplication.processEvents()
        rect = arbol.visualItemRect(nodo_a)
        punto = QPoint(rect.x() + 8, rect.y() + rect.height() // 2)
        QTest.mouseClick(
            arbol.viewport(), Qt.LeftButton, Qt.NoModifier, punto
        )
        QApplication.processEvents()
        verifica(
            nodo_a.checkState(0) == Qt.Checked
            and arbol.carpeta_actual() == c,
            "clic sobre un checkbox alterna el estado sin cambiar la carpeta activa",
        )

        # --- D) persistencia tras expansión diferida ---
        sub = os.path.join(base, "sub")
        sub1 = os.path.join(sub, "1")
        sub2 = os.path.join(sub, "2")
        _crear_dirs([sub, sub1, sub2])
        arbol._crear_nodo_carpeta(raiz, sub)
        sel.seleccionar(sub1)
        arbol.expandItem(_nodo(arbol, sub))
        QApplication.processEvents()
        nodo_sub1 = _nodo(arbol, sub1)
        nodo_sub2 = _nodo(arbol, sub2)
        verifica(
            nodo_sub1 is not None
            and nodo_sub2 is not None
            and nodo_sub1.checkState(0) == Qt.Checked
            and nodo_sub2.checkState(0) == Qt.Unchecked,
            "al expandir, los nodos nuevos reflejan la selección persistida",
        )

        # --- E) modo desactivado: vuelve al estado original ---
        arbol.set_modo_seleccion(False)
        QApplication.processEvents()
        verifica(
            all(
                not (nodo.flags() & Qt.ItemIsUserCheckable)
                for nodo in (nodo_a, nodo_b, nodo_c, _nodo(arbol, sub))
            ),
            "desactivar el modo oculta los checks (árbol idéntico al actual)",
        )
        arbol.close()
    finally:
        temp.cleanup()

    # --- F) integración con la ventana: restauración al iniciar y sin escaneo ---
    temp = tempfile.TemporaryDirectory()
    cfg = os.path.join(temp.name, "config.json")
    base = os.path.join(temp.name, "carpetas")
    a = os.path.join(base, "a")
    b = os.path.join(base, "b")
    c = os.path.join(base, "c")
    _crear_dirs([a, b, c])
    try:
        sel = SeleccionCarpetas(ruta_config=cfg)
        sel.seleccionar(a)
        sel.seleccionar(b)
        with _ventana_con(cfg) as ventana:
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == {a, b},
                "la aplicación restaura la selección al iniciar",
            )
            ventana.toggle_modo_seleccion.setChecked(True)
            QApplication.processEvents()
            verifica(
                ventana.arbol_navegacion._modo_seleccion is True,
                "el toggle activa el modo de selección del árbol",
            )
            raiz = ventana.arbol_navegacion.topLevelItem(0)
            for ruta in (a, b, c):
                ventana.arbol_navegacion._crear_nodo_carpeta(raiz, ruta)
            QApplication.processEvents()
            nodo_c = _nodo(ventana.arbol_navegacion, c)
            videos_antes = ventana.videos_detectados
            ventana.carpeta_seleccionada = a
            nodo_c.setCheckState(0, Qt.Checked)
            QApplication.processEvents()
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == {a, b, c}
                and ventana.videos_detectados is videos_antes
                and not ventana.gestor.activo
                and ventana.gestor_operaciones.activo is False
                and ventana.carpeta_seleccionada == a,
                "marcar un checkbox en la ventana solo modifica la selección (sin escaneo ni carpeta activa)",
            )
            ventana.toggle_modo_seleccion.setChecked(False)
            QApplication.processEvents()
            verifica(
                ventana.arbol_navegacion._modo_seleccion is False
                and not (nodo_c.flags() & Qt.ItemIsUserCheckable),
                "desactivar el toggle restaura el árbol al modo normal",
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
