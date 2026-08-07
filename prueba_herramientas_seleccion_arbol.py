import contextlib
import os
import sqlite3
import sys
import tempfile

from PySide6.QtCore import Qt
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


def _checks(arbol, nodos):
    return {
        arbol._ruta_valida(n): n.checkState(0) == Qt.Checked for n in nodos
    }


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
    nivel = os.path.join(base, "Nivel")
    a = os.path.join(nivel, "a")
    b = os.path.join(nivel, "b")
    c = os.path.join(nivel, "c")
    externo = os.path.join(base, "externo")
    _crear_dirs([nivel, a, b, c, externo])
    try:
        sel = SeleccionCarpetas(ruta_config=cfg)
        arbol = ArbolNavegacion(seleccion=sel)
        arbol.resize(300, 400)
        arbol.show()
        QApplication.processEvents()
        raiz = arbol.topLevelItem(0)
        arbol._crear_nodo_carpeta(raiz, externo)
        nodo_nivel = arbol._crear_nodo_carpeta(raiz, nivel)
        nodo_a = arbol._crear_nodo_carpeta(nodo_nivel, a)
        nodo_b = arbol._crear_nodo_carpeta(nodo_nivel, b)
        nodo_c = arbol._crear_nodo_carpeta(nodo_nivel, c)
        QApplication.processEvents()

        arbol.set_modo_seleccion(True)
        arbol.setCurrentItem(nodo_nivel)
        QApplication.processEvents()

        # --- A) Seleccionar todas del nivel ---
        arbol.seleccionar_todas_nivel()
        verifica(
            sel.obtener_seleccion() == {a, b, c},
            "seleccionar_todas_nivel selecciona los hijos del nivel actual",
        )
        verifica(
            all(_checks(arbol, [nodo_a, nodo_b, nodo_c]).values()),
            "los checks del nivel quedan marcados",
        )

        # --- B) Deseleccionar todas ---
        arbol.deseleccionar_todas()
        verifica(
            sel.obtener_seleccion() == set(),
            "deseleccionar_todas vacía la selección",
        )
        verifica(
            not any(_checks(arbol, [nodo_a, nodo_b, nodo_c]).values()),
            "los checks quedan desmarcados",
        )

        # --- C) Invertir nivel (conserva lo externo) ---
        _nodo(arbol, externo).setCheckState(0, Qt.Checked)
        nodo_b.setCheckState(0, Qt.Checked)
        QApplication.processEvents()
        arbol.invertir_nivel()
        verifica(
            sel.obtener_seleccion() == {a, c, externo},
            "invertir_nivel invierte solo el nivel y conserva las selecciones externas",
            extra=sel.obtener_seleccion(),
        )
        estados = _checks(arbol, [nodo_a, nodo_b, nodo_c, _nodo(arbol, externo)])
        verifica(
            estados[a] is True
            and estados[b] is False
            and estados[c] is True
            and estados[externo] is True,
            "los checks reflejan la inversión del nivel",
        )

        # --- D) Seleccionar hasta aquí (por orden visual a, b, c) ---
        arbol.deseleccionar_todas()
        sel.seleccionar(externo)
        arbol.seleccionar_hasta(nodo_c)
        verifica(
            sel.obtener_seleccion() == {a, b, c, externo},
            "seleccionar_hasta materializa las rutas anteriores (a, b, c)",
            extra=sel.obtener_seleccion(),
        )

        # --- E) Deseleccionar hasta aquí ---
        arbol.deseleccionar_hasta(nodo_b)
        verifica(
            sel.obtener_seleccion() == {c, externo},
            "deseleccionar_hasta quita las anteriores a b (a y b)",
            extra=sel.obtener_seleccion(),
        )

        # --- F) Seleccionar desde aquí hasta el final ---
        arbol.seleccionar_desde(nodo_a)
        verifica(
            sel.obtener_seleccion() == {a, b, c, externo},
            "seleccionar_desde materializa desde a hasta el final",
        )

        # --- G) Deseleccionar desde aquí hasta el final ---
        arbol.deseleccionar_desde(nodo_b)
        verifica(
            sel.obtener_seleccion() == {a, externo},
            "deseleccionar_desde quita desde b hasta el final (b y c)",
            extra=sel.obtener_seleccion(),
        )

        # --- H) el conjunto de SeleccionCarpetas es la única fuente de verdad ---
        sel_persistida = SeleccionCarpetas(ruta_config=cfg)
        verifica(
            sel_persistida.obtener_seleccion() == {a, externo},
            "el conjunto persistido es la única fuente de verdad (sin intervalos)",
        )

        # --- I) la carpeta activa no cambia ---
        activa_antes = arbol.carpeta_actual()
        arbol.seleccionar_todas_nivel()
        arbol.invertir_nivel()
        arbol.seleccionar_hasta(nodo_b)
        arbol.deseleccionar_desde(nodo_a)
        verifica(
            arbol.carpeta_actual() == activa_antes,
            "las acciones rápidas no cambian la carpeta activa",
        )

        # --- J) sin hijos cargados: no-op ---
        arbol.deseleccionar_todas()
        nodo_vacio = arbol._crear_nodo_carpeta(raiz, os.path.join(base, "vacio"))
        _crear_dirs([os.path.join(base, "vacio")])
        arbol.setCurrentItem(nodo_vacio)
        arbol.seleccionar_todas_nivel()
        arbol.invertir_nivel()
        verifica(
            sel.obtener_seleccion() == set(),
            "acciones sobre un nivel sin hijos cargados no cambian la selección",
        )
        arbol.close()
    finally:
        temp.cleanup()

    # --- K) integración con la ventana ---
    temp = tempfile.TemporaryDirectory()
    cfg = os.path.join(temp.name, "config.json")
    base = os.path.join(temp.name, "carpetas")
    nivel = os.path.join(base, "Nivel")
    a = os.path.join(nivel, "a")
    b = os.path.join(nivel, "b")
    c = os.path.join(nivel, "c")
    _crear_dirs([nivel, a, b, c])
    try:
        with _ventana_con(cfg) as ventana:
            verifica(
                not ventana.contenedor_acciones_seleccion.isVisible(),
                "la fila de acciones está oculta sin modo selección",
            )
            ventana.toggle_modo_seleccion.setChecked(True)
            QApplication.processEvents()
            verifica(
                ventana.contenedor_acciones_seleccion.isVisible(),
                "la fila de acciones se muestra con el modo selección activo",
            )
            raiz = ventana.arbol_navegacion.topLevelItem(0)
            nodo_nivel = ventana.arbol_navegacion._crear_nodo_carpeta(raiz, nivel)
            for ruta in (a, b, c):
                ventana.arbol_navegacion._crear_nodo_carpeta(nodo_nivel, ruta)
            ventana.arbol_navegacion.setCurrentItem(nodo_nivel)
            QApplication.processEvents()
            videos_antes = ventana.videos_detectados
            ventana.carpeta_seleccionada = nivel
            ventana.boton_seleccionar_todas.click()
            QApplication.processEvents()
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == {a, b, c},
                "el botón 'Seleccionar todas' actualiza la selección",
            )
            verifica(
                ventana.carpeta_seleccionada == nivel
                and ventana.videos_detectados is videos_antes
                and not ventana.gestor.activo
                and ventana.gestor_operaciones.activo is False,
                "las acciones masivas no cambian la carpeta activa ni inician escaneos",
            )
            ventana.boton_invertir_seleccion.click()
            QApplication.processEvents()
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == set(),
                "el botón 'Invertir' invierte la selección del nivel",
            )
            ventana.boton_deseleccionar_todas.click()
            ventana.boton_seleccionar_todas.click()
            ventana.boton_deseleccionar_todas.click()
            QApplication.processEvents()
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == set(),
                "el botón 'Deseleccionar todas' vacía la selección",
            )
            ventana.toggle_modo_seleccion.setChecked(False)
            QApplication.processEvents()
            verifica(
                not ventana.contenedor_acciones_seleccion.isVisible(),
                "la fila de acciones se oculta al desactivar el modo",
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
