import contextlib
import json
import os
import sqlite3
import shutil
import sys
import tempfile

from PySide6.QtWidgets import QApplication

import configuracion
import escanear_videos as escanear_mod
import visor_videos
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
    inexistente = os.path.join(base, "no_existe")
    try:
        # --- A) API del conjunto ---
        sel = SeleccionCarpetas(ruta_config=cfg)
        verifica(
            sel.obtener_seleccion() == set(),
            "la selección arranca vacía sin configuración previa",
        )
        verifica(
            sel.seleccionar(a) is True and sel.obtener_seleccion() == {a},
            "seleccionar agrega una ruta",
        )
        sel.seleccionar(a)
        verifica(
            sel.obtener_seleccion() == {a},
            "seleccionar repetido no genera duplicados",
        )
        sel.seleccionar(b)
        verifica(
            sel.obtener_seleccion() == {a, b},
            "seleccionar varias rutas",
        )
        verifica(
            sel.seleccionar(inexistente) is False
            and inexistente not in sel.obtener_seleccion(),
            "seleccionar una ruta inexistente es ignorada",
        )
        verifica(
            sel.seleccionar("") is False
            and sel.seleccionar(42) is False,
            "seleccionar valores no válidos no agrega nada",
        )
        verifica(
            sel.deseleccionar(a) is True
            and sel.obtener_seleccion() == {b},
            "deseleccionar quita la ruta",
        )
        verifica(
            sel.deseleccionar(inexistente) is True,
            "deseleccionar una ruta ausente es un no-op sin error",
        )
        verifica(
            sel.alternar(b) is False
            and sel.obtener_seleccion() == set(),
            "alternar sobre una ruta seleccionada la deselecciona",
        )
        verifica(
            sel.alternar(c) is True
            and sel.obtener_seleccion() == {c},
            "alternar sobre una ruta no seleccionada la selecciona",
        )
        agregadas = sel.seleccionar_todas([a, b, c, inexistente, a])
        verifica(
            agregadas == 2
            and sel.obtener_seleccion() == {a, b, c},
            "seleccionar_todas agrega las existentes, ignora inexistentes y no duplica",
            extra=agregadas,
        )
        sel.limpiar()
        verifica(
            sel.obtener_seleccion() == set(),
            "limpiar vacía la selección",
        )

        # --- B) persistencia y restauración ---
        sel.seleccionar(a)
        sel.seleccionar(b)
        sel2 = SeleccionCarpetas(ruta_config=cfg)
        verifica(
            sel2.obtener_seleccion() == {a, b},
            "una nueva instancia restaura la selección persistida",
        )
        shutil.rmtree(b)
        sel3 = SeleccionCarpetas(ruta_config=cfg)
        verifica(
            sel3.obtener_seleccion() == {a},
            "al restaurar se descartan automáticamente las rutas inexistentes",
        )
        copia = sel3.obtener_seleccion()
        copia.add(os.path.join(base, "fantasma"))
        verifica(
            sel3.obtener_seleccion() == {a},
            "obtener_seleccion devuelve una copia (no expone el estado interno)",
        )

        # --- C) configuracion: capa de persistencia ---
        _crear_dirs([b])
        configuracion.guardar_seleccion_carpetas([a, a, b], cfg)
        verifica(
            configuracion.obtener_seleccion_carpetas(cfg) == [a, b],
            "guardar_seleccion_carpetas deduplica y normaliza rutas",
        )
        configuracion.guardar_seleccion_carpetas([a, inexistente], cfg)
        verifica(
            configuracion.obtener_seleccion_carpetas(cfg) == [a],
            "obtener_seleccion_carpetas descarta rutas inexistentes",
        )
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"carpetas_seleccionadas": "no_es_lista"}, f)
        verifica(
            configuracion.obtener_seleccion_carpetas(cfg) == [],
            "configuración con valor inválido devuelve lista vacía",
        )
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"otra_clave": 1}, f)
        verifica(
            configuracion.obtener_seleccion_carpetas(cfg) == [],
            "configuraciones anteriores sin la clave devuelven lista vacía",
        )
        configuracion.guardar_ultima_carpeta(a, cfg)
        configuracion.guardar_seleccion_carpetas([b], cfg)
        verifica(
            configuracion.obtener_ultima_carpeta(cfg) == a
            and configuracion.obtener_seleccion_carpetas(cfg) == [b],
            "guardar la selección conserva las demás claves de configuración",
        )
    finally:
        temp.cleanup()

    # --- D) restauración al iniciar la aplicación ---
    temp = tempfile.TemporaryDirectory()
    cfg = os.path.join(temp.name, "config.json")
    base = os.path.join(temp.name, "carpetas")
    a = os.path.join(base, "a")
    b = os.path.join(base, "b")
    _crear_dirs([a, b])
    try:
        configuracion.guardar_seleccion_carpetas([a, b], cfg)
        with _ventana_con(cfg) as ventana:
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == {a, b},
                "la aplicación restaura la selección al iniciar",
            )
        shutil.rmtree(b)
        configuracion.guardar_seleccion_carpetas([a, b], cfg)
        with _ventana_con(cfg) as ventana:
            verifica(
                ventana.seleccion_carpetas.obtener_seleccion() == {a},
                "al iniciar se descartan las rutas inexistentes",
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
